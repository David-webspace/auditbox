import base64
import json
from typing import Protocol

import httpx

# USD per 1M tokens (input, output)
CLAUDE_PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}


class LLM(Protocol):
    name: str
    usage: dict

    def json(self, prompt: str, schema: dict, images: list[bytes] | None = None) -> dict: ...


def _new_usage() -> dict:
    return {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}


class Ollama:
    def __init__(self, base_url: str, model: str, timeout: float = 300):
        self.name = f"ollama:{model}"
        self.model = model
        self.usage = _new_usage()
        self.client = httpx.Client(base_url=base_url, timeout=timeout)

    def json(self, prompt: str, schema: dict, images: list[bytes] | None = None) -> dict:
        msg = {"role": "user", "content": prompt}
        if images:
            msg["images"] = [base64.b64encode(i).decode() for i in images]
        r = self.client.post("/api/chat", json={
            "model": self.model, "messages": [msg], "format": schema, "stream": False, "think": False,
            "options": {"temperature": 0, "num_ctx": 16384},
        })
        r.raise_for_status()
        body = r.json()
        self.usage["calls"] += 1
        self.usage["input_tokens"] += body.get("prompt_eval_count", 0)
        self.usage["output_tokens"] += body.get("eval_count", 0)
        return json.loads(body["message"]["content"])


class Claude:
    def __init__(self, model: str, effort: str = "low", max_tokens: int = 16000, api_key: str | None = None):
        import anthropic

        self.name = f"claude:{model}"
        self.model, self.effort, self.max_tokens = model, effort, max_tokens
        self.usage = _new_usage()
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def json(self, prompt: str, schema: dict, images: list[bytes] | None = None) -> dict:
        content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                "data": base64.standard_b64encode(i).decode()}}
                   for i in images or []]
        schema, nullable = _strip_nulls(schema)
        if nullable:
            prompt += "\n（輸出格式不允許 null：本來要填 null 的地方，文字欄填空字串 \"\"，數字欄填 0。）"
        content.append({"type": "text", "text": prompt})
        kw = {}
        if "haiku" not in self.model:  # Haiku 沒有伺服器端備援模型
            kw = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        resp = self.client.beta.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": content}],
            **kw,
        )
        self.usage["calls"] += 1
        self.usage["input_tokens"] += resp.usage.input_tokens
        self.usage["output_tokens"] += resp.usage.output_tokens
        price_in, price_out = CLAUDE_PRICES.get(resp.model, CLAUDE_PRICES.get(self.model, (0, 0)))
        self.usage["cost_usd"] += (resp.usage.input_tokens * price_in + resp.usage.output_tokens * price_out) / 1e6
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"Claude 婉拒處理（{getattr(resp.stop_details, 'category', None)}）")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError("Claude 回應超過 max_tokens")
        text = next(b.text for b in resp.content if b.type == "text")
        return _restore_nulls(json.loads(text), nullable)


def _strip_nulls(schema: dict) -> tuple[dict, set[str]]:
    """Claude structured outputs 限制最多 16 個 nullable 參數；把 ["string","null"] 改成單一型別，
    回傳時再把空值還原成 None。nullable 記錄「欄位名.子欄位」路徑。"""
    nullable: set[str] = set()

    def walk(node, path):
        if not isinstance(node, dict):
            return node
        node = dict(node)
        t = node.get("type")
        if isinstance(t, list) and "null" in t and len(t) == 2:
            node["type"] = next(x for x in t if x != "null")
            nullable.add(path)
        if "properties" in node:
            node["properties"] = {k: walk(v, f"{path}.{k}" if path else k) for k, v in node["properties"].items()}
        return node

    return walk(schema, ""), nullable


def _restore_nulls(obj, nullable: set[str], path=""):
    if isinstance(obj, dict):
        return {k: _restore_nulls(v, nullable, f"{path}.{k}" if path else k) for k, v in obj.items()}
    if path in nullable and obj in ("", 0):
        return None
    return obj


CLAUDE_MODELS = {
    "claude-opus-5-5": "Claude Opus 5.5（最準，約 USD 0.17／件）",
    "claude-sonnet-5-5": "Claude Sonnet 5.5（約 USD 0.08／件）",
    "claude-haiku-5-5": "Claude Haiku 5.5（最便宜，約 USD 0.01／件）",
}


def from_settings(settings: dict, provider: str | None = None, model: str | None = None,
                  api_key: str | None = None) -> LLM:
    cfg = settings["llm"]
    provider = provider or cfg["provider"]
    if provider == "ollama":
        o = cfg["ollama"]
        return Ollama(o["base_url"], model or o["model"], o.get("timeout", 300))
    if provider == "claude":
        c = cfg["claude"]
        return Claude(model or c["model"], c.get("effort", "low"), api_key=api_key)
    raise ValueError(f"不支援的 LLM provider：{provider}")
