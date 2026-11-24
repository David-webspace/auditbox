import json
import re
import shutil
import time
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import pymupdf

from . import audit, form, mail, reference, routing, zh
from .config import Workspace
from .db import DB
from .extract import extract_case
from .llm import LLM

Log = Callable[[str], None]
Extractor = Callable[[Path, Path, Log], dict]


class Stopped(Exception):
    pass


@dataclass
class InboxItem:
    base: str
    invoice: str | None
    attachment: str | None
    pages: int
    modified: str
    problem: str | None


def scan_inbox(ws: Workspace, pic: str) -> list[InboxItem]:
    folder = ws.folder("inbox") / pic
    suffix = ws.settings["files"]["invoice_suffix"]
    groups: dict[str, dict] = {}
    for p in sorted(folder.glob("*.pdf")):
        is_inv = p.stem.endswith(suffix)
        base = p.stem[: -len(suffix)] if is_inv else p.stem
        groups.setdefault(base, {})["invoice" if is_inv else "attachment"] = p
    items = []
    for base, g in groups.items():
        files = list(g.values())
        pages = sum(len(pymupdf.open(f)) for f in files)
        problem = None if len(g) == 2 else ("缺發票檔（檔名需為「" + base + suffix + ".pdf」）" if "invoice" not in g
                                            else "缺附件檔（檔名需為「" + base + ".pdf」）")
        items.append(InboxItem(base, g.get("invoice", Path()).name or None, g.get("attachment", Path()).name or None,
                               pages, datetime.fromtimestamp(max(f.stat().st_mtime for f in files)).strftime("%m/%d %H:%M"),
                               problem))
    return items


def processed_pos(ws: Workspace) -> set[str]:
    pattern = re.compile(ws.settings["patterns"]["po_no"])
    out = set()
    for d in ws.folder("done").glob("*/*"):
        if d.is_dir() and (m := pattern.match(d.name)):
            out.add(m.group())
    return out


def _move(files: list[Path], dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    return [Path(shutil.move(str(f), dest / f.name)) for f in files]


def _report_md(case_id: str, outcome: str, findings: list, route, draft) -> str:
    lines = [f"# {case_id}　{audit.OUTCOME_LABEL[outcome]}", "", "## 稽核結果", ""]
    for f in findings:
        mark = {"pass": "✅", "fail": "❌", "skipped": "－"}[f.status]
        lines.append(f"- {mark} {f.rule} {f.name}：{f.message}")
    lines += ["", "## 信件草稿", "", f"- 主旨：{draft.subject}", f"- 收件人：{', '.join(route.to)}",
              f"- 副本：{', '.join(route.cc) or '（無）'}", "- 檔案：草稿.eml（雙擊用 Outlook 開啟後確認送出）"]
    if route.warnings:
        lines += ["", "## 寄信對照表提醒", ""] + [f"- {w}" for w in route.warnings]
    return "\n".join(lines) + "\n"


class Pipeline:
    def __init__(self, ws: Workspace, db: DB, extractor: Extractor, llm: LLM | None):
        self.ws, self.db, self.extractor, self.llm = ws, db, extractor, llm
        self.ref = reference.load(ws)
        self.rules = routing.load(ws.config_dir / ws.settings["files"]["mail_routing"])

    def process(self, pic: str, base: str, log: Log = print) -> dict:
        ws, s = self.ws, self.ws.settings
        inbox = ws.folder("inbox") / pic
        inv = inbox / f"{base}{s['files']['invoice_suffix']}.pdf"
        att = inbox / f"{base}.pdf"
        now = datetime.now()
        case_id = f"{now:%Y%m%d-%H%M%S}-{pic}-{base}"
        try:
            run = None
            for attempt in range(s["retry"] + 1):
                try:
                    run = self.extractor(inv, att, log)
                    break
                except Stopped:
                    raise
                except Exception as e:
                    log(f"  擷取失敗（第 {attempt + 1} 次）：{e}")
                    if attempt == s["retry"]:
                        raise
                    time.sleep(2)
            docs = run["documents"]
            findings, ctx = audit.run(docs, self.ref, ws.rules, processed_pos(ws))
            outcome = audit.outcome(findings, ws.rules["outcome_priority"])
            log(f"  稽核結果：{audit.OUTCOME_LABEL[outcome]}" +
                "".join(f"\n    ❌ {f.rule} {f.message}" for f in findings if f.status == "fail"))
            pic_emp = self.ref.employees[s["pics"][pic]]
            po = ctx.po_no or "未知PO"
            case = {"pic": pic_emp, "files": run["files"]}
            vals = None
            if outcome == "ready_to_sign":
                dest = ws.folder("done") / pic / f"{po}_{zh.t(base)}"
                vals = form.values(ws.form_map, ctx, docs, pic_emp, now)
                xlsx = form.write_xlsx(ws.config_dir / s["files"]["form_template"], ws.form_map, vals,
                                       ws.folder("forms") / pic / f"{po}_資產驗收單_{now:%Y%m%d_%H%M}.xlsx")
                merged = form.merge([form.render_pdf(s["company"]["name"], ws.form_map, vals), inv, att],
                                    dest / f"{po}_{zh.t(base)}_驗收單合併.pdf")
                case |= {"form_xlsx": xlsx, "merged_pdf": merged.relative_to(ws.root)}
                log(f"  驗收單：{xlsx.relative_to(ws.root)}")
            else:
                dest = ws.folder("manual") / pic / f"{po}_{zh.t(base)}"
            route = routing.resolve(self.rules, self.ref, outcome, [f.rule for f in findings if f.status == "fail"],
                                    ctx.vendor, (ctx.sap_po or {}).get("產品線"), pic_emp["Email"])
            draft = mail.compose(outcome=outcome, findings=findings, ctx=ctx, case=case, route=route, form_vals=vals,
                                 company=s["company"]["name"], llm=self.llm, llm_mode=s["mail"]["llm_intro"],
                                 company_en=s["company"].get("name_en"))
            eml = mail.to_eml(draft, s["mail"]["from"], dest / "草稿.eml")
            if s["mail"]["mode"] == "mailpit":
                mail.send_mailpit(eml, s["mail"]["mailpit"]["host"], s["mail"]["mailpit"]["port"])
            originals = _move([inv, att], dest / "原始檔")
            (dest / "稽核結果.md").write_text(_report_md(case_id, outcome, findings, route, draft), encoding="utf-8")
            detail = {"case_id": case_id, "extraction": run, "findings": audit.to_dict(findings),
                      "outcome": outcome, "form": vals, "originals": {k: str(p.relative_to(dest)) for k, p in
                                                                       zip(("invoice", "attachment"), originals)},
                      "route": asdict(route), "draft": {"subject": draft.subject, "html": draft.html,
                                                        "lang": draft.lang, "intro_source": draft.intro_source,
                                                        "to": draft.to, "cc": draft.cc}}
            (dest / "case.json").write_text(json.dumps(detail, ensure_ascii=False, indent=2, default=str),
                                            encoding="utf-8")
            vendor = ctx.vendor.short if ctx.vendor else (ctx.sap_po or {}).get("供應商名稱", "")
            self.db.add(id=case_id, pic=pic, base=base, po_no=ctx.po_no, vendor=vendor, outcome=outcome,
                        status=audit.OUTCOME_LABEL[outcome], folder=str(dest))
            log(f"  草稿：{eml.relative_to(ws.root)}（To {', '.join(draft.to)}）")
            return {"case_id": case_id, "outcome": outcome}
        except Stopped:
            raise
        except Exception as e:
            dest = ws.folder("manual") / pic / f"系統失敗_{zh.t(base)}"
            _move([p for p in (inv, att) if p.exists()], dest / "原始檔")
            (dest / "失敗原因.md").write_text(f"# {case_id} 系統處理失敗\n\n{e}\n\n```\n{traceback.format_exc()}```\n",
                                           encoding="utf-8")
            self.db.add(id=case_id, pic=pic, base=base, po_no=None, vendor="", outcome="system_error",
                        status="系統失敗", folder=str(dest))
            log(f"  ❌ 系統失敗，已移到 {dest.relative_to(ws.root)}：{e}")
            return {"case_id": case_id, "outcome": "system_error"}


def llm_extractor(ws: Workspace, llm: LLM, should_stop: Callable[[], bool] = lambda: False) -> Extractor:
    def run(inv: Path, att: Path, log: Log) -> dict:
        def guarded(msg: str):
            if should_stop():
                raise Stopped()
            log(msg)

        return extract_case(inv, att, llm, ws.settings["patterns"], guarded)

    return run
