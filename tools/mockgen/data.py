from dataclasses import dataclass, field
from datetime import date

COMPANY = {
    "name_zh": "隼光科技股份有限公司",
    "name_en": "KESTREL OPTRONICS CORP.",
    "tax_id": "83920517",
    "address_zh": "新北市新店區北新路三段 999 號 12 樓",
    "address_en": "12F., No. 999, Sec. 3, Beixin Rd., Xindian Dist., New Taipei City, Taiwan",
    "domain": "kestrel-optronics.example",
}

MAIL = {
    "sourcing_team": f"sourcing-team@{COMPANY['domain']}",
    "asset_mgmt": f"asset-mgmt@{COMPANY['domain']}",
    "finance_ap": f"finance-ap@{COMPANY['domain']}",
    "optical_pm": f"optical-bu-pm@{COMPANY['domain']}",
}


@dataclass
class Vendor:
    code: str
    short: str
    name_local: str
    name_en: str
    aliases: list[str]
    country: str
    tax_no: str
    currency: str
    tax_rate: float
    payment_terms: str
    contact: str
    contact_email: str
    lang: str
    sourcing_owner: str
    status: str = "有效"
    address: str = ""


VENDORS = [
    Vendor("100231", "恆岳", "东莞恒岳精密模具有限公司", "DONGGUAN HENGYUE PRECISION MOULD CO., LTD",
           ["恆岳", "恒岳", "東莞恆岳", "HENGYUE", "HENG YUE PRECISION MOULD (DONGGUAN) LTD"],
           "CN", "91441900MA4UX3K27B", "USD", 0.0, "月結 60 天", "刘伟", "liu.wei@hengyue-mould.example.cn",
           "zh-CN", "K20117", address="广东省东莞市长安镇振安中路 288 号"),
    Vendor("100318", "鑫拓", "深圳市鑫拓模塑科技有限公司", "SHENZHEN XINTUO MOLDING TECHNOLOGY CO., LTD",
           ["鑫拓", "XINTUO"], "CN", "91440300MA5FQ8L61X", "USD", 0.0, "月結 60 天", "陈晓燕",
           "chen.xy@xintuo-molding.example.cn", "zh-CN", "K20117", address="深圳市宝安区福海街道桥头社区 66 号"),
    Vendor("100452", "昆睿", "昆山昆睿压铸有限公司", "KUNSHAN KUNRUI DIE CASTING CO., LTD",
           ["昆睿", "KUNRUI"], "CN", "91320583MA1N7RD03Q", "RMB", 0.13, "月結 90 天", "周海涛",
           "zhou.ht@kunrui-diecast.example.cn", "zh-CN", "K20263", address="江苏省昆山市玉山镇元丰路 17 号"),
    Vendor("100517", "蘇韻", "苏州苏韵精工模具有限公司", "SUZHOU SUYUN PRECISION TOOLING CO., LTD",
           ["苏韵", "蘇韻", "SUYUN"], "CN", "91320505MA27K9WQ5H", "USD", 0.0, "月結 60 天", "王磊",
           "wang.lei@suyun-tooling.example.cn", "zh-CN", "K20263", address="苏州市高新区浒关工业园 5 号"),
    Vendor("100609", "華盛", "东莞华盛五金冲压有限公司", "DONGGUAN HUASHENG METAL STAMPING CO., LTD",
           ["华盛", "華盛", "HUASHENG"], "CN", "91441900MA51T2E88C", "USD", 0.0, "月結 60 天", "黄志强",
           "huang.zq@huasheng-stamping.example.cn", "zh-CN", "K20117", address="广东省东莞市塘厦镇林村 3 号"),
    Vendor("200108", "嘉鴻", "嘉鴻模具工業股份有限公司", "CHIA HUNG MOLD INDUSTRIAL CO., LTD",
           ["嘉鴻", "CHIA HUNG"], "TW", "24817035", "TWD", 0.05, "月結 60 天", "蔡文彬",
           "wb.tsai@chiahung-mold.example.tw", "zh-TW", "K20263", address="新北市五股區五權路 41 號"),
    Vendor("200233", "立旭", "立旭精密股份有限公司", "LIHSU PRECISION CO., LTD",
           ["立旭", "LIHSU"], "TW", "53106628", "TWD", 0.05, "月結 60 天", "郭怡君",
           "yc.kuo@lihsu.example.tw", "zh-TW", "K20117", address="台中市西屯區工業區三十路 8 號"),
    Vendor("200377", "富鈦", "富鈦金屬工業有限公司", "FU TAI METAL INDUSTRY CO., LTD",
           ["富鈦", "FU TAI"], "TW", "16409952", "TWD", 0.05, "月結 60 天", "林宗翰",
           "th.lin@futai-metal.example.tw", "zh-TW", "K20263", address="桃園市觀音區工業三路 12 號"),
    Vendor("300041", "VietAn", "VIET AN MOLD TECHNOLOGY CO., LTD", "VIET AN MOLD TECHNOLOGY CO., LTD",
           ["VIET AN", "VIETAN MOLD"], "VN", "2301129874", "USD", 0.0, "Net 60", "Nguyen Van Minh",
           "minh.nv@vietan-mold.example.vn", "en", "K20117", address="Lot C2, Que Vo Industrial Park, Bac Ninh, Vietnam"),
    Vendor("300099", "PenangTool", "PENANG TOOLMAKERS SDN. BHD.", "PENANG TOOLMAKERS SDN. BHD.",
           ["PENANG TOOLMAKERS", "PTM"], "MY", "201501028816", "USD", 0.0, "Net 60", "Tan Wei Liang",
           "wl.tan@penangtool.example.my", "en", "K20263", address="Plot 88, Bayan Lepas FIZ Phase 4, Penang, Malaysia"),
    Vendor("100733", "精岳", "东莞精岳光电治具有限公司", "DONGGUAN JINGYUE OPTO FIXTURE CO., LTD",
           ["精岳"], "CN", "91441900MA4WK0P17D", "USD", 0.0, "月結 60 天", "李娜",
           "li.na@jingyue-opto.example.cn", "zh-CN", "K20117", address="广东省东莞市凤岗镇雁田村 9 号"),
    Vendor("100811", "永泰", "宁波永泰模具有限公司", "NINGBO YONGTAI MOULD CO., LTD",
           ["永泰"], "CN", "91330206MA2H3NQ45R", "USD", 0.0, "月結 60 天", "孙强",
           "sun.q@yongtai-mould.example.cn", "zh-CN", "K20263", status="停用", address="浙江省宁波市北仑区新碶 21 号"),
]

UNLISTED_VENDOR = Vendor(
    "100955", "博創", "惠州博创模具有限公司", "HUIZHOU BOCHUANG MOULD CO., LTD", ["博創", "博创"], "CN",
    "91441300MA56R7XC2L", "USD", 0.0, "月結 60 天", "何俊", "he.jun@bochuang-mould.example.cn", "zh-CN", "K20117",
    address="广东省惠州市仲恺高新区 23 号小区")

VENDOR_BY_CODE = {v.code: v for v in VENDORS + [UNLISTED_VENDOR]}


@dataclass
class Employee:
    emp_id: str
    name: str
    name_en: str
    dept: str
    title: str
    status: str = "在職"

    @property
    def email(self) -> str:
        return f"{self.name_en.lower().replace(' ', '.')}@{COMPANY['domain']}"


EMPLOYEES = [
    Employee("K10231", "林雅婷", "Amber Lin", "採購部", "採購專員"),
    Employee("K10418", "陳冠宇", "Kevin Chen", "採購部", "採購專員"),
    Employee("K10552", "王思明", "Ming Wang", "採購部", "資深採購"),
    Employee("K20117", "張書豪", "Howard Chang", "策略採購部", "策購經理"),
    Employee("K20263", "李佩珊", "Peishan Lee", "策略採購部", "策購工程師"),
    Employee("K30045", "黃柏翰", "Bohan Huang", "機構工程部", "模具工程師"),
    Employee("K30112", "吳佳蓉", "Jiarong Wu", "機構工程部", "模具工程師"),
    Employee("K30187", "許志明", "Zhiming Hsu", "機構工程部", "資深模具工程師"),
    Employee("K30209", "鄭宇翔", "Yuxiang Cheng", "機構工程部", "模具工程師", "離職"),
    Employee("K30244", "蘇怡安", "Yian Su", "機構工程部", "模具工程師"),
    Employee("K40031", "劉家豪", "Jiahao Liu", "品保部", "品保工程師"),
    Employee("K40078", "楊雅雯", "Yawen Yang", "品保部", "品保主任"),
    Employee("K50012", "趙怡君", "Yijun Chao", "財務部", "資產管理專員"),
    Employee("K50033", "周明哲", "Mingzhe Chou", "財務部", "應付帳款專員"),
    Employee("K30301", "高子晴", "Ziqing Kao", "機構工程部", "模具工程師"),
]
EMP_BY_ID = {e.emp_id: e for e in EMPLOYEES}
PICS = {"Amber": "K10231", "Kevin": "K10418", "Ming": "K10552"}


@dataclass
class Case:
    case_id: str
    pic: str
    vendor_code: str
    file_ref: str
    mold_no: str
    part_no: str
    item_zh: str
    item_en: str
    product_line: str
    mold_type: str
    cavities: str
    steel: str
    shot_life: int
    po_no: str
    po_date: date
    amount: float
    approval_date: date
    gr_no: str | None
    gr_date: date | None
    invoice_no: str
    invoice_date: date
    custodian: str
    storage: str
    anomaly: str
    expect_issues: list[str]
    expect_outcome: str
    overrides: dict = field(default_factory=dict)
    scanned: bool = False
    extra_pages: int = 6

    @property
    def vendor(self) -> Vendor:
        return VENDOR_BY_CODE[self.vendor_code]


CASES = [
    Case("C01", "Amber", "100231", "2041", "KT-M260318", "51-QD800-021", "QSFP-DD 800G 外殼上蓋 鋅合金壓鑄模 1x4",
         "QSFP-DD 800G TOP COVER ZINC DIE-CAST MOULD 1x4", "光通訊", "壓鑄模", "1x4", "SKD61", 300000,
         "4502318801", date(2026, 3, 18), 48500.00, date(2026, 6, 22), "5000871204", date(2026, 7, 15),
         "HY-INV-2026-0917", date(2026, 10, 28), "K30045", "廠商端－東莞恒岳長安廠 B 棟模具倉",
         "正常", [], "ready_to_sign", extra_pages=12),
    Case("C02", "Kevin", "200108", "6118", "KT-M260402", "31-TWS7-CS01", "TWS 充電盒上蓋 射出模 1x2",
         "TWS CHARGING CASE TOP COVER INJECTION MOLD 1x2", "消費電子", "射出模", "1x2", "NAK80", 500000,
         "4502318812", date(2026, 4, 2), 1286000.00, date(2026, 6, 30), "5000871266", date(2026, 7, 21),
         "AB-37190256", date(2026, 10, 31), "K30112", "廠商端－嘉鴻五股廠 2F 模具區",
         "正常", [], "ready_to_sign", extra_pages=5),
    Case("C03", "Ming", "100318", "3305", "KT-M260415", "31-TWS7-HS02", "TWS 耳機外殼 左右 射出模 1+1",
         "TWS EARBUD HOUSING L/R INJECTION MOULD 1+1", "消費電子", "射出模", "1+1", "S136", 500000,
         "4502318826", date(2026, 4, 15), 36800.00, date(2026, 7, 8), "5000871310", date(2026, 8, 4),
         "XT20261029-03", date(2026, 10, 29), "K30187", "廠商端－深圳鑫拓寶安廠 模具倉 A3",
         "缺保管單", ["R01"], "need_vendor_docs", overrides={"drop_docs": ["custody"]}, extra_pages=8),
    Case("C04", "Amber", "100517", "7720", "KT-M260421", "61-LC08-CL01", "LC 光纖連接器卡扣 射出模 1x8",
         "LC CONNECTOR LATCH INJECTION MOULD 1x8", "光通訊", "射出模", "1x8", "S136", 1000000,
         "4502318839", date(2026, 4, 21), 27350.00, date(2026, 7, 14), "5000871355", date(2026, 8, 11),
         "SY-2026-1102", date(2026, 11, 2), "K30244", "廠商端－蘇州蘇韻滸關廠 模具倉",
         "發票金額與 PO 不符", ["R04"], "need_vendor_docs", overrides={"invoice_amount": 23750.00}, extra_pages=4),
    Case("C05", "Kevin", "100452", "1187", "KT-M260506", "21-SW5-MF01", "智慧手錶中框 鋁合金壓鑄模 1x2",
         "SMART WATCH MIDDLE FRAME AL DIE-CAST MOULD 1x2", "消費電子", "壓鑄模", "1x2", "H13", 150000,
         "4502318874", date(2026, 5, 6), 386000.00, date(2026, 7, 29), "5000871402", date(2026, 8, 25),
         "04412688", date(2026, 11, 3), "K30045", "厂商端－昆山昆睿玉山厂 压铸模具库",
         "承諾書 PO 號打錯", ["R02"], "need_vendor_docs", overrides={"commitment_po": "4502318847"}, extra_pages=10),
    Case("C06", "Ming", "300041", "3307", "KT-M260512", "41-PB20-HS01", "行動電源外殼 射出模 1x1",
         "POWER BANK HOUSING INJECTION MOLD 1x1", "消費電子", "射出模", "1x1", "NAK80", 300000,
         "4502318885", date(2026, 5, 12), 21900.00, date(2026, 8, 5), "5000871447", date(2026, 9, 1),
         "VAM-INV-26-0388", date(2026, 11, 4), "K30301", "Vendor site - Viet An Que Vo plant, Tool Store 1",
         "承認書未簽品保", ["R07"], "need_vendor_docs", overrides={"unsigned_roles": ["qa"]}, extra_pages=3),
    Case("C07", "Amber", "100609", "5162", "KT-M260520", "61-OS16-PT01", "800G 光模組拉環 沖壓連續模",
         "800G TRANSCEIVER PULL TAB PROGRESSIVE STAMPING DIE", "光通訊", "沖壓模", "連續模 12 工站", "SKD11", 2000000,
         "4502318893", date(2026, 5, 20), 18600.00, date(2026, 8, 12), "5000871490", date(2026, 9, 8),
         "HS-2026-1105", date(2026, 11, 5), "K30244", "廠商端－東莞華盛塘廈廠 沖模倉",
         "發票幣別與 PO 不符", ["R05"], "need_vendor_docs",
         overrides={"invoice_currency": "RMB", "invoice_amount": 132060.00}, extra_pages=6),
    Case("C08", "Kevin", "200233", "8840", "KT-M260603", "41-SPK3-GR01", "藍牙喇叭網罩 沖壓模 1x1",
         "BLUETOOTH SPEAKER GRILLE STAMPING DIE 1x1", "消費電子", "沖壓模", "1x1", "SKD11", 800000,
         "4502318921", date(2026, 6, 3), 742000.00, date(2026, 8, 19), None, None,
         "AB-37190788", date(2026, 11, 6), "K30112", "廠商端－立旭台中廠 模具區 C",
         "SAP 查無 GR", ["R09"], "internal_action", extra_pages=5),
    Case("C09", "Ming", "100231", "2066", "KT-M260611", "61-OS16-HS01", "OSFP 散熱鰭片 鋁壓鑄模 1x2",
         "OSFP HEATSINK ALUMINIUM DIE-CAST MOULD 1x2", "光通訊", "壓鑄模", "1x2", "H13", 200000,
         "4502318938", date(2026, 6, 11), 52600.00, date(2026, 8, 26), "5000871533", date(2026, 9, 15),
         "HY-INV-2026-0784", date(2026, 9, 18), "K30187", "廠商端－東莞恒岳長安廠 B 棟模具倉",
         "重複請款", ["R10"], "internal_action", extra_pages=9),
    Case("C10", "Amber", "100231", "2071", "KT-M260618", "61-QD800-022", "QSFP-DD 800G 外殼下蓋 鋅合金壓鑄模 1x4",
         "QSFP-DD 800G BOTTOM COVER ZINC DIE-CAST MOULD 1x4", "光通訊", "壓鑄模", "1x4", "SKD61", 300000,
         "4502318947", date(2026, 6, 18), 46200.00, date(2026, 9, 2), "5000871579", date(2026, 9, 23),
         "HY-INV-2026-0952", date(2026, 11, 7), "K30045", "廠商端－東莞恒岳長安廠 B 棟模具倉",
         "掃描檔歪斜＋廠商用別名", [], "ready_to_sign",
         overrides={"vendor_display_en": "HENG YUE PRECISION MOULD (DONGGUAN) LTD"}, scanned=True, extra_pages=6),
    Case("C11", "Kevin", "100955", "5520", "KT-M260625", "31-TWS8-CS01", "TWS 充電盒底座 射出模 1x2",
         "TWS CHARGING CASE BASE INJECTION MOULD 1x2", "消費電子", "射出模", "1x2", "NAK80", 500000,
         "4502318956", date(2026, 6, 25), 33400.00, date(2026, 9, 9), "5000871612", date(2026, 9, 30),
         "BC-2026-1108", date(2026, 11, 8), "K30112", "廠商端－惠州博創仲愷廠 模具倉",
         "廠商不在主檔", ["R06"], "master_data", extra_pages=4),
    Case("C12", "Ming", "300099", "4419", "KT-M260702", "61-AOC4-BT01", "AOC 線材尾套 射出模 1x4",
         "AOC CABLE BOOT INJECTION MOULD 1x4", "光通訊", "射出模", "1x4", "S136", 1000000,
         "4502318964", date(2026, 7, 2), 24750.00, date(2026, 9, 16), "5000871648", date(2026, 10, 7),
         "PTM-INV-2611-021", date(2026, 11, 9), "K30209", "Vendor site - Penang Toolmakers Bayan Lepas, Rack 7",
         "保管人已離職", ["R08"], "internal_action", extra_pages=7),
]

PAID_HISTORY_CASE = "C09"
