import io
import os
import random
from pathlib import Path

import pymupdf
from PIL import Image, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .data import COMPANY, EMP_BY_ID, Case

FONT_CANDIDATES = [
    os.environ.get("AUDITBOX_CJK_FONT", ""),
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msjh.ttc",
]


def register_font():
    for p in FONT_CANDIDATES:
        if p and Path(p).exists():
            pdfmetrics.registerFont(TTFont("CJK", p, subfontIndex=0))
            return
    raise SystemExit("找不到中文字型，請設定 AUDITBOX_CJK_FONT 指向 .ttf/.ttc")


def S(size=9.5, lead=None, align=0, color=colors.black):
    return ParagraphStyle("s", fontName="CJK", fontSize=size, leading=lead or size * 1.45, alignment=align,
                          textColor=color)


T = {
    "zh-CN": dict(
        commitment="模具订单承诺书", approval="模具承认书", spec="模具规格书", custody="模具保管单",
        cost="模具费用明细表", photo="模具照片", dim="产品尺寸检测报告", po_no="采购订单号", mold_no="模具编号",
        part_no="产品料号", item="产品名称", cav="模穴数", steel="模具钢材", life="设计寿命（模次）",
        owner="资产所有人", location="存放地点", custodian="甲方保管人", vendor_keeper="乙方保管责任人",
        date="日期", sign="签章", total="合计", currency="币别", amount="金额", trial="试模记录",
        result="判定", approved="承认", roles={"design": "模具设计", "qa": "品保", "me": "机构工程（ME）"},
        signer="签核人", stage="阶段", note="备注", seq="序号", cost_item="费用项目", vendor="供应商",
        commit_body=[
            "本公司（以下简称乙方）承接{buyer}（以下简称甲方）采购订单 {po} 所列模具（模具编号 {mold}），特此承诺如下：",
            "一、该模具所有权自甲方付清模具款项之日起归甲方所有，乙方仅为保管人。",
            "二、模具设计寿命不低于 {life} 模次，于寿命期内因模具本身造成之损坏，由乙方负责免费维修。",
            "三、未经甲方书面同意，乙方不得将模具转移、出借、抵押或用于第三方产品之生产。",
            "四、甲方要求返还模具时，乙方应于 15 个工作日内配合办理，不得以任何理由留置。",
            "五、乙方应每年配合甲方进行模具盘点，并提供模具使用模次记录。",
        ],
        custody_body=[
            "一、乙方应妥善保管上述模具，避免锈蚀、碰撞及非授权使用。",
            "二、模具如有维修、改模或移转存放地点，应事先以书面通知甲方并取得同意。",
            "三、本保管单与采购订单具同等效力，保管期间至甲方书面通知终止为止。",
        ],
    ),
    "zh-TW": dict(
        commitment="模具訂單承諾書", approval="模具承認書", spec="模具規格書", custody="模具保管單",
        cost="模具費用明細表", photo="模具照片", dim="產品尺寸檢測報告", po_no="採購訂單號", mold_no="模具編號",
        part_no="產品料號", item="產品名稱", cav="模穴數", steel="模具鋼材", life="設計壽命（模次）",
        owner="資產所有人", location="存放地點", custodian="甲方保管人", vendor_keeper="乙方保管責任人",
        date="日期", sign="簽章", total="合計", currency="幣別", amount="金額", trial="試模紀錄",
        result="判定", approved="承認", roles={"design": "模具設計", "qa": "品保", "me": "機構工程（ME）"},
        signer="簽核人", stage="階段", note="備註", seq="序號", cost_item="費用項目", vendor="供應商",
        commit_body=[
            "本公司（以下簡稱乙方）承接{buyer}（以下簡稱甲方）採購訂單 {po} 所列模具（模具編號 {mold}），特此承諾如下：",
            "一、該模具所有權自甲方付清模具款項之日起歸甲方所有，乙方僅為保管人。",
            "二、模具設計壽命不低於 {life} 模次，於壽命期內因模具本身造成之損壞，由乙方負責免費維修。",
            "三、未經甲方書面同意，乙方不得將模具轉移、出借、抵押或用於第三方產品之生產。",
            "四、甲方要求返還模具時，乙方應於 15 個工作日內配合辦理，不得以任何理由留置。",
            "五、乙方應每年配合甲方進行模具盤點，並提供模具使用模次紀錄。",
        ],
        custody_body=[
            "一、乙方應妥善保管上述模具，避免鏽蝕、碰撞及非授權使用。",
            "二、模具如有維修、改模或移轉存放地點，應事先以書面通知甲方並取得同意。",
            "三、本保管單與採購訂單具同等效力，保管期間至甲方書面通知終止為止。",
        ],
    ),
    "en": dict(
        commitment="TOOLING ORDER COMMITMENT LETTER", approval="MOLD APPROVAL SHEET", spec="MOLD SPECIFICATION",
        custody="TOOLING CUSTODY AGREEMENT", cost="TOOLING COST BREAKDOWN", photo="MOLD PHOTOS",
        dim="DIMENSIONAL INSPECTION REPORT", po_no="PO No.", mold_no="Mold No.", part_no="Part No.",
        item="Description", cav="Cavities", steel="Steel", life="Design Life (shots)", owner="Asset Owner",
        location="Storage Location", custodian="Buyer Custodian", vendor_keeper="Supplier Keeper", date="Date",
        sign="Signature", total="Total", currency="Currency", amount="Amount", trial="Trial Records",
        result="Result", approved="APPROVED", roles={"design": "Mold Design", "qa": "QA", "me": "ME"},
        signer="Signed by", stage="Stage", note="Remark", seq="No.", cost_item="Cost Item", vendor="Supplier",
        commit_body=[
            "We (the Supplier) hereby confirm acceptance of {buyer} (the Buyer) purchase order {po} for mold {mold} and commit to:",
            "1. Title to the mold passes to the Buyer upon full payment; the Supplier acts as custodian only.",
            "2. The mold is designed for no less than {life} shots; failures within design life are repaired free of charge.",
            "3. The mold shall not be moved, lent, pledged or used for third-party production without written consent.",
            "4. Upon request, the mold shall be returned to the Buyer within 15 working days.",
            "5. The Supplier shall support annual tooling audits and provide shot-count records.",
        ],
        custody_body=[
            "1. The Supplier shall keep the mold properly protected against rust, damage and unauthorized use.",
            "2. Any repair, modification or relocation requires prior written approval from the Buyer.",
            "3. This agreement remains valid until terminated in writing by the Buyer.",
        ],
    ),
}


def money(v: float, cur: str) -> str:
    return f"{cur} {v:,.2f}"


class Stamp(Flowable):
    def __init__(self, text, size=30 * mm, color=colors.Color(0.85, 0.1, 0.1, alpha=0.8)):
        super().__init__()
        self.text, self.size, self.color = text, size, color
        self.width = self.height = size

    def draw(self):
        c, r = self.canv, self.size / 2
        c.saveState()
        c.setStrokeColor(self.color)
        c.setFillColor(self.color)
        c.setLineWidth(2)
        c.translate(r, r)
        c.rotate(-8)
        c.circle(0, 0, r - 2)
        c.setFont("CJK", 12)
        c.drawCentredString(0, -4, "★")
        c.setFont("CJK", 6.5)
        c.drawCentredString(0, r * 0.45, self.text[:14])
        c.drawCentredString(0, -r * 0.6, "合同专用章" if any("\u4e00" <= ch <= "\u9fff" for ch in self.text) else "COMPANY SEAL")
        c.restoreState()


class Signature(Flowable):
    def __init__(self, name, when=""):
        super().__init__()
        self.name, self.when = name, when
        self.width, self.height = 40 * mm, 12 * mm

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFillColor(colors.Color(0.1, 0.15, 0.6))
        c.translate(2 * mm, 4 * mm)
        c.rotate(6)
        c.setFont("CJK", 13)
        c.drawString(0, 0, self.name)
        c.restoreState()
        if self.when:
            c.setFont("CJK", 7)
            c.drawString(2 * mm, 0, self.when)


def grid(rows, widths, header=True, size=8.5):
    data = [[Paragraph(str(x), S(size)) if not isinstance(x, Flowable) else x for x in r] for r in rows]
    t = Table(data, colWidths=widths)
    style = [("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.9, 0.92, 0.95)))
    t.setStyle(TableStyle(style))
    return t


def kv(pairs, w=(38 * mm, 52 * mm, 38 * mm, 52 * mm)):
    rows = []
    for i in range(0, len(pairs), 2):
        a = pairs[i]
        b = pairs[i + 1] if i + 1 < len(pairs) else ("", "")
        rows.append([a[0], a[1], b[0], b[1]])
    t = grid(rows, w, header=False)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.Color(0.93, 0.93, 0.93)),
                           ("BACKGROUND", (2, 0), (2, -1), colors.Color(0.93, 0.93, 0.93))]))
    return t


def letterhead(name_local, name_en, addr):
    out = [Paragraph(name_local, S(13, align=1))]
    if name_en != name_local:
        out.append(Paragraph(name_en, S(9, align=1)))
    out.append(Paragraph(addr, S(7.5, align=1, color=colors.grey)))
    out.append(Spacer(1, 4 * mm))
    return out


def title(text):
    return [Paragraph(text, S(15, align=1)), Spacer(1, 5 * mm)]


def build(flows) -> bytes:
    buf = io.BytesIO()

    def footer(canv, doc):
        canv.setFont("CJK", 7)
        canv.setFillColor(colors.grey)
        canv.drawRightString(A4[0] - 15 * mm, 10 * mm, f"- {doc.page} -")

    SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm,
                      bottomMargin=16 * mm).build(flows, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def _vendor_head(c: Case):
    v = c.vendor
    return letterhead(v.name_local, c.overrides.get("vendor_display_en", v.name_en), v.address)


def doc_po(c: Case) -> bytes:
    v, pic = c.vendor, EMP_BY_ID[{"Amber": "K10231", "Kevin": "K10418", "Ming": "K10552"}[c.pic]]
    unit = c.amount
    f = letterhead(COMPANY["name_zh"], COMPANY["name_en"], COMPANY["address_zh"])
    f += title("採購單 PURCHASE ORDER")
    f.append(kv([("採購單號 PO No.", c.po_no), ("訂單日期 Date", c.po_date.strftime("%Y/%m/%d")),
                 ("供應商代號 Vendor", v.code), ("供應商 Supplier", v.name_local),
                 ("幣別 Currency", v.currency), ("付款條件 Terms", v.payment_terms),
                 ("採購員 Buyer", f"{pic.name} {pic.name_en}"), ("交貨地點 Ship to", "模具存放於供應商廠內")]))
    f.append(Spacer(1, 5 * mm))
    f.append(grid([["項次", "料號", "品名 / 規格", "模具編號", "數量", "單價", "金額"],
                   ["10", "Z1-" + c.mold_no[-6:], f"{c.item_zh}<br/>{c.item_en}", c.mold_no, "1 SET",
                    f"{unit:,.2f}", f"{unit:,.2f}"],
                   ["", "", "", "", "", "未稅合計", money(c.amount, v.currency)]],
                  [12 * mm, 24 * mm, 62 * mm, 26 * mm, 14 * mm, 20 * mm, 20 * mm]))
    f.append(Spacer(1, 6 * mm))
    for line in ["1. 本模具為本公司固定資產，所有權歸屬本公司，供應商僅負保管責任。",
                 "2. 模具驗收以本公司承認書簽核完成為準，請款時須檢附：發票、模具訂單承諾書、模具承認書、"
                 "模具規格書、模具保管單、費用明細表。",
                 "3. 發票請註明本採購單號，未註明者本公司得退回。",
                 "4. 本採購單未稅金額即為模具總價，不另計試模、運費及設計費。"]:
        f.append(Paragraph(line, S(8.5)))
    f.append(Spacer(1, 10 * mm))
    f.append(grid([["採購", "採購主管", "供應商回簽"],
                   [Signature(pic.name), Signature("張書豪" if v.sourcing_owner == "K20117" else "李佩珊"), Stamp(v.name_local)]],
                  [58 * mm] * 3))
    return build(f)


def doc_invoice(c: Case) -> bytes:
    v = c.vendor
    cur = c.overrides.get("invoice_currency", v.currency)
    amt = c.overrides.get("invoice_amount", c.amount)
    name_en = c.overrides.get("vendor_display_en", v.name_en)
    if v.country == "TW":
        tax = round(amt * v.tax_rate)
        f = title("電子發票證明聯")
        f.append(kv([("發票號碼", c.invoice_no), ("開立日期", c.invoice_date.strftime("%Y-%m-%d")),
                     ("賣方", v.name_local), ("賣方統編", v.tax_no),
                     ("買方", COMPANY["name_zh"]), ("買方統編", COMPANY["tax_id"])]))
        f.append(Spacer(1, 5 * mm))
        f.append(grid([["品名", "數量", "單價", "金額"],
                       [f"{c.item_zh}（{c.mold_no}）", "1", f"{amt:,.0f}", f"{amt:,.0f}"],
                       ["銷售額合計", "", "", f"{amt:,.0f}"], ["營業稅（5%）", "", "", f"{tax:,.0f}"],
                       ["總計", "", "", f"{amt + tax:,.0f}"]], [92 * mm, 20 * mm, 32 * mm, 34 * mm]))
        f.append(Spacer(1, 4 * mm))
        f.append(Paragraph(f"備註：PO {c.po_no}　幣別：新台幣 {cur}", S(9)))
        f.append(Spacer(1, 8 * mm))
        f.append(Stamp(v.name_local))
        return build(f)
    if v.tax_rate > 0 and cur == "RMB":
        tax = round(amt * v.tax_rate, 2)
        f = title("增值税专用发票")
        f.append(kv([("发票号码", c.invoice_no), ("开票日期", c.invoice_date.strftime("%Y年%m月%d日")),
                     ("购买方名称", COMPANY["name_zh"]), ("购买方纳税人识别号", COMPANY["tax_id"]),
                     ("销售方名称", v.name_local), ("销售方纳税人识别号", v.tax_no)]))
        f.append(Spacer(1, 5 * mm))
        f.append(grid([["项目名称", "规格型号", "单位", "数量", "单价", "金额", "税率", "税额"],
                       [f"*模具*{c.item_zh}", c.mold_no, "套", "1", f"{amt:,.2f}", f"{amt:,.2f}",
                        f"{int(v.tax_rate * 100)}%", f"{tax:,.2f}"],
                       ["合计", "", "", "", "", f"¥{amt:,.2f}", "", f"¥{tax:,.2f}"],
                       ["价税合计（小写）", "", "", "", "", f"¥{amt + tax:,.2f}", "", ""]],
                      [44 * mm, 26 * mm, 10 * mm, 10 * mm, 22 * mm, 24 * mm, 12 * mm, 22 * mm]))
        f.append(Spacer(1, 4 * mm))
        f.append(Paragraph(f"备注：PO {c.po_no}　币别：人民币 RMB", S(9)))
        f.append(Spacer(1, 8 * mm))
        f.append(Stamp(v.name_local))
        return build(f)
    f = letterhead(v.name_local, name_en, v.address)
    f += title("COMMERCIAL INVOICE")
    f.append(kv([("Invoice No.", c.invoice_no), ("Invoice Date", c.invoice_date.strftime("%d %b %Y")),
                 ("Seller", name_en), ("Buyer", COMPANY["name_en"]),
                 ("Customer PO", c.po_no), ("Payment Terms", v.payment_terms),
                 ("Currency", cur), ("Incoterms", "EXW (tooling kept at supplier)")]))
    f.append(Spacer(1, 5 * mm))
    f.append(grid([["Item", "Description", "Mold No.", "Qty", "Unit Price", "Amount"],
                   ["1", c.item_en, c.mold_no, "1 SET", f"{amt:,.2f}", f"{amt:,.2f}"],
                   ["", "", "", "", "TOTAL", money(amt, cur)]],
                  [12 * mm, 70 * mm, 28 * mm, 16 * mm, 24 * mm, 28 * mm]))
    f.append(Spacer(1, 5 * mm))
    f.append(Paragraph("Bank: (on file with buyer's AP)  /  Tax: zero-rated export of tooling", S(8)))
    f.append(Spacer(1, 10 * mm))
    f.append(Paragraph("Authorized Signature", S(8)))
    f.append(Stamp(v.name_local))
    return build(f)


def doc_commitment(c: Case) -> bytes:
    v, L = c.vendor, T[c.vendor.lang]
    po = c.overrides.get("commitment_po", c.po_no)
    buyer = COMPANY["name_en"] if v.lang == "en" else COMPANY["name_zh"]
    f = _vendor_head(c) + title(L["commitment"])
    for i, line in enumerate(L["commit_body"]):
        f.append(Paragraph(line.format(buyer=buyer, po=po, mold=c.mold_no, life=f"{c.shot_life:,}"), S(10)))
        f.append(Spacer(1, 2.5 * mm if i else 4 * mm))
    f.append(Spacer(1, 6 * mm))
    f.append(kv([(L["po_no"], po), (L["mold_no"], c.mold_no), (L["item"], c.item_zh if v.lang != "en" else c.item_en),
                 (L["cav"], c.cavities)]))
    f.append(Spacer(1, 12 * mm))
    f.append(grid([[f"{L['vendor']} {L['sign']}", L["date"]],
                   [Stamp(v.name_local), (c.po_date.replace(day=min(c.po_date.day + 3, 28))).strftime("%Y-%m-%d")]],
                  [90 * mm, 60 * mm], header=False))
    return build(f)


def approval_signers(c: Case):
    me = EMP_BY_ID[c.custodian] if EMP_BY_ID[c.custodian].dept == "機構工程部" else EMP_BY_ID["K30187"]
    return {"design": c.vendor.contact, "qa": "楊雅雯" if c.vendor.lang != "en" else "Yawen Yang",
            "me": me.name if c.vendor.lang != "en" else me.name_en}


def doc_approval(c: Case) -> bytes:
    v, L = c.vendor, T[c.vendor.lang]
    unsigned = set(c.overrides.get("unsigned_roles", []))
    f = _vendor_head(c) + title(L["approval"])
    f.append(kv([(L["mold_no"], c.mold_no), (L["part_no"], c.part_no),
                 (L["item"], c.item_zh if v.lang != "en" else c.item_en), (L["cav"], c.cavities),
                 (L["po_no"], c.po_no), (L["steel"], c.steel)]))
    f.append(Spacer(1, 5 * mm))
    f.append(Paragraph(L["trial"], S(10)))
    d = c.approval_date
    from datetime import timedelta
    f.append(grid([[L["stage"], L["date"], L["result"], L["note"]],
                   ["T0", (d - timedelta(days=34)).isoformat(), "NG", "缩水 / sink mark"],
                   ["T1", (d - timedelta(days=19)).isoformat(), "NG", "尺寸修正 / dimension fix"],
                   ["T2", (d - timedelta(days=6)).isoformat(), "OK", "-"]],
                  [24 * mm, 40 * mm, 30 * mm, 84 * mm]))
    f.append(Spacer(1, 6 * mm))
    f.append(Paragraph(f"{L['result']}：{L['approved']}　　{L['date']}：{d.isoformat()}", S(11)))
    f.append(Spacer(1, 6 * mm))
    signers = approval_signers(c)
    rows = [[L["signer"], L["sign"], L["date"]]]
    for role in ("design", "qa", "me"):
        if role in unsigned:
            rows.append([L["roles"][role], "", ""])
        else:
            rows.append([L["roles"][role], Signature(signers[role]), d.isoformat()])
    t = grid(rows, [50 * mm, 70 * mm, 50 * mm])
    t.setStyle(TableStyle([("ROWHEIGHT", (0, 1), (-1, -1), 16 * mm)]))
    f.append(t)
    return build(f)


def doc_spec(c: Case, rng: random.Random) -> bytes:
    v, L = c.vendor, T[c.vendor.lang]
    f = _vendor_head(c) + title(L["spec"])
    tons = {"射出模": rng.choice([120, 150, 180, 220]), "壓鑄模": rng.choice([280, 400, 500]),
            "沖壓模": rng.choice([80, 110, 160])}[c.mold_type]
    rows = [[L["mold_no"], c.mold_no], [L["part_no"], c.part_no],
            [L["item"], c.item_zh if v.lang != "en" else c.item_en], [L["cav"], c.cavities],
            [L["steel"], c.steel], ["Mold base", f"LKM CI-{rng.choice([2025, 2530, 3035, 3540])}"],
            ["Gate / Runner", rng.choice(["Pin point gate", "Hot runner 2-drop", "Side gate", "N/A"])],
            ["Mold size (mm)", f"{rng.randint(250, 450)} x {rng.randint(250, 500)} x {rng.randint(280, 420)}"],
            ["Mold weight (kg)", str(rng.randint(180, 950))], [L["life"], f"{c.shot_life:,}"],
            ["Cycle time (s)", str(rng.randint(18, 45))], ["Machine (ton)", str(tons)],
            ["Surface", rng.choice(["VDI 24", "SPI A2", "MT-11010", "Bead blast"])]]
    f.append(grid(rows, [60 * mm, 118 * mm], header=False))
    f.append(Spacer(1, 4 * mm))
    f.append(_Drawing(c.mold_no, rng))
    return build(f)


class _Drawing(Flowable):
    def __init__(self, label, rng):
        super().__init__()
        self.label, self.rng = label, rng
        self.width, self.height = 178 * mm, 95 * mm

    def draw(self):
        c, r = self.canv, self.rng
        c.setStrokeColor(colors.grey)
        c.rect(0, 0, self.width, self.height)
        c.setStrokeColor(colors.black)
        for _ in range(3):
            x, y = r.uniform(10, 90) * mm, r.uniform(10, 40) * mm
            c.rect(x, y, r.uniform(30, 70) * mm, r.uniform(20, 45) * mm)
            c.circle(x + 15 * mm, y + 12 * mm, r.uniform(3, 8) * mm)
        c.setFont("CJK", 7)
        c.drawString(4 * mm, 4 * mm, f"DWG {self.label}  SCALE 1:2  UNIT mm")


def doc_custody(c: Case) -> bytes:
    v, L = c.vendor, T[c.vendor.lang]
    e = EMP_BY_ID[c.custodian]
    f = _vendor_head(c) + title(L["custody"])
    f.append(kv([(L["owner"], COMPANY["name_zh"] if v.lang != "en" else COMPANY["name_en"]), (L["po_no"], c.po_no),
                 (L["mold_no"], c.mold_no), (L["item"], c.item_zh if v.lang != "en" else c.item_en),
                 (L["location"], c.storage), ("Qty", "1 SET"),
                 (L["custodian"], f"{e.name if v.lang != 'en' else e.name_en}（{e.emp_id}）"),
                 (L["vendor_keeper"], v.contact)]))
    f.append(Spacer(1, 6 * mm))
    for line in L["custody_body"]:
        f.append(Paragraph(line, S(10)))
        f.append(Spacer(1, 2 * mm))
    f.append(Spacer(1, 10 * mm))
    f.append(grid([[f"{L['custodian']} {L['sign']}", f"{L['vendor']} {L['sign']}", L["date"]],
                   [Signature(e.name if v.lang != "en" else e.name_en), Stamp(v.name_local),
                    c.approval_date.isoformat()]], [60 * mm, 70 * mm, 48 * mm]))
    return build(f)


def cost_lines(c: Case, rng: random.Random):
    names = {"zh-CN": ["模架", "模仁钢材", "CNC 加工", "放电加工 EDM", "线切割", "热处理", "抛光 / 咬花", "热流道 / 镶件",
                       "模具设计费", "试模费", "管理费及利润"],
             "zh-TW": ["模座", "模仁鋼材", "CNC 加工", "放電加工 EDM", "線切割", "熱處理", "拋光 / 咬花", "熱流道 / 入子",
                       "模具設計費", "試模費", "管理費及利潤"],
             "en": ["Mold base", "Core/cavity steel", "CNC machining", "EDM", "Wire cut", "Heat treatment",
                    "Polishing / texture", "Hot runner / inserts", "Design", "Trial", "Overhead & profit"]}[c.vendor.lang]
    weights = [rng.uniform(0.6, 1.4) * w for w in [10, 14, 18, 12, 6, 4, 5, 9, 7, 5, 10]]
    total = sum(weights)
    dec = 0 if c.vendor.currency == "TWD" else 2
    vals = [round(c.amount * w / total, dec) for w in weights]
    vals[-1] = round(c.amount - sum(vals[:-1]), dec)
    return list(zip(names, vals))


def doc_cost(c: Case, rng: random.Random) -> bytes:
    v, L = c.vendor, T[c.vendor.lang]
    f = _vendor_head(c) + title(L["cost"])
    f.append(kv([(L["po_no"], c.po_no), (L["mold_no"], c.mold_no), (L["currency"], v.currency), (L["cav"], c.cavities)]))
    f.append(Spacer(1, 5 * mm))
    rows = [[L["seq"], L["cost_item"], L["amount"]]]
    for i, (n, val) in enumerate(cost_lines(c, rng), 1):
        rows.append([str(i), n, f"{val:,.2f}"])
    rows.append(["", L["total"], money(c.amount, v.currency)])
    f.append(grid(rows, [16 * mm, 100 * mm, 62 * mm]))
    f.append(Spacer(1, 10 * mm))
    f.append(Stamp(v.name_local))
    return build(f)


class _Photo(Flowable):
    def __init__(self, rng, caption):
        super().__init__()
        self.rng, self.caption = rng, caption
        self.width, self.height = 178 * mm, 105 * mm

    def draw(self):
        c, r = self.canv, self.rng
        g = r.uniform(0.35, 0.6)
        c.setFillColor(colors.Color(g, g, g + 0.03))
        c.rect(0, 8 * mm, self.width, self.height - 8 * mm, fill=1, stroke=0)
        for _ in range(r.randint(4, 9)):
            s = r.uniform(0.55, 0.85)
            c.setFillColor(colors.Color(s, s, s))
            c.rect(r.uniform(5, 120) * mm, r.uniform(12, 70) * mm, r.uniform(15, 50) * mm, r.uniform(10, 30) * mm,
                   fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("CJK", 8)
        c.drawString(0, 2 * mm, self.caption)


def doc_photos(c: Case, n: int, rng: random.Random) -> bytes:
    L = T[c.vendor.lang]
    caps = ["定模侧 / Cavity side", "动模侧 / Core side", "模具铭牌 / Nameplate", "资产标签 / Asset tag",
            "成品 / Sample", "滑块 / Slider", "冷却水路 / Cooling", "模具外观 / Overview"]
    f = _vendor_head(c)
    for i in range(n):
        f += title(f"{L['photo']} {i + 1}/{n}")
        f.append(_Photo(rng, f"{c.mold_no}  {caps[i % len(caps)]}"))
        f.append(Spacer(1, 4 * mm))
        f.append(_Photo(rng, f"{c.mold_no}  {caps[(i + 3) % len(caps)]}"))
        if i < n - 1:
            from reportlab.platypus import PageBreak
            f.append(PageBreak())
    return build(f)


def doc_dims(c: Case, n_pages: int, rng: random.Random) -> bytes:
    L = T[c.vendor.lang]
    f = _vendor_head(c) + title(L["dim"])
    f.append(kv([(L["part_no"], c.part_no), (L["mold_no"], c.mold_no), ("Cavity", "#1"), ("Sample", "T2 x 5 pcs")]))
    f.append(Spacer(1, 4 * mm))
    rows = [["#", "Nominal", "Tol.", "S1", "S2", "S3", "S4", "S5", L["result"]]]
    for i in range(1, 28 * n_pages):
        nom = round(rng.uniform(0.5, 45), 2)
        tol = rng.choice([0.02, 0.03, 0.05, 0.1])
        rows.append([str(i), f"{nom:.2f}", f"±{tol}"] + [f"{nom + rng.uniform(-tol, tol) * 0.7:.3f}" for _ in range(5)]
                    + ["OK"])
    f.append(grid(rows, [10 * mm, 22 * mm, 16 * mm] + [22 * mm] * 5 + [20 * mm], size=7.5))
    return build(f)


def scan(pdf_bytes: bytes, rng: random.Random) -> bytes:
    src = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    out = pymupdf.open()
    for page in src:
        pix = page.get_pixmap(dpi=110, colorspace=pymupdf.csGRAY)
        img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        img = img.rotate(rng.uniform(-2.2, 2.2), resample=Image.BICUBIC, expand=False, fillcolor=245)
        noise = Image.effect_noise(img.size, 18).point(lambda p: p - 128)
        img = Image.blend(img, Image.merge("L", [noise]).point(lambda p: 255 - p // 6), 0.12)
        img = img.filter(ImageFilter.GaussianBlur(0.6))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=55)
        p = out.new_page(width=page.rect.width, height=page.rect.height)
        p.insert_image(p.rect, stream=buf.getvalue())
    return out.tobytes(garbage=3, deflate=True)
