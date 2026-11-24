"""系統產出一律用繁體（台灣用字）。廠商原始文件不轉換，證據引文保持原文。"""
from functools import lru_cache

from opencc import OpenCC

_CC = OpenCC("s2tw")
# OpenCC 對專有名詞的一對多字會選錯，這個領域裡「岳」幾乎都是人名或公司名
_FIX = {"嶽": "岳"}


@lru_cache(maxsize=4096)
def t(s: str) -> str:
    out = _CC.convert(s)
    for a, b in _FIX.items():
        out = out.replace(a, b)
    return out


def deep(obj):
    if isinstance(obj, str):
        return t(obj)
    if isinstance(obj, dict):
        return {k: deep(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep(v) for v in obj]
    return obj
