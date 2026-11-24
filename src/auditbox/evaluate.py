import argparse
import json
from collections import defaultdict
from pathlib import Path

from . import config, localstore
from . import normalize as N
from .extract import JUDGED_FIELDS, extract_case, normalize_field
from .llm import from_settings


def same(field: str, got, want) -> bool:
    if field == "tax" and not want:
        return not got
    if isinstance(want, (int, float)) and not isinstance(want, bool):
        return got is not None and abs(float(got) - float(want)) < 0.01
    if isinstance(want, list):
        return sorted(got or []) == sorted(want)
    if isinstance(want, bool):
        return got is want
    return N.squash(str(got or "")) == N.squash(str(want))


def score(gt: dict, run: dict) -> dict:
    want_pages = {("invoice", 1): "invoice"}
    for t, (a, b) in gt["pages"].items():
        for n in range(a, b + 1):
            want_pages[("attachment", n)] = t
    got_pages = {(p["file"], p["page"]): p for p in run["pages"]}
    page_miss = [f"{f} p{n}: 應為 {t}，判成 {got_pages.get((f, n), {}).get('type')}"
                 for (f, n), t in want_pages.items() if got_pages.get((f, n), {}).get("type") != t]
    fields, field_miss = [], []
    for doc, want in gt["extraction"].items():
        got = run["documents"].get(doc, {}).get("fields", {})
        for name, w in want.items():
            g = got.get(name, {}).get("value")
            ok = same(name, g, w)
            fields.append((doc, name, ok))
            if not ok:
                field_miss.append(f"{doc}.{name}: 應為 {w!r}，擷取 {g!r}（原文 {got.get(name, {}).get('raw')!r}）")
    unverified = sum(1 for d in run["documents"].values() for n, f in d.get("fields", {}).items()
                     if f.get("verified") is False and n not in JUDGED_FIELDS)
    return {"case": gt["case_id"], "scenario": gt["scenario"], "pages_total": len(want_pages),
            "pages_ok": len(want_pages) - len(page_miss), "fields_total": len(fields),
            "fields_ok": sum(ok for *_, ok in fields), "fields": fields, "page_miss": page_miss,
            "field_miss": field_miss, "unverified": unverified, "seconds": run["seconds"],
            "usage": run.get("usage", {})}


def report(results: list[dict], llm_name: str) -> str:
    lines = [f"# 擷取評測：{llm_name}", "",
             "| 案例 | 情境 | 分頁正確 | 欄位正確 | 證據未對上 | 秒數 | 呼叫 | 輸入 tokens | 輸出 tokens | 費用 USD |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    tp = tf = op = of = secs = 0
    tot = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    by_field = defaultdict(lambda: [0, 0])
    for r in results:
        u = r["usage"]
        for k in tot:
            tot[k] += u.get(k, 0)
        lines.append(f"| {r['case']} | {r['scenario']} | {r['pages_ok']}/{r['pages_total']} | "
                     f"{r['fields_ok']}/{r['fields_total']} | {r['unverified']} | {r['seconds']} | "
                     f"{u.get('calls', '')} | {u.get('input_tokens', '')} | {u.get('output_tokens', '')} | "
                     f"{u.get('cost_usd', 0):.4f} |")
        tp, op, tf, of, secs = (tp + r["pages_total"], op + r["pages_ok"], tf + r["fields_total"],
                                of + r["fields_ok"], secs + r["seconds"])
        for doc, name, ok in r["fields"]:
            by_field[f"{doc}.{name}"][0] += ok
            by_field[f"{doc}.{name}"][1] += 1
    lines += [f"| **合計** | | **{op}/{tp}（{op / tp:.1%}）** | **{of}/{tf}（{of / tf:.1%}）** | | "
              f"**{secs:.0f}** | {tot['calls']} | {tot['input_tokens']} | {tot['output_tokens']} | "
              f"**{tot['cost_usd']:.4f}** |", "", "## 各欄位正確率", "", "| 欄位 | 正確 |", "|---|---|"]
    for k, (ok, n) in sorted(by_field.items(), key=lambda x: x[1][0] / x[1][1]):
        if ok < n:
            lines.append(f"| {k} | {ok}/{n} |")
    lines += ["", "## 錯誤明細", ""]
    for r in results:
        for m in r["page_miss"] + r["field_miss"]:
            lines.append(f"- {r['case']} {m}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="對標準答案評測 PDF 擷取")
    ap.add_argument("workspace", type=Path)
    ap.add_argument("--gt", type=Path, default=Path("eval/ground_truth"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cases", nargs="*")
    ap.add_argument("--score-only", action="store_true", help="不重跑 LLM，只重新計分已存的結果")
    ap.add_argument("--provider", choices=["ollama", "claude"], help="覆寫設定檔的 llm.provider")
    ap.add_argument("--model", help="覆寫設定檔的模型")
    ap.add_argument("--intros", action="store_true", help="改為比較信件開頭段落（用標準答案的擷取結果）")
    args = ap.parse_args()

    ws = config.load(args.workspace)
    llm = None if args.score_only else from_settings(ws.settings, args.provider, args.model, localstore.api_key())
    if args.intros:
        args.out.mkdir(parents=True, exist_ok=True)
        md = intro_report(ws, llm, args.gt)
        (args.out / "intros.md").write_text(md, encoding="utf-8")
        print(md)
        return
    args.out.mkdir(parents=True, exist_ok=True)
    results, name = [], llm.name if llm else ""
    for gt_path in sorted(args.gt.glob("*.json")):
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        if args.cases and gt["case_id"] not in args.cases:
            continue
        run_path = args.out / f"{gt['case_id']}.json"
        if args.score_only:
            run = json.loads(run_path.read_text(encoding="utf-8"))
            for doc in run["documents"].values():
                for fname, f in doc.get("fields", {}).items():
                    f["value"] = normalize_field(fname, f["raw"], ws.settings["patterns"])
        else:
            print(f"[{gt['case_id']}] {gt['files']['attachment']}")
            inbox = ws.folder("inbox") / gt["pic"]
            before = dict(llm.usage)
            run = extract_case(inbox / gt["files"]["invoice"], inbox / gt["files"]["attachment"], llm,
                               ws.settings["patterns"])
            run["usage"] = {k: round(llm.usage[k] - before[k], 6) for k in before}
            run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
        name = run["llm"]
        r = score(gt, run)
        print(f"  分頁 {r['pages_ok']}/{r['pages_total']}  欄位 {r['fields_ok']}/{r['fields_total']}  {run['seconds']}s")
        results.append(r)
    md = report(results, name)
    (args.out / "report.md").write_text(md, encoding="utf-8")
    print(md)


def intro_report(ws, llm, gt_dir: Path) -> str:
    from . import audit, mail, reference, routing

    ref = reference.load(ws)
    rules = routing.load(ws.config_dir / ws.settings["files"]["mail_routing"])
    lines = [f"# 信件開頭段落：{llm.name}", "", "模式 all：每封信都請 LLM 寫開頭，未通過檢查會退回範本。", ""]
    before = dict(llm.usage)
    for p in sorted(gt_dir.glob("*.json")):
        gt = json.loads(p.read_text(encoding="utf-8"))
        docs = {d: {"file": "attachment", "fields": {k: {"value": v} for k, v in f.items()}}
                for d, f in gt["extraction"].items()}
        fs, ctx = audit.run(docs, ref, ws.rules)
        oc = audit.outcome(fs, ws.rules["outcome_priority"])
        pic = ref.employees[ws.settings["pics"][gt["pic"]]]
        route = routing.resolve(rules, ref, oc, [f.rule for f in fs if f.status == "fail"], ctx.vendor,
                                (ctx.sap_po or {}).get("產品線"), pic["Email"])
        d = mail.compose(outcome=oc, findings=fs, ctx=ctx, case={"pic": pic, "files": gt["files"]}, route=route,
                         form_vals=None if oc != "ready_to_sign" else {}, company=ws.settings["company"]["name"],
                         company_en=ws.settings["company"].get("name_en"), llm=llm, llm_mode="all") if oc != "ready_to_sign" else None
        if d is None:
            continue
        intro = d.html.split("<p>")[1].split("</p>")[0]
        lines += [f"## {gt['case_id']} {gt['scenario']}（{audit.OUTCOME_LABEL[oc]}，{d.lang}）", "",
                  f"- 來源：{d.intro_source}", f"- 開頭：{intro}", ""]
    u = {k: round(llm.usage[k] - before[k], 6) for k in before}
    lines.append(f"用量：{u}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
