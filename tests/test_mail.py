import json
from email import message_from_bytes, policy
from pathlib import Path

import pytest

from auditbox import audit, config, mail, reference, routing, zh

ROOT = Path(__file__).resolve().parents[1]
WS = config.load(ROOT / "demo")
REF = reference.load(WS)
RULES = routing.load(WS.config_dir / WS.settings["files"]["mail_routing"])
GTS = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "eval/ground_truth").glob("*.json"))}

EXPECTED_ROUTE = {
    "C01": (["M08", "M09"], ["amber.lin"], ["optical-bu-pm", "optical-pm"]),
    "C02": (["M01"], ["kevin.chen"], []),
    "C03": (["M02"], ["chen.xy"], ["ming.wang", "howard.chang"]),
    "C06": (["M13"], ["minh.nv"], ["ming.wang"]),
    "C09": (["M05"], ["ming.wang"], ["howard.chang", "finance-ap"]),
    "C11": (["M06"], ["sourcing-team"], ["kevin.chen"]),
    "C12": (["M04", "M12"], ["ming.wang"], ["asset-mgmt"]),
}


def case(cid):
    gt = GTS[cid]
    docs = json.loads((ROOT / f"eval/runs/qwen3.5-9b/{cid}.json").read_text(encoding="utf-8"))["documents"]
    fs, ctx = audit.run(docs, REF, WS.rules)
    oc = audit.outcome(fs, WS.rules["outcome_priority"])
    pic = REF.employees[WS.settings["pics"][gt["pic"]]]
    route = routing.resolve(RULES, REF, oc, [f.rule for f in fs if f.status == "fail"], ctx.vendor,
                            (ctx.sap_po or {}).get("產品線"), pic["Email"])
    return gt, fs, ctx, oc, pic, route


@pytest.mark.parametrize("cid", EXPECTED_ROUTE)
def test_route(cid):
    *_, route = case(cid)
    rules, to, cc = EXPECTED_ROUTE[cid]
    assert route.rules == rules
    assert [a.split("@")[0] for a in route.to] == to
    assert [a.split("@")[0] for a in route.cc] == cc


def test_lint_finds_planted_problems():
    issues = routing.lint(RULES, REF, set(WS.rules["rules"]))
    found = {(i["rule_id"], i["level"]) for i in issues}
    assert {("M09", "warning"), ("M10", "error"), ("M12", "error"), ("M13", "error"), ("M01", "warning")} <= found
    assert not any(i["rule_id"] in {"M02", "M03", "M05", "M06", "M07", "M08"} for i in issues)


@pytest.mark.parametrize("cid,lang,needle", [
    ("C05", "zh-TW", "模具訂單承諾書第 5 頁的訂單號寫為 4502318847，正確應為 4502318874"),
    ("C06", "en", "missing the QA signature"),
    ("C04", "zh-TW", "發票未稅金額 USD 23,750.00 與訂單金額 USD 27,350.00 不一致"),
    ("C03", "zh-TW", "缺少以下文件：模具保管單"),
])
def test_vendor_mail(cid, lang, needle, tmp_path):
    gt, fs, ctx, oc, pic, route = case(cid)
    d = mail.compose(outcome=oc, findings=fs, ctx=ctx, case={"pic": pic, "files": gt["files"]}, route=route,
                     form_vals=None, company=WS.settings["company"]["name"],
                     company_en=WS.settings["company"]["name_en"], llm=None)
    assert d.lang == lang
    assert needle in d.html
    assert zh.t(d.html) == d.html and zh.t(d.subject) == d.subject
    if lang == "en":
        assert "隼光" not in d.html and "KESTREL OPTRONICS" in d.html
    for internal in ("SAP", "GR", "K3", "策購"):
        assert internal not in d.html
    msg = message_from_bytes(mail.to_eml(d, "a@b.example", tmp_path / "x.eml").read_bytes(), policy=policy.default)
    assert msg["X-Unsent"] == "1"
    assert msg["To"] == ", ".join(d.to)


def test_llm_intro_guard():
    class Fake:
        name = "fake"

        def __init__(self, text):
            self.text = text

        def json(self, *a, **k):
            return {"intro": self.text}

    facts = {"PO": "4502318874"}
    assert mail.llm_intro(Fake("請協助處理 PO 4502318874。"), facts, "zh-TW", "FB")[1] == "LLM"
    assert mail.llm_intro(Fake("金額 99,999 請確認 PO 4502318874"), facts, "zh-TW", "FB")[0] == "FB"
    assert mail.llm_intro(Fake("王磊先生您好，請確認 PO 4502318874"), facts, "zh-TW", "FB")[0] == "FB"
    assert mail.llm_intro(Fake("Dear Mr. Nguyen, PO 4502318874"), facts, "en", "FB")[0] == "FB"
    assert mail.llm_intro(Fake("Dear Nguyen Van Minh, PO 4502318874"), facts, "en", "FB")[1] == "LLM"


def test_claude_schema_null_roundtrip():
    from auditbox.extract import field_schema
    from auditbox.llm import _restore_nulls, _strip_nulls
    schema, nullable = _strip_nulls(field_schema("invoice"))
    assert "null" not in json.dumps(schema) and len(nullable) == 24
    got = _restore_nulls({"tax": {"value": "", "page": 0, "quote": "稅額 0"}}, nullable)
    assert got == {"tax": {"value": None, "page": None, "quote": "稅額 0"}}
