from auditbox import zh
import json
import os
import random
import time
from datetime import datetime
from pathlib import Path

import pymupdf

from . import excel, pdfs
from .data import CASES, EMP_BY_ID, PICS, Case

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demo"
GT = ROOT / "eval" / "ground_truth"
REQUIRED = ["po", "commitment", "approval", "spec", "custody", "cost_breakdown"]


def build_attachment(c: Case, rng: random.Random):
    docs = {
        "po": pdfs.doc_po(c),
        "commitment": pdfs.doc_commitment(c),
        "approval": pdfs.doc_approval(c),
        "spec": pdfs.doc_spec(c, rng),
        "custody": pdfs.doc_custody(c),
        "cost_breakdown": pdfs.doc_cost(c, rng),
    }
    photo_n = max(1, c.extra_pages * 2 // 3)
    dim_n = max(1, c.extra_pages - photo_n)
    docs["photos"] = pdfs.doc_photos(c, photo_n, rng)
    docs["dimension_report"] = pdfs.doc_dims(c, dim_n, rng)
    for d in c.overrides.get("drop_docs", []):
        docs.pop(d)
    rest = [k for k in docs if k != "po"]
    rng.shuffle(rest)
    order = ["po"] + rest
    out, pages, cursor = pymupdf.open(), {}, 1
    for k in order:
        src = pymupdf.open(stream=docs[k], filetype="pdf")
        pages[k] = [cursor, cursor + len(src) - 1]
        cursor += len(src)
        out.insert_pdf(src)
    return out.tobytes(garbage=3, deflate=True), pages


def ground_truth(c: Case, pages: dict, files: dict):
    v, cust, pic = c.vendor, EMP_BY_ID[c.custodian], EMP_BY_ID[PICS[c.pic]]
    inv_cur = c.overrides.get("invoice_currency", v.currency)
    inv_amt = c.overrides.get("invoice_amount", c.amount)
    if v.country == "TW":
        inv_name, tax = v.name_local, round(inv_amt * v.tax_rate)
    elif v.tax_rate > 0 and inv_cur == "RMB":
        inv_name, tax = v.name_local, round(inv_amt * v.tax_rate, 2)
    else:
        inv_name, tax = c.overrides.get("vendor_display_en", v.name_en), 0
    unsigned = set(c.overrides.get("unsigned_roles", []))
    extraction = {
        "invoice": {"invoice_no": c.invoice_no, "invoice_date": c.invoice_date.isoformat(), "vendor_name": inv_name,
                    "po_no": c.po_no, "mold_no": c.mold_no, "currency": inv_cur, "amount_untaxed": inv_amt,
                    "tax": tax},
        "po": {"po_no": c.po_no, "po_date": c.po_date.isoformat(), "vendor_code": v.code,
               "vendor_name": v.name_local, "mold_no": c.mold_no, "currency": v.currency, "amount": c.amount},
        "commitment": {"po_no": c.overrides.get("commitment_po", c.po_no), "mold_no": c.mold_no,
                       "vendor_stamped": True},
        "approval": {"mold_no": c.mold_no, "po_no": c.po_no, "approval_date": c.approval_date.isoformat(),
                     "result": "approved", "signed_roles": [r for r in ("design", "qa", "me") if r not in unsigned]},
        "spec": {"mold_no": c.mold_no, "cavities": c.cavities, "steel": c.steel, "shot_life": c.shot_life},
        "custody": {"po_no": c.po_no, "mold_no": c.mold_no, "storage_location": c.storage,
                    "custodian_id": cust.emp_id},
        "cost_breakdown": {"po_no": c.po_no, "mold_no": c.mold_no, "currency": v.currency, "total": c.amount},
    }
    for d in c.overrides.get("drop_docs", []):
        extraction.pop(d)
    form = {
        "申請人": pic.name, "部門": pic.dept, "廠商名稱": v.name_local, "廠商代號": v.code, "PO 號": c.po_no,
        "PO 項次": "10", "GR 號": c.gr_no or "", "收貨日期": c.gr_date.isoformat() if c.gr_date else "",
        "驗收日期": c.approval_date.isoformat(), "資產類別": "模具", "品名": c.item_zh, "模具編號": c.mold_no,
        "模穴數": c.cavities, "數量": 1, "單位": "SET", "幣別": v.currency, "未稅總價": c.amount,
        "存放地點": c.storage if "custody" in extraction else "", "保管人工號": cust.emp_id if "custody" in extraction else "",
        "保管人姓名": cust.name if "custody" in extraction else "",
    }
    return {
        "case_id": c.case_id, "pic": c.pic, "scenario": c.anomaly, "scanned": c.scanned, "files": files,
        "pages": pages, "extraction": extraction, "expected_issues": c.expect_issues,
        "expected_outcome": c.expect_outcome, "acceptance_form": zh.deep(form),
    }


def main():
    pdfs.register_font()
    rng = random.Random(20261124)
    for d in ["00_設定", "01_待處理", "02_驗收單", "03_已處理", "04_人工處理", "05_系統匯出", "Logs"]:
        (DEMO / d).mkdir(parents=True, exist_ok=True)
    GT.mkdir(parents=True, exist_ok=True)

    excel.vendor_master(DEMO / "00_設定" / "模具廠商主檔表_策購維護.xlsx")
    excel.mail_routing(DEMO / "00_設定" / "寄信對照表.xlsx")
    excel.acceptance_template(DEMO / "00_設定" / "資產驗收單範本.xlsx")
    excel.sap_exports(DEMO / "05_系統匯出", rng)

    for c in CASES:
        inbox = DEMO / "01_待處理" / c.pic
        inbox.mkdir(exist_ok=True)
        base = f"{c.vendor.short}{c.file_ref}"
        attachment, pages = build_attachment(c, rng)
        invoice = pdfs.doc_invoice(c)
        if c.scanned:
            attachment, invoice = pdfs.scan(attachment, rng), pdfs.scan(invoice, rng)
        files = {"invoice": f"{base} IV.pdf", "attachment": f"{base}.pdf"}
        stamp = time.mktime(datetime(2026, 11, 20, 9, 0).timetuple()) + rng.randint(0, 3 * 86400)
        for name, data in ((files["invoice"], invoice), (files["attachment"], attachment)):
            (inbox / name).write_bytes(data)
            os.utime(inbox / name, (stamp, stamp))
        (GT / f"{c.case_id}.json").write_text(
            json.dumps(ground_truth(c, pages, files), ensure_ascii=False, indent=2), encoding="utf-8")
        total = sum(p[1] - p[0] + 1 for p in pages.values())
        print(f"{c.case_id} {c.pic:<6} {base:<14} {total:>2} 頁  {c.anomaly}")


if __name__ == "__main__":
    main()
