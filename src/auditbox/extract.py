import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pymupdf

from . import normalize as N
from .llm import LLM

DOC_TYPES = ["invoice", "po", "commitment", "approval", "spec", "custody", "cost_breakdown", "photos",
             "dimension_report", "other"]
DOC_LABELS = {
    "invoice": "發票", "po": "採購單 PO", "commitment": "模具訂單承諾書", "approval": "模具承認書",
    "spec": "模具規格書", "custody": "模具保管單", "cost_breakdown": "模具費用明細表", "photos": "模具照片",
    "dimension_report": "尺寸檢測報告", "other": "其他",
}
TITLE_KEYWORDS = {
    "commitment": ["承诺书", "承諾書", "COMMITMENT LETTER"],
    "approval": ["承认书", "承認書", "APPROVAL SHEET"],
    "spec": ["规格书", "規格書", "MOLD SPECIFICATION"],
    "custody": ["保管单", "保管單", "CUSTODY AGREEMENT"],
    "cost_breakdown": ["费用明细", "費用明細", "COST BREAKDOWN"],
    "photos": ["模具照片", "MOLD PHOTOS"],
    "dimension_report": ["尺寸检测", "尺寸檢測", "DIMENSIONAL INSPECTION"],
    "invoice": ["发票", "發票", "INVOICE"],
    "po": ["採購單", "采购单", "PURCHASE ORDER"],
}
VISION_DOCS = {"approval", "commitment"}
ROLES = {"design", "qa", "me"}
JUDGED_FIELDS = {"signed_roles", "vendor_stamped"}

FIELDS = {
    "invoice": {
        "invoice_no": "發票號碼",
        "invoice_date": "發票開立日期",
        "vendor_name": "賣方／銷售方／Seller 名稱",
        "po_no": "買方採購單號（PO，常寫在備註或 Customer PO）",
        "mold_no": "模具編號（可能在品名或規格型號欄）",
        "currency": "幣別",
        "amount_untaxed": "未稅金額（銷售額合計／金額合計／TOTAL，不含稅）",
        "tax": "稅額；外銷或無稅額欄位則 null",
    },
    "po": {
        "po_no": "採購單號",
        "po_date": "訂單日期",
        "vendor_code": "供應商代號",
        "vendor_name": "供應商名稱",
        "mold_no": "模具編號",
        "currency": "幣別",
        "amount": "未稅合計金額",
    },
    "commitment": {
        "po_no": "文中提到的採購訂單號",
        "mold_no": "模具編號",
        "vendor_stamped": "供應商簽章欄是否有蓋章或簽名，填 yes 或 no",
    },
    "approval": {
        "mold_no": "模具編號",
        "po_no": "採購訂單號",
        "approval_date": "承認日期（判定結果旁的日期）",
        "result": "最終判定結果原文",
        "signed_roles": "簽核欄中『已有簽名』的角色，從 design（模具設計）、qa（品保）、me（機構工程 ME）選，"
                        "逗號分隔；簽名格空白的角色不要列入",
    },
    "spec": {
        "mold_no": "模具編號",
        "cavities": "模穴數",
        "steel": "模具鋼材",
        "shot_life": "設計壽命模次",
    },
    "custody": {
        "po_no": "採購訂單號",
        "mold_no": "模具編號",
        "storage_location": "存放地點",
        "custodian_id": "甲方（買方）保管人的工號",
    },
    "cost_breakdown": {
        "po_no": "採購訂單號",
        "mold_no": "模具編號",
        "currency": "幣別",
        "total": "合計金額",
    },
}


@dataclass
class Page:
    file: str
    number: int
    text: str
    doc: pymupdf.Document

    @property
    def scanned(self) -> bool:
        return len(self.text.strip()) < 30

    def image(self, dpi=130) -> bytes:
        return self.doc[self.number - 1].get_pixmap(dpi=dpi).tobytes("png")

    def head(self, lines=8) -> str:
        return "\n".join([l for l in self.text.splitlines() if l.strip()][:lines])


def load_pages(path: Path, file_key: str) -> list[Page]:
    doc = pymupdf.open(path)
    return [Page(file_key, i + 1, p.get_text(), doc) for i, p in enumerate(doc)]


def keyword_type(page: Page) -> str | None:
    head = page.head().upper()
    hits = []
    for t, kws in TITLE_KEYWORDS.items():
        for k in kws:
            pos = head.find(k.upper())
            if pos >= 0:
                hits.append((pos, t))
    return min(hits)[1] if hits else None


CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {"doc_type": {"type": "string", "enum": DOC_TYPES + ["continuation"]}},
    "required": ["doc_type"],
    "additionalProperties": False,
}


def classify_prompt(prev: str | None) -> str:
    opts = "\n".join(f"- {k}：{v}" for k, v in DOC_LABELS.items())
    hint = f"上一頁是「{prev}」。若本頁沒有標題、只是延續上一頁的表格或內容，回答 continuation。\n" if prev else ""
    return (f"判斷這一頁屬於哪一種模具請款文件，只回答類別代碼。\n{opts}\n{hint}"
            "判斷依據以頁面標題為主。")


def classify(pages: list[Page], llm: LLM, log: Callable[[str], None]) -> list[dict]:
    out, prev = [], None
    for p in pages:
        t, method = (None, None) if p.scanned else (keyword_type(p), "keyword")
        if t is None:
            if p.scanned:
                t, method = llm.json(classify_prompt(prev), CLASSIFY_SCHEMA, [p.image(100)])["doc_type"], "llm-vision"
            else:
                t, method = llm.json(classify_prompt(prev) + "\n頁面文字：\n" + p.text[:2500],
                                     CLASSIFY_SCHEMA)["doc_type"], "llm-text"
        if t == "continuation":
            t, method = prev or "other", method + "+continuation"
        if p.file == "invoice" and t == "other":
            t = "invoice"
        out.append({"file": p.file, "page": p.number, "type": t, "method": method})
        log(f"  {p.file} p{p.number} → {t}（{method}）")
        prev = t
    return out


def field_schema(doc_type: str) -> dict:
    item = {
        "type": "object",
        "properties": {"value": {"type": ["string", "null"]}, "page": {"type": ["integer", "null"]},
                       "quote": {"type": ["string", "null"]}},
        "required": ["value", "page", "quote"],
        "additionalProperties": False,
    }
    names = list(FIELDS[doc_type])
    return {"type": "object", "properties": {n: item for n in names}, "required": names,
            "additionalProperties": False}


def extract_prompt(doc_type: str, pages: list[Page], with_text: bool) -> str:
    fields = "\n".join(f"- {k}：{v}" for k, v in FIELDS[doc_type].items())
    body = (f"你是採購文件擷取器。以下是「{DOC_LABELS[doc_type]}」，共 {len(pages)} 頁。\n"
            "規則：\n1. 只能使用文件中出現的資訊，找不到填 null，不要猜。\n"
            "2. value 照文件原樣抄寫，不要換算或翻譯。\n3. page 填該值所在的頁碼（用下方標示的頁碼）。\n"
            "4. quote 填文件中包含該值的一小段逐字原文（10–40 字）。\n"
            f"欄位：\n{fields}\n")
    if with_text:
        body += "\n文件內容：\n" + "\n".join(f"=== 第 {p.number} 頁 ===\n{p.text}" for p in pages)
    else:
        body += "\n文件為掃描影像，頁碼依序為：" + "、".join(str(p.number) for p in pages)
    return body


def normalize_field(name: str, raw, patterns: dict):
    if raw is None or raw == "":
        return None
    if name.endswith("_date"):
        return N.iso_date(raw)
    if name in {"amount", "amount_untaxed", "tax", "total"}:
        return N.amount(raw)
    if name == "shot_life":
        return N.integer(raw)
    if name == "currency":
        return N.currency(raw)
    if name in {"po_no", "mold_no"}:
        return N.pattern(raw, patterns[name])
    if name == "custodian_id":
        return N.pattern(raw, patterns["emp_id"])
    if name == "signed_roles":
        return sorted({r.strip().lower() for r in str(raw).replace("，", ",").split(",")} & ROLES)
    if name == "result":
        s = str(raw).strip().upper()
        if any(k in s for k in ("NG", "不合格", "REJECT", "退回")):
            return "rejected"
        if any(k in s for k in ("承认", "承認", "APPROVED", "OK", "合格", "PASS")):
            return "approved"
        return N.text(str(raw))
    if name == "vendor_stamped":
        return str(raw).strip().lower() in {"yes", "true", "是", "有"}
    return N.text(str(raw))


def extract_doc(doc_type: str, pages: list[Page], llm: LLM, patterns: dict) -> dict:
    scanned = any(p.scanned for p in pages)
    images = [p.image() for p in pages[:3]] if scanned or doc_type in VISION_DOCS else None
    raw = llm.json(extract_prompt(doc_type, pages, not scanned), field_schema(doc_type), images)
    by_no = {p.number: p for p in pages}
    fields = {}
    for name in FIELDS[doc_type]:
        r = raw.get(name) or {}
        value = normalize_field(name, r.get("value"), patterns)
        page = r.get("page") if r.get("page") in by_no else None
        verified = None
        if not scanned and r.get("value") and page and name not in JUDGED_FIELDS:
            verified = N.squash(r["value"]) in N.squash(by_no[page].text)
        fields[name] = {"value": value, "raw": r.get("value"), "page": page, "quote": r.get("quote"),
                        "verified": verified}
    return {"file": pages[0].file, "pages": [p.number for p in pages], "scanned": scanned, "fields": fields}


def extract_case(invoice_pdf: Path, attachment_pdf: Path, llm: LLM, patterns: dict,
                 log: Callable[[str], None] = print) -> dict:
    t0 = time.time()
    pages = load_pages(invoice_pdf, "invoice") + load_pages(attachment_pdf, "attachment")
    labels = classify(pages, llm, log)
    groups: dict[str, list[Page]] = {}
    for p, lab in zip(pages, labels):
        groups.setdefault(lab["type"], []).append(p)
    documents = {}
    for doc_type, ps in groups.items():
        if doc_type not in FIELDS:
            documents[doc_type] = {"file": ps[0].file, "pages": [p.number for p in ps], "fields": {}}
            continue
        if len({p.file for p in ps}) > 1:
            ps = [p for p in ps if p.file == ("invoice" if doc_type == "invoice" else "attachment")]
        log(f"  擷取 {DOC_LABELS[doc_type]}（{len(ps)} 頁）")
        documents[doc_type] = extract_doc(doc_type, ps, llm, patterns)
    return {"files": {"invoice": invoice_pdf.name, "attachment": attachment_pdf.name}, "llm": llm.name,
            "pages": labels, "documents": documents, "seconds": round(time.time() - t0, 1)}
