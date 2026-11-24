from dataclasses import asdict, dataclass, field

from . import normalize as N
from . import zh
from .extract import DOC_LABELS
from .reference import Reference, Vendor

OUTCOME_BY_OWNER = {"vendor": "need_vendor_docs", "pic": "internal_action", "sourcing": "master_data"}
OUTCOME_LABEL = {"ready_to_sign": "可送簽", "need_vendor_docs": "待廠商補件", "internal_action": "內部處理",
                 "master_data": "主檔維護"}
ROLE_LABEL = {"design": "模具設計", "qa": "品保", "me": "ME"}


@dataclass
class Finding:
    rule: str
    name: str
    owner: str
    status: str
    message: str
    evidence: list[dict] = field(default_factory=list)
    data: dict = field(default_factory=dict)


@dataclass
class Context:
    po_no: str | None
    sap_po: dict | None
    vendor: Vendor | None
    gr: dict | None
    custodian: dict | None


def _f(docs: dict, doc: str, name: str):
    return docs.get(doc, {}).get("fields", {}).get(name, {}).get("value")


def _ev(docs: dict, doc: str, name: str) -> dict:
    d = docs.get(doc, {})
    f = d.get("fields", {}).get(name, {})
    return {"doc": DOC_LABELS[doc], "file": d.get("file"), "page": f.get("page"), "value": f.get("value"),
            "raw": f.get("raw"), "quote": f.get("quote")}


def _close(a, b, tol) -> bool:
    return a is not None and b is not None and abs(a - b) <= tol


def resolve(docs: dict, ref: Reference) -> Context:
    po_no = _f(docs, "po", "po_no") or _f(docs, "invoice", "po_no")
    sap_po = ref.po.get(po_no or "")
    vendor = ref.vendors.get(str(sap_po["供應商"])) if sap_po else None
    grs = ref.gr.get(po_no or "", [])
    cust = ref.employees.get(_f(docs, "custody", "custodian_id") or "")
    return Context(po_no, sap_po, vendor, grs[0] if grs else None, cust)


def run(docs: dict, ref: Reference, cfg: dict, ledger: set[str] = frozenset()) -> tuple[list[Finding], Context]:
    ctx = resolve(docs, ref)
    rules, tol = cfg["rules"], cfg["amount_tolerance"]
    out: list[Finding] = []

    def add(rid, ok, msg, evidence=(), skip=None, data=None):
        status = "skipped" if skip else ("pass" if ok else "fail")
        out.append(Finding(rid, rules[rid]["name"], rules[rid]["owner"], status, zh.t(skip or msg), list(evidence),
                           data or {}))

    present = {d for d, v in docs.items() if v.get("fields")}
    missing = [d for d in cfg["required_docs"] if d not in present]
    add("R01", not missing, "缺少：" + "、".join(DOC_LABELS[d] for d in missing) if missing else "文件齊全",
        data={"missing": missing})

    for rid, fname in (("R02", "po_no"), ("R03", "mold_no")):
        want = ctx.po_no if fname == "po_no" else (ctx.sap_po or {}).get("模具編號") or _f(docs, "po", "mold_no")
        diffs = [{**_ev(docs, d, fname), "doc_key": d} for d in docs
                 if _f(docs, d, fname) and _f(docs, d, fname) != want]
        label = "PO 號" if fname == "po_no" else "模具編號"
        add(rid, not diffs, f"{label}與 PO 不一致（應為 {want}）：" +
            "、".join(f"{e['doc']} 第 {e['page']} 頁寫 {e['value']}" for e in diffs) if diffs else f"{label}一致",
            diffs, skip=None if want else f"找不到 {label}，無法比對", data={"want": want, "diffs": diffs})

    inv_cur, po_cur = _f(docs, "invoice", "currency"), _f(docs, "po", "currency") or (ctx.sap_po or {}).get("幣別")
    add("R05", inv_cur == po_cur, f"發票幣別 {inv_cur}，PO 幣別 {po_cur}",
        [_ev(docs, "invoice", "currency")], skip=None if inv_cur and po_cur else "缺發票或 PO 幣別",
        data={"invoice": inv_cur, "po": po_cur})

    inv_amt = _f(docs, "invoice", "amount_untaxed")
    po_amt = _f(docs, "po", "amount") or (ctx.sap_po or {}).get("淨價")
    cost = _f(docs, "cost_breakdown", "total")
    sap_amt = (ctx.sap_po or {}).get("淨價")
    if inv_cur != po_cur:
        add("R04", True, "", skip="幣別不同，改由 R05 判定")
    elif inv_amt is None or po_amt is None:
        add("R04", True, "", skip="缺發票或 PO 金額")
    else:
        bad = []
        if not _close(inv_amt, po_amt, tol):
            bad.append(f"發票未稅 {inv_amt:,.2f} ≠ PO {po_amt:,.2f}")
        if cost is not None and not _close(cost, po_amt, tol):
            bad.append(f"明細表合計 {cost:,.2f} ≠ PO {po_amt:,.2f}")
        if sap_amt is not None and not _close(sap_amt, po_amt, tol):
            bad.append(f"SAP 淨價 {sap_amt:,.2f} ≠ PO 文件 {po_amt:,.2f}")
        add("R04", not bad, "；".join(bad) or f"金額一致 {po_cur} {po_amt:,.2f}",
            [_ev(docs, "invoice", "amount_untaxed"), _ev(docs, "po", "amount"), _ev(docs, "cost_breakdown", "total")],
            data={"currency": po_cur, "invoice": inv_amt, "po": po_amt, "cost": cost,
                  "invoice_bad": not _close(inv_amt, po_amt, tol),
                  "cost_bad": cost is not None and not _close(cost, po_amt, tol)})

    v = ctx.vendor
    if not ctx.sap_po:
        add("R06", False, f"SAP 查無 PO {ctx.po_no}，無法確認廠商")
    elif not v:
        add("R06", False, f"廠商 {ctx.sap_po['供應商']} {ctx.sap_po['供應商名稱']} 不在模具廠商主檔")
    else:
        add("R06", v.active, f"廠商 {v.code} {v.short} 狀態{'有效' if v.active else '停用'}")

    roles = _f(docs, "approval", "signed_roles")
    if "approval" not in present:
        add("R07", True, "", skip="缺承認書，由 R01 判定")
    else:
        lack = [r for r in cfg["required_approval_roles"] if r not in (roles or [])]
        result = _f(docs, "approval", "result")
        msg = []
        if lack:
            msg.append("未簽：" + "、".join(ROLE_LABEL[r] for r in lack))
        if result != "approved":
            msg.append(f"判定結果為 {result}")
        add("R07", not msg, "；".join(msg) or "簽核完整", [_ev(docs, "approval", "signed_roles")],
            data={"lack": lack, "result": result})

    cid = _f(docs, "custody", "custodian_id")
    if not cid:
        add("R08", True, "", skip="缺保管單或保管人工號")
    else:
        e = ctx.custodian
        ok = bool(e) and e["在職狀態"] == "在職"
        add("R08", ok, f"保管人 {cid} {e['姓名']} {e['在職狀態']}" if e else f"HR 名單查無工號 {cid}",
            [_ev(docs, "custody", "custodian_id")])

    if not ctx.po_no:
        add("R09", True, "", skip="缺 PO 號")
    elif not ctx.gr:
        add("R09", False, f"SAP 查無 PO {ctx.po_no} 的收貨（GR），請先完成收貨")
    else:
        ok = po_amt is None or _close(ctx.gr["金額"], po_amt, tol)
        add("R09", ok, f"GR {ctx.gr['物料文件']}（{ctx.gr['過帳日期']}）金額 {ctx.gr['金額']:,.2f}")

    paid = ref.paid.get(ctx.po_no or "", [])
    dup = paid or (ctx.po_no in ledger)
    add("R10", not dup, (f"PO {ctx.po_no} 已於 {paid[0]['付款日']} 付款（發票 {paid[0]['發票號碼']}）" if paid
                         else f"PO {ctx.po_no} 已在本系統處理過") if dup else "無重複請款紀錄")

    po_d, ap_d, iv_d = _f(docs, "po", "po_date"), _f(docs, "approval", "approval_date"), _f(docs, "invoice", "invoice_date")
    bad = []
    if po_d and ap_d and ap_d < po_d:
        bad.append(f"承認日 {ap_d} 早於 PO 日 {po_d}")
    if po_d and iv_d and iv_d < po_d:
        bad.append(f"發票日 {iv_d} 早於 PO 日 {po_d}")
    add("R11", not bad, "；".join(bad) or "日期順序合理", skip=None if po_d else "缺 PO 日期",
        data={"po_date": po_d, "approval_date": ap_d, "invoice_date": iv_d})

    tax = _f(docs, "invoice", "tax") or 0.0
    if not v or inv_amt is None:
        add("R12", True, "", skip="缺主檔或發票金額")
    else:
        rate = tax / inv_amt if inv_amt else 0
        add("R12", abs(rate - v.tax_rate) < 0.005, f"發票稅率 {rate:.1%}，主檔 {v.tax_rate:.0%}",
            [_ev(docs, "invoice", "tax")], data={"rate": rate, "master": v.tax_rate})

    seller = _f(docs, "invoice", "vendor_name")
    if not v or not seller:
        add("R13", True, "", skip="缺主檔或發票賣方")
    else:
        add("R13", v.matches(seller), f"發票賣方「{seller}」" + ("對應主檔 " if v.matches(seller) else "不符主檔 ")
            + f"{v.code} {v.name_local}", [_ev(docs, "invoice", "vendor_name")],
            data={"seller": seller, "vendor": v.name_en or v.name_local})

    out.sort(key=lambda f: f.rule)
    return out, ctx


def outcome(findings: list[Finding], priority: list[str]) -> str:
    owners = {f.owner for f in findings if f.status == "fail"}
    for o in priority:
        if o in owners:
            return OUTCOME_BY_OWNER[o]
    return "ready_to_sign"


def to_dict(findings: list[Finding]) -> list[dict]:
    return [asdict(f) for f in findings]
