import re
from collections import defaultdict
from dataclasses import dataclass, field

from .audit import OUTCOME_LABEL
from .reference import Reference, Vendor, read_sheet

EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PLACEHOLDERS = {"{PIC}", "{廠商窗口}", "{策購負責人}"}
MATCH_KEYS = ("異常規則", "廠商代號", "產品線")


@dataclass
class Rule:
    row: int
    rule_id: str
    enabled: bool
    outcome: str
    cond: dict
    to: list[str]
    cc: list[str]
    maintainer: str
    updated: str

    @property
    def specificity(self) -> int:
        return sum(v != "*" for v in self.cond.values())


@dataclass
class Route:
    to: list[str]
    cc: list[str]
    rules: list[str]
    warnings: list[str] = field(default_factory=list)


def _split(s) -> list[str]:
    return [x.strip() for x in re.split(r"[;；]", str(s or "")) if x.strip()]


def load(path) -> list[Rule]:
    out = []
    for i, r in enumerate(read_sheet(path), start=2):
        out.append(Rule(i, str(r["規則ID"]), str(r["啟用"]).upper() == "Y", r["結果"],
                        {k: str(r[k] or "*").strip() for k in MATCH_KEYS}, _split(r["收件人 To"]),
                        _split(r["副本 CC"]), r.get("維護人") or "", str(r.get("更新日") or "")))
    return out


def _bad_recipient(addr: str, ref: Reference) -> str | None:
    if addr in PLACEHOLDERS:
        return None
    if addr.startswith("{"):
        return f"不認得的代稱 {addr}"
    if not EMAIL.match(addr):
        return f"「{addr}」不是有效的 Email"
    left = [e for e in ref.employees.values() if e["Email"] == addr and e["在職狀態"] != "在職"]
    if left:
        return f"{addr}（{left[0]['姓名']}）已{left[0]['在職狀態']}"
    return None


def lint(rules: list[Rule], ref: Reference, rule_ids: set[str]) -> list[dict]:
    issues = []

    def add(level, rule, msg):
        issues.append({"level": level, "row": rule.row, "rule_id": rule.rule_id, "message": msg})

    seen = {}
    groups = defaultdict(list)
    active_names = {e["姓名"] for e in ref.employees.values() if e["在職狀態"] == "在職"}
    for r in rules:
        if not r.enabled:
            continue
        key = (r.outcome, tuple(r.cond.values()))
        full = key + (tuple(r.to), tuple(r.cc))
        if full in seen:
            add("warning", r, f"與第 {seen[full]} 列完全重複")
            continue
        seen[full] = r.row
        groups[key].append(r)
        if r.outcome not in OUTCOME_LABEL.values():
            add("error", r, f"結果「{r.outcome}」不在 {list(OUTCOME_LABEL.values())}")
        if r.cond["異常規則"] != "*" and r.cond["異常規則"] not in rule_ids:
            add("error", r, f"異常規則 {r.cond['異常規則']} 不存在")
        if r.cond["廠商代號"] != "*" and r.cond["廠商代號"] not in ref.vendors:
            add("warning", r, f"廠商代號 {r.cond['廠商代號']} 不在廠商主檔")
        if not r.to:
            add("error", r, "沒有收件人")
        for addr in r.to + r.cc:
            if msg := _bad_recipient(addr, ref):
                add("error", r, msg)
        if r.maintainer and r.maintainer not in active_names:
            add("info", r, f"維護人 {r.maintainer} 不在在職名單，建議改由其他人維護")
    for key, rs in groups.items():
        if len({(tuple(r.to), tuple(r.cc)) for r in rs}) > 1:
            for r in rs[1:]:
                add("warning", r, f"與 {rs[0].rule_id}（第 {rs[0].row} 列）條件相同但收件人不同，系統會合併兩者的收件人")
    return sorted(issues, key=lambda x: x["row"])


def resolve(rules: list[Rule], ref: Reference, outcome: str, failed: list[str], vendor: Vendor | None,
            product_line: str | None, pic_email: str) -> Route:
    label = OUTCOME_LABEL[outcome]
    facts = {"異常規則": set(failed) | {"*"}, "廠商代號": {vendor.code if vendor else "", "*"},
             "產品線": {product_line or "", "*"}}
    hits = [r for r in rules if r.enabled and r.outcome == label and all(r.cond[k] in facts[k] for k in MATCH_KEYS)]
    route = Route([], [], [])
    if not hits:
        route.to = [pic_email]
        route.warnings.append(f"寄信對照表沒有「{label}」的規則，改寄承辦")
        return route
    top = max(r.specificity for r in hits)
    chosen, seen = [], set()
    for r in hits:
        if r.specificity == top and (tuple(r.to), tuple(r.cc)) not in seen:
            seen.add((tuple(r.to), tuple(r.cc)))
            chosen.append(r)
    subst = {"{PIC}": pic_email, "{廠商窗口}": vendor.contact_email if vendor else "",
             "{策購負責人}": vendor.sourcing_email if vendor else ""}
    for r in chosen:
        route.rules.append(r.rule_id)
        for bucket, addrs in ((route.to, r.to), (route.cc, r.cc)):
            for a in addrs:
                if msg := _bad_recipient(a, ref):
                    route.warnings.append(f"{r.rule_id}：{msg}，已略過")
                    continue
                a = subst.get(a, a)
                if a and a not in bucket:
                    bucket.append(a)
    route.cc = [a for a in route.cc if a not in route.to]
    if len(chosen) > 1:
        route.warnings.append(f"{'、'.join(route.rules)} 條件相同，已合併收件人")
    if not route.to:
        route.to = [pic_email]
        route.warnings.append("規則解析後沒有收件人，改寄承辦")
    return route
