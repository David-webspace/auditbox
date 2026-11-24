from datetime import datetime
from html import escape
from pathlib import Path

import pymupdf
from openpyxl import load_workbook

from . import zh

from .audit import Context
from .reference import as_date


def _fmt(v):
    if isinstance(v, float):
        return f"{v:,.2f}"
    d = as_date(v) if isinstance(v, str) and len(v) == 10 and v[4] in "-/" else None
    return d.replace("-", "/") if d else ("" if v is None else str(v))


def values(form_map: dict, ctx: Context, docs: dict, pic: dict, now: datetime) -> dict:
    src = {
        "pic": {"name": pic["姓名"], "dept": pic["部門"]},
        "vendor": {"name_local": ctx.vendor.name_local, "code": ctx.vendor.code} if ctx.vendor else {},
        "sap_po": ctx.sap_po or {},
        "sap_gr": ctx.gr or {},
        "employee": ctx.custodian or {},
    }
    out = {}
    for label, (_, source) in form_map.items():
        if source == "auto":
            v = f"MA-{now:%Y%m%d}-{(ctx.po_no or '0000')[-4:]}"
        elif source == "today":
            v = now.strftime("%Y/%m/%d")
        elif source.startswith("const."):
            v = source.split(".", 1)[1]
        elif source.startswith("doc."):
            _, doc, fname = source.split(".")
            v = docs.get(doc, {}).get("fields", {}).get(fname, {}).get("value")
        else:
            group, key = source.split(".", 1)
            v = src[group].get(key)
        out[label] = _fmt(v)
    return zh.deep(out)


def write_xlsx(template: Path, form_map: dict, vals: dict, out: Path) -> Path:
    wb = load_workbook(template)
    ws = wb.active
    for label, (cell, _) in form_map.items():
        ws[cell] = vals[label]
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


NAVY = (0.12, 0.23, 0.37)


def _cell(page, rect, text, size=10, color="#000", align="left"):
    page.insert_htmlbox(rect + (5, 4, -5, -2),
                        f"<div style='font-size:{size}px;color:{color};text-align:{align}'>{escape(text)}</div>")


def render_pdf(company: str, form_map: dict, vals: dict) -> bytes:
    rows: dict[int, dict] = {}
    for label, (cell, _) in form_map.items():
        rows.setdefault(int(cell[1:]), {})[cell[0]] = label
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    _cell(page, pymupdf.Rect(48, 40, 547, 60), company, 12, align="center")
    _cell(page, pymupdf.Rect(48, 60, 547, 86), "固定資產驗收單（模具）", 16, align="center")
    x = [48, 128, 298, 378, 547]
    y = 100
    for r in sorted(rows):
        h = 34 if any(len(vals[l]) > 26 for l in rows[r].values()) else 24
        cols = [(0, rows[r]["B"])] + ([(2, rows[r]["D"])] if "D" in rows[r] else [])
        for i, label in cols:
            right = x[i + 2] if len(cols) == 2 else x[4]
            page.draw_rect(pymupdf.Rect(x[i], y, x[i + 1], y + h), color=(0.5, 0.5, 0.5), fill=NAVY, width=0.5)
            page.draw_rect(pymupdf.Rect(x[i + 1], y, right, y + h), color=(0.5, 0.5, 0.5), width=0.5)
            _cell(page, pymupdf.Rect(x[i], y, x[i + 1], y + h), label, 9.5, "#fff")
            _cell(page, pymupdf.Rect(x[i + 1], y, right, y + h), vals[label], 9.5)
        y += h
    y += 18
    for i, title in enumerate(["申請人", "單位主管", "資產管理", "財務"]):
        rx = 48 + i * 124.75
        page.draw_rect(pymupdf.Rect(rx, y, rx + 124.75, y + 20), color=(0.5, 0.5, 0.5), fill=NAVY, width=0.5)
        page.draw_rect(pymupdf.Rect(rx, y + 20, rx + 124.75, y + 80), color=(0.5, 0.5, 0.5), width=0.5)
        _cell(page, pymupdf.Rect(rx, y, rx + 124.75, y + 20), title, 9.5, "#fff", "center")
    _cell(page, pymupdf.Rect(48, y + 88, 547, y + 104), "本單由系統依廠商文件與 SAP 資料預填，送簽前請承辦確認。", 8, "#777")
    return doc.tobytes()


def merge(parts: list[bytes | Path], out: Path) -> Path:
    doc = pymupdf.open()
    for p in parts:
        src = pymupdf.open(p) if isinstance(p, Path) else pymupdf.open(stream=p, filetype="pdf")
        doc.insert_pdf(src)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out, garbage=3, deflate=True)
    return out
