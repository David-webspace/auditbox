import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Workspace:
    root: Path
    settings: dict
    rules: dict
    form_map: dict

    @property
    def config_dir(self) -> Path:
        return self.root / "00_設定"

    def folder(self, key: str) -> Path:
        return self.root / self.settings["folders"][key]

    def export(self, key: str) -> Path:
        matches = sorted(self.folder("exports").glob(self.settings["files"][key]))
        if not matches:
            raise FileNotFoundError(f"05_系統匯出 找不到 {self.settings['files'][key]}")
        return matches[-1]


def load(root: Path) -> Workspace:
    cfg = root / "00_設定"

    def read(name):
        return yaml.safe_load((cfg / name).read_text(encoding="utf-8"))

    settings = read("設定.yaml")
    _env_overrides(settings)
    return Workspace(root, settings, read("稽核規則.yaml"), read("驗收單欄位對照.yaml"))


def _env_overrides(s: dict):
    """讓同一份 設定.yaml 在本機和 Docker 都能用：容器內的服務位址由環境變數決定。"""
    env = os.environ.get
    if env("OLLAMA_BASE_URL"):
        s["llm"]["ollama"]["base_url"] = env("OLLAMA_BASE_URL")
    if env("AUDITBOX_MAIL_MODE"):
        s["mail"]["mode"] = env("AUDITBOX_MAIL_MODE")
    if env("MAILPIT_HOST"):
        s["mail"]["mailpit"]["host"] = env("MAILPIT_HOST")
    if env("MAILPIT_PORT"):
        s["mail"]["mailpit"]["port"] = int(env("MAILPIT_PORT"))
