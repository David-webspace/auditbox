import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

from . import normalize as N
from .config import Workspace


def read_sheet(path: Path) -> list[dict]:
    ws = load_workbook(path, read_only=True, data_only=True).active
    rows = ws.iter_rows(values_only=True)
    headers = [str(h).strip() if h is not None else "" for h in next(rows)]
    return [{h: (v.strip() if isinstance(v, str) else v) for h, v in zip(headers, r)}
            for r in rows if any(v is not None for v in r)]


def as_date(v) -> str | None:
    if isinstance(v, (datetime, date)):
        return v.strftime("%Y-%m-%d")
    return N.iso_date(str(v)) if v else None


@dataclass
class Vendor:
    code: str
    short: str
    name_local: str
    name_en: str
    aliases: list[str]
    currency: str
    tax_rate: float
    contact: str
    contact_email: str
    lang: str
    sourcing_name: str
    sourcing_email: str
    active: bool

    def names(self) -> list[str]:
        return [self.name_local, self.name_en, self.short] + self.aliases

    def matches(self, name: str | None) -> bool:
        if not name:
            return False
        s = N.squash(name)
        return any(N.squash(n) and (N.squash(n) == s or N.squash(n) in s) for n in self.names() if len(n) >= 2)


@dataclass
class Reference:
    vendors: dict[str, Vendor]
    po: dict[str, dict]
    gr: dict[str, list[dict]]
    paid: dict[str, list[dict]]
    employees: dict[str, dict]


def load(ws: Workspace) -> Reference:
    vendors = {}
    for r in read_sheet(ws.config_dir / ws.settings["files"]["vendor_master"]):
        code = str(r["廠商代號"])
        vendors[code] = Vendor(
            code=code, short=r["簡稱"], name_local=r["廠商全名"], name_en=r["英文名稱"] or "",
            aliases=[a.strip() for a in re.split(r"[;；,，]", r.get("別名（分號分隔）") or "") if a.strip()],
            currency=N.currency(r["交易幣別"]), tax_rate=N.amount(r["稅率"]) / 100,
            contact=r["窗口"] or "", contact_email=(r["窗口 Email"] or "").strip(), lang={"簡中": "zh-CN", "繁中": "zh-TW"}.get(r["溝通語言"], "en"),
            sourcing_name=r["策購負責人"], sourcing_email=(r["策購 Email"] or "").strip(), active=r["狀態"] == "有效",
        )
    po = {}
    for r in read_sheet(ws.export("sap_po")):
        r["幣別"] = N.currency(r["幣別"])
        r["文件日期"] = as_date(r["文件日期"])
        r["淨價"] = float(r["淨價"])
        po[str(r["採購文件"])] = r
    gr, paid = {}, {}
    for r in read_sheet(ws.export("sap_gr")):
        r["過帳日期"] = as_date(r["過帳日期"])
        r["金額"] = float(r["金額"])
        gr.setdefault(str(r["採購文件"]), []).append(r)
    for r in read_sheet(ws.export("ap_paid")):
        paid.setdefault(str(r["採購文件"]), []).append(r)
    employees = {str(r["工號"]): r for r in read_sheet(ws.export("employees"))}
    return Reference(vendors, po, gr, paid, employees)
