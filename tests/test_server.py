import json
import shutil
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from auditbox import config, pipeline
from auditbox.db import DB
from auditbox.server import create_app

ROOT = Path(__file__).resolve().parents[1]
RUNS = {json.loads(p.read_text(encoding="utf-8"))["files"]["attachment"]: json.loads(p.read_text(encoding="utf-8"))
        for p in (ROOT / "eval/runs/qwen3.5-9b").glob("C*.json")}


def make(tmp_path):
    root = tmp_path / "ws"
    shutil.copytree(ROOT / "demo", root)
    cfg = root / "00_設定" / "設定.yaml"
    s = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    s["local_db"] = str(tmp_path / "t.db")
    cfg.write_text(yaml.safe_dump(s, allow_unicode=True), encoding="utf-8")
    return root, TestClient(create_app(root))


def test_api_flow(tmp_path):
    root, client = make(tmp_path)
    assert client.get("/api/meta").json()["pics"] == ["Amber", "Kevin", "Ming"]
    inbox = client.get("/api/inbox", params={"pic": "Kevin"}).json()
    assert {i["base"] for i in inbox} == {"嘉鴻6118", "昆睿1187", "立旭8840", "博創5520"}
    assert client.post("/api/jobs", json={"pic": "Kevin", "bases": ["不存在"]}).status_code == 400
    assert any(c["name"] == "寄信對照表" and not c["ok"] for c in client.get("/api/health").json())
    assert len(client.get("/api/routing/lint").json()["issues"]) == 7

    ws = config.load(root)
    pipe = pipeline.Pipeline(ws, DB(tmp_path / "t.db"), lambda i, a, log: RUNS[a.name], llm=None)
    case_id = pipe.process("Kevin", "昆睿1187", log=lambda m: None)["case_id"]
    cases = client.get("/api/cases", params={"status": "待廠商補件"}).json()
    assert [c["id"] for c in cases] == [case_id]
    detail = client.get(f"/api/cases/{case_id}").json()["detail"]
    r02 = next(f for f in detail["findings"] if f["rule"] == "R02")
    ev = r02["evidence"][0]
    png = client.get(f"/api/cases/{case_id}/page", params={"file": "attachment", "n": ev["page"], "q": ev["value"]})
    assert png.headers["content-type"] == "image/png" and len(png.content) > 10000
    assert client.get(f"/api/cases/{case_id}/files/草稿.eml").status_code == 200
    assert client.get(f"/api/cases/{case_id}/files/../../00_設定/設定.yaml").status_code == 404
    r = client.patch(f"/api/cases/{case_id}", json={"status": "已寄補件", "note": "11/24 已寄"})
    assert r.json()["status"] == "已寄補件"
    assert client.patch(f"/api/cases/{case_id}", json={"status": "亂寫"}).status_code == 400


def test_llm_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDITBOX_DATA", str(tmp_path / "data"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("AUDITBOX_LLM_PROVIDER", raising=False)
    checked = []
    monkeypatch.setattr("auditbox.server.check_claude_key", lambda key, model: checked.append((key, model)))
    _, client = make(tmp_path)

    assert client.put("/api/llm", json={"provider": "claude"}).status_code == 400  # 沒有 key
    key = "sk-ant-api03-" + "x" * 40 + "WXYZ"
    r = client.put("/api/llm", json={"provider": "claude", "model": "claude-haiku-5-5", "api_key": key})
    assert r.status_code == 200 and checked == [(key, "claude-haiku-5-5")]
    body = client.get("/api/llm").json()
    assert body["provider"] == "claude" and body["model"] == "claude-haiku-5-5"
    assert key not in json.dumps(body) and body["key_hint"].endswith("WXYZ")
    assert client.get("/api/meta").json()["llm_ready"]
    prefs = tmp_path / "data" / "llm.json"
    assert prefs.stat().st_mode & 0o777 == 0o600

    # 只換 provider 不帶 key：保留原本的 key
    client.put("/api/llm", json={"provider": "ollama"})
    assert json.loads(prefs.read_text())["api_key"] == key
    # 空字串清除 key 後，Claude 不能開跑
    client.put("/api/llm", json={"provider": "ollama", "api_key": ""})
    client.put("/api/llm", json={"provider": "ollama"})
    assert "api_key" not in json.loads(prefs.read_text())
    assert client.put("/api/llm", json={"provider": "claude", "model": "bad-model", "api_key": key}).status_code == 400


def test_display_paths_hide_home():
    from auditbox.server import _short
    home = Path.home()
    assert _short(home / "Documents" / "ws") == str(Path("~") / "Documents" / "ws")
    assert _short("/opt/ws") == "/opt/ws"
    assert _short(str(home) + "2/x") == str(home) + "2/x"
