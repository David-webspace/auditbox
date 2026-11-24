import json
import shutil
from pathlib import Path

import pytest

from auditbox import config, pipeline
from auditbox.db import DB

ROOT = Path(__file__).resolve().parents[1]
GTS = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "eval/ground_truth").glob("*.json"))]
RUNS = {json.loads(p.read_text(encoding="utf-8"))["files"]["attachment"]: json.loads(p.read_text(encoding="utf-8"))
        for p in (ROOT / "eval/runs/qwen3.5-9b").glob("C*.json")}


def replay(inv: Path, att: Path, log) -> dict:
    return RUNS[att.name]


@pytest.fixture
def env(tmp_path):
    ws_root = tmp_path / "ws"
    shutil.copytree(ROOT / "demo", ws_root, ignore=shutil.ignore_patterns(".gitkeep"))
    for d in ("02_驗收單", "03_已處理", "04_人工處理"):
        for p in (ws_root / d).iterdir():
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    ws = config.load(ws_root)
    db = DB(tmp_path / "local.db")
    return ws, db, pipeline.Pipeline(ws, db, replay, llm=None)


def test_scan_inbox_pairs_files(env):
    ws, *_ = env
    items = pipeline.scan_inbox(ws, "Amber")
    assert [i.base for i in items] == ["恆岳2041", "恆岳2071", "華盛5162", "蘇韻7720"]
    assert all(i.problem is None for i in items)
    (ws.folder("inbox") / "Amber" / "孤兒9999.pdf").write_bytes((ws.folder("inbox") / "Amber" / "恆岳2041.pdf").read_bytes())
    orphan = next(i for i in pipeline.scan_inbox(ws, "Amber") if i.base == "孤兒9999")
    assert "缺發票檔" in orphan.problem


def test_process_all_cases(env):
    ws, db, pipe = env
    for gt in GTS:
        base = gt["files"]["attachment"][:-4]
        r = pipe.process(gt["pic"], base, log=lambda m: None)
        assert r["outcome"] == gt["expected_outcome"], gt["case_id"]
        case = db.get(r["case_id"])
        folder = Path(case["folder"])
        assert (folder / "草稿.eml").exists() and (folder / "稽核結果.md").exists()
        assert not (ws.folder("inbox") / gt["pic"] / gt["files"]["attachment"]).exists()
        assert (folder / "原始檔" / gt["files"]["invoice"]).exists()
        top = {"ready_to_sign": "03_已處理"}.get(gt["expected_outcome"], "04_人工處理")
        assert folder.parent.parent.name == top
        if gt["expected_outcome"] == "ready_to_sign":
            assert list((ws.folder("forms") / gt["pic"]).glob(f"{gt['extraction']['po']['po_no']}_資產驗收單_*.xlsx"))
            assert list(folder.glob("*_驗收單合併.pdf"))
        assert case["detail"]["outcome"] == gt["expected_outcome"]
    assert len(db.list()) == 12
    assert len(db.list(status="可送簽")) == 3


def test_resubmitted_po_is_flagged_as_duplicate(env):
    ws, db, pipe = env
    gt = next(g for g in GTS if g["case_id"] == "C01")
    inbox = ws.folder("inbox") / "Amber"
    backup = {n: (inbox / n).read_bytes() for n in gt["files"].values()}
    assert pipe.process("Amber", "恆岳2041", log=lambda m: None)["outcome"] == "ready_to_sign"
    for n, data in backup.items():
        (inbox / n).write_bytes(data)
    r = pipe.process("Amber", "恆岳2041", log=lambda m: None)
    assert r["outcome"] == "internal_action"
    assert any(f["rule"] == "R10" and f["status"] == "fail" for f in db.get(r["case_id"])["detail"]["findings"])


def test_extractor_failure_goes_to_manual_after_retries(env, monkeypatch):
    ws, db, _ = env
    calls = []

    def boom(inv, att, log):
        calls.append(1)
        raise RuntimeError("Ollama 連不上")

    ws.settings["retry"] = 1
    pipe = pipeline.Pipeline(ws, db, boom, llm=None)
    monkeypatch.setattr(pipeline.time, "sleep", lambda s: None)
    r = pipe.process("Kevin", "嘉鴻6118", log=lambda m: None)
    assert r["outcome"] == "system_error" and len(calls) == 2
    assert (ws.folder("manual") / "Kevin" / "系統失敗_嘉鴻6118" / "失敗原因.md").exists()


def test_db_concurrent_access(env):
    from concurrent.futures import ThreadPoolExecutor
    ws, db, pipe = env
    r = pipe.process("Kevin", "嘉鴻6118", log=lambda m: None)
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(lambda i: db.get(r["case_id"]) if i % 3 else db.list(), range(60)))
    assert all(results)


def test_status_update_and_history(env):
    ws, db, pipe = env
    r = pipe.process("Kevin", "嘉鴻6118", log=lambda m: None)
    db.set_status(r["case_id"], "送簽中", "已送傳簽單 #A123")
    c = db.get(r["case_id"])
    assert c["status"] == "送簽中"
    assert [h["status"] for h in c["history"]] == ["可送簽", "送簽中"]
    with pytest.raises(ValueError):
        db.set_status(r["case_id"], "亂寫")
