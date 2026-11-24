"""每台電腦自己的資料：案件資料庫與 LLM 設定（含 API key）。

刻意放在工作區之外：工作區是 OneDrive／SharePoint 共用資料夾，API key 不能跟著同步給全部門。
"""
import json
import os
from pathlib import Path

PROVIDERS = ("claude", "ollama")


def data_dir() -> Path:
    d = Path(os.environ.get("AUDITBOX_DATA") or Path.home() / ".auditbox").expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path(ws) -> Path:
    custom = ws.settings.get("local_db")
    return Path(custom).expanduser() if custom else data_dir() / f"{ws.root.name}.db"


def _prefs_file() -> Path:
    return data_dir() / "llm.json"


def load_prefs() -> dict:
    try:
        return json.loads(_prefs_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_prefs(prefs: dict):
    f = _prefs_file()
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(f)


def api_key(prefs: dict | None = None) -> str | None:
    prefs = load_prefs() if prefs is None else prefs
    return prefs.get("api_key") or os.environ.get("ANTHROPIC_API_KEY") or None


def effective(settings: dict) -> dict:
    """畫面上存的設定優先，其次環境變數，最後才是 設定.yaml。"""
    prefs = load_prefs()
    cfg = settings["llm"]
    provider = prefs.get("provider") or os.environ.get("AUDITBOX_LLM_PROVIDER") or cfg["provider"]
    model = prefs.get("model") or cfg["claude"]["model"]
    key = api_key(prefs)
    return {"provider": provider, "model": model if provider == "claude" else cfg["ollama"]["model"],
            "api_key": key, "key_source": "畫面設定" if prefs.get("api_key") else ("環境變數" if key else None)}
