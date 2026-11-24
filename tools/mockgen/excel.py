from auditbox.zh import t
import random
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .data import CASES, COMPANY, EMP_BY_ID, EMPLOYEES, MAIL, PAID_HISTORY_CASE, PICS, VENDORS

HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
HEADER_FONT = Font(bold=True, color="FFFFFF")
THIN = Side(style="thin", color="7F7F7F")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _table(ws, headers, rows, widths=None):
    ws.append(headers)
    for c in ws[1]:
        c.fill, c.font, c.alignment = HEADER_FILL, HEADER_FONT, Alignment(horizontal="center", vertical="center")
    for r in rows:
        ws.append(r)
    for i, h in enumerate(headers, 1):
        w = (widths or {}).get(h) or max(10, min(48, max(len(str(x)) for x in [h] + [r[i - 1] for r in rows]) * 1.6))
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"


def vendor_master(path: Path):
    wb = Workbook()
    ws = wb.active
    ws.title = "廠商主檔"
    owners = {"K20117": EMP_BY_ID["K20117"], "K20263": EMP_BY_ID["K20263"]}
    rows = []
    for v in VENDORS:
        o = owners[v.sourcing_owner]
        rows.append([v.code, v.short, t(v.name_local), v.name_en, "; ".join(v.aliases), v.country, v.tax_no,
                     v.currency, f"{int(v.tax_rate * 100)}%", v.payment_terms, t(v.contact), v.contact_email,
                     {"zh-CN": "簡中", "zh-TW": "繁中", "en": "英文"}[v.lang], o.name, o.email, v.status,
                     "2026/10/15", o.name])
    rows[2][11] = "zhou.ht@kunrui-diecast.example.cn "
    rows[4][4] = "华盛;華盛;HUASHENG"
    _table(ws, ["廠商代號", "簡稱", "廠商全名", "英文名稱", "別名（分號分隔）", "國別", "稅號/統編", "交易幣別",
                "稅率", "付款條件", "窗口", "窗口 Email", "溝通語言", "策購負責人", "策購 Email", "狀態",
                "更新日", "維護人"], rows)
    wb.save(path)


def _other_pos(rng: random.Random, n: int):
    items = ["治具 測試座", "包材 吸塑盤 開模", "檢具 外觀檢具", "射出模 修模費", "沖壓模 備品沖頭",
             "光纖耦合治具", "電測治具 ICT", "壓鑄模 保養費"]
    rows = []
    for i in range(n):
        v = rng.choice(VENDORS[:10])
        d = date(2026, 1, 5) + timedelta(days=rng.randint(0, 300))
        amt = round(rng.uniform(800, 30000), 2) if v.currency != "TWD" else float(rng.randint(30, 900) * 1000)
        if v.currency == "RMB":
            amt = float(rng.randint(10, 300) * 1000)
        rows.append([f"45023{rng.randint(10000, 17999)}", 10, v.code, t(v.name_local), f"Z9-{rng.randint(1000, 9999)}",
                     rng.choice(items), 1, "SET", amt, v.currency, d.strftime("%Y/%m/%d"), "P31",
                     rng.choice(["消費電子", "光通訊"]), rng.choice(["K10231", "K10418", "K10552"]), ""])
    return rows


def sap_exports(dir_: Path, rng: random.Random):
    po_rows = []
    for c in CASES:
        v = c.vendor
        po_rows.append([c.po_no, 10, v.code, t(v.name_local), "Z1-" + c.mold_no[-6:], c.item_zh, 1, "SET",
                        c.amount, v.currency, c.po_date.strftime("%Y/%m/%d"), "P31", c.product_line,
                        PICS[c.pic], c.mold_no])
    po_rows += _other_pos(rng, 46)
    rng.shuffle(po_rows)
    wb = Workbook()
    ws = wb.active
    ws.title = "ME2N"
    _table(ws, ["採購文件", "項目", "供應商", "供應商名稱", "物料", "短文", "訂單數量", "單位", "淨價", "幣別",
                "文件日期", "採購群組", "產品線", "請購人", "模具編號"], po_rows)
    wb.save(dir_ / "SAP_PO明細_ME2N_20261124.xlsx")

    gr_rows = []
    for c in CASES:
        if c.gr_no:
            gr_rows.append([c.gr_no, 2026, c.po_no, 10, c.gr_date.strftime("%Y/%m/%d"), 1, "SET", c.amount,
                            c.vendor.currency, "M100", "101"])
    for r in rng.sample(po_rows, 30):
        if r[0] in {c.po_no for c in CASES}:
            continue
        d = date(2026, 2, 1) + timedelta(days=rng.randint(0, 280))
        gr_rows.append([f"50008{rng.randint(10000, 69999)}", 2026, r[0], 10, d.strftime("%Y/%m/%d"), 1, "SET",
                        r[8], r[9], "M100", "101"])
    rng.shuffle(gr_rows)
    wb = Workbook()
    ws = wb.active
    ws.title = "MB51"
    _table(ws, ["物料文件", "物料文件年度", "採購文件", "項目", "過帳日期", "數量", "單位", "金額", "幣別",
                "儲存地點", "異動類型"], gr_rows)
    wb.save(dir_ / "SAP_GR明細_MB51_20261124.xlsx")

    paid = []
    for r in rng.sample(po_rows, 14):
        if r[0] in {c.po_no for c in CASES}:
            continue
        d = date(2026, 3, 1) + timedelta(days=rng.randint(0, 240))
        paid.append([r[0], 10, r[2], r[3], f"INV-{rng.randint(100000, 999999)}", r[8], r[9],
                     d.strftime("%Y/%m/%d"), "已付款"])
    c9 = next(c for c in CASES if c.case_id == PAID_HISTORY_CASE)
    paid.append([c9.po_no, 10, c9.vendor_code, t(c9.vendor.name_local), c9.invoice_no, c9.amount, c9.vendor.currency,
                 "2026/10/30", "已付款"])
    rng.shuffle(paid)
    wb = Workbook()
    ws = wb.active
    ws.title = "AP"
    _table(ws, ["採購文件", "項目", "供應商", "供應商名稱", "發票號碼", "未稅金額", "幣別", "付款日", "狀態"], paid)
    wb.save(dir_ / "應付帳款_已付款模具清單_20261124.xlsx")

    wb = Workbook()
    ws = wb.active
    ws.title = "員工"
    _table(ws, ["工號", "姓名", "英文名", "部門", "職稱", "Email", "在職狀態"],
           [[e.emp_id, e.name, e.name_en, e.dept, e.title, e.email, e.status] for e in EMPLOYEES])
    wb.save(dir_ / "HR_員工名單_20261124.xlsx")


def mail_routing(path: Path):
    howard, peishan, left = EMP_BY_ID["K20117"], EMP_BY_ID["K20263"], EMP_BY_ID["K30209"]
    rows = [
        ["M01", "Y", "可送簽", "*", "*", "*", "{PIC}", "", "通過一律寄給承辦", peishan.name, "2026/09/02"],
        ["M02", "Y", "待廠商補件", "*", "*", "*", "{廠商窗口}", "{PIC}; {策購負責人}", "補件信寄廠商，副本承辦與策購",
         howard.name, "2026/09/02"],
        ["M03", "Y", "內部處理", "R09", "*", "*", "{PIC}", "", "SAP 尚未收貨，請承辦先做 GR", howard.name, "2026/09/10"],
        ["M04", "Y", "內部處理", "R08", "*", "*", "{PIC}", MAIL["asset_mgmt"], "保管人異動需資產管理確認",
         "趙怡君", "2026/09/18"],
        ["M05", "Y", "內部處理", "R10", "*", "*", "{PIC}", f"{{策購負責人}}; {MAIL['finance_ap']}", "疑似重複請款",
         "周明哲", "2026/09/18"],
        ["M06", "Y", "主檔維護", "R06", "*", "*", MAIL["sourcing_team"], "{PIC}", "廠商不在主檔，請策購建檔",
         howard.name, "2026/09/02"],
        ["M07", "Y", "待廠商補件", "*", "100231", "*", "{廠商窗口}; qa@hengyue-mould.example.cn",
         "{PIC}; {策購負責人}", "恒岳要求補件信同時寄品保窗口", peishan.name, "2026/10/03"],
        ["M08", "Y", "可送簽", "*", "*", "光通訊", "{PIC}", MAIL["optical_pm"], "光通訊 BU PM 要知道模具進度",
         "許志明", "2026/10/12"],
        ["M09", "Y", "可送簽", "*", "*", "光通訊", "{PIC}", f"optical-pm@{COMPANY['domain']}", "",
         "黃柏翰", "2026/10/20"],
        ["M10", "Y", "待廠商補件", "*", "200108", "*", "wb.tsai@chiahung-mold,example.tw", "{PIC}",
         "嘉鴻窗口", "蘇怡安", "2026/10/22"],
        ["M11", "N", "可送簽", "*", "100811", "*", "{PIC}", "", "永泰已停用", howard.name, "2026/06/30"],
        ["M12", "Y", "內部處理", "R08", "*", "*", "{PIC}", "王大同", "", "吳佳蓉", "2026/10/25"],
        ["M13", "Y", "待廠商補件", "R07", "*", "*", "{廠商窗口}", f"{{PIC}}; {left.email}", "承認書問題副本模具工程",
         left.name, "2026/05/14"],
        ["M01", "Y", "可送簽", "*", "*", "*", "{PIC}", "", "通過一律寄給承辦", peishan.name, "2026/09/02"],
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = "寄信對照表"
    _table(ws, ["規則ID", "啟用", "結果", "異常規則", "廠商代號", "產品線", "收件人 To", "副本 CC", "說明",
                "維護人", "更新日"], rows, widths={"說明": 34, "收件人 To": 44, "副本 CC": 52})
    ws2 = wb.create_sheet("說明")
    for line in [
        "欄位填 * 代表不限。同一案件會套用「條件最具體」的規則（指定欄位越多越優先）。",
        "可用代稱：{PIC} 承辦、{廠商窗口} 廠商主檔的窗口 Email、{策購負責人} 廠商主檔的策購 Email。",
        "結果：可送簽／待廠商補件／內部處理／主檔維護。異常規則填稽核規則編號（R01–R12）。",
        "多個收件人用分號分隔。",
    ]:
        ws2.append([line])
    ws2.column_dimensions["A"].width = 100
    wb.save(path)


FORM_FIELDS = [
    (4, "單號", "申請日期"), (5, "申請人", "部門"), (6, "廠商名稱", "廠商代號"), (7, "PO 號", "PO 項次"),
    (8, "GR 號", "收貨日期"), (9, "驗收日期", "資產類別"), (10, "品名", None), (11, "模具編號", "模穴數"),
    (12, "數量", "單位"), (13, "幣別", "未稅總價"), (14, "存放地點", None), (15, "保管人工號", "保管人姓名"),
    (16, "備註", None),
]


def acceptance_template(path: Path):
    wb = Workbook()
    ws = wb.active
    ws.title = "驗收單"
    for col, w in zip("ABCD", [16, 34, 16, 34]):
        ws.column_dimensions[col].width = w
    ws.merge_cells("A1:D1")
    ws.merge_cells("A2:D2")
    ws["A1"] = COMPANY["name_zh"]
    ws["A2"] = "固定資產驗收單（模具）"
    ws["A1"].font = Font(size=14, bold=True)
    ws["A2"].font = Font(size=16, bold=True)
    for cell in ("A1", "A2"):
        ws[cell].alignment = Alignment(horizontal="center")
    for row, left, right in FORM_FIELDS:
        ws.row_dimensions[row].height = 22
        ws[f"A{row}"] = left
        if right:
            ws[f"C{row}"] = right
        else:
            ws.merge_cells(f"B{row}:D{row}")
        for col in "ABCD":
            c = ws[f"{col}{row}"]
            c.border = BOX
            c.alignment = Alignment(vertical="center", wrap_text=True)
            if col in "AC" and (right or col == "A"):
                c.fill, c.font = HEADER_FILL, HEADER_FONT
    ws["D9"] = "模具"
    ws.row_dimensions[16].height = 40
    for i, title in enumerate(["申請人", "單位主管", "資產管理", "財務"]):
        col = "ABCD"[i]
        ws[f"{col}18"] = title
        ws[f"{col}18"].fill, ws[f"{col}18"].font = HEADER_FILL, HEADER_FONT
        ws[f"{col}18"].alignment = Alignment(horizontal="center")
        for r in (18, 19):
            ws[f"{col}{r}"].border = BOX
    ws.row_dimensions[19].height = 60
    ws["A21"] = "本單由系統依廠商文件與 SAP 資料預填，送簽前請承辦確認。"
    ws["A21"].font = Font(size=9, color="7F7F7F")
    wb.save(path)
