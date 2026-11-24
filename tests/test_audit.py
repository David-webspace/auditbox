import json
from datetime import datetime
from pathlib import Path

import pytest

from auditbox import audit, config, form, reference
from auditbox import normalize as N

ROOT = Path(__file__).resolve().parents[1]
WS = config.load(ROOT / "demo")
REF = reference.load(WS)
GTS = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "eval/ground_truth").glob("*.json"))]
RUN_DIR = ROOT / "eval/runs/qwen3.5-9b"


def gt_docs(gt):
    return {d: {"file": "attachment", "fields": {k: {"value": v} for k, v in f.items()}}
            for d, f in gt["extraction"].items()}


def run_docs(gt):
    return json.loads((RUN_DIR / f"{gt['case_id']}.json").read_text(encoding="utf-8"))["documents"]


@pytest.mark.parametrize("source", [gt_docs, run_docs], ids=["ground_truth", "qwen_run"])
@pytest.mark.parametrize("gt", GTS, ids=[g["case_id"] for g in GTS])
def test_rules(gt, source):
    findings, _ = audit.run(source(gt), REF, WS.rules)
    failed = [f.rule for f in findings if f.status == "fail"]
    assert failed == gt["expected_issues"], [(f.rule, f.message) for f in findings if f.status == "fail"]
    assert audit.outcome(findings, WS.rules["outcome_priority"]) == gt["expected_outcome"]


def _norm(v):
    s = str(v)
    return N.iso_date(s) or (f"{N.amount(s):.2f}" if N.amount(s) is not None and s.replace(",", "").replace(".", "").isdigit() else N.squash(s))


@pytest.mark.parametrize("gt", [g for g in GTS if g["expected_outcome"] == "ready_to_sign"], ids=lambda g: g["case_id"])
def test_form_values(gt, tmp_path):
    docs = run_docs(gt)
    _, ctx = audit.run(docs, REF, WS.rules)
    pic = REF.employees[WS.settings["pics"][gt["pic"]]]
    vals = form.values(WS.form_map, ctx, docs, pic, datetime(2026, 11, 24, 15, 0))
    for k, want in gt["acceptance_form"].items():
        assert _norm(vals[k]) == _norm(want), k
    xlsx = form.write_xlsx(WS.config_dir / WS.settings["files"]["form_template"], WS.form_map, vals,
                           tmp_path / "form.xlsx")
    assert xlsx.exists()
    inbox = WS.folder("inbox") / gt["pic"]
    merged = form.merge([form.render_pdf(WS.settings["company"]["name"], WS.form_map, vals),
                         inbox / gt["files"]["invoice"], inbox / gt["files"]["attachment"]], tmp_path / "m.pdf")
    import pymupdf
    pages = sum(b - a + 1 for a, b in gt["pages"].values()) + 2
    assert len(pymupdf.open(merged)) == pages
