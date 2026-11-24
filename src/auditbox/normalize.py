import re
import unicodedata
from datetime import date, datetime

from .zh import t

CURRENCY = {
    "RMB": "RMB", "CNY": "RMB", "人民币": "RMB", "人民幣": "RMB", "¥": "RMB", "￥": "RMB",
    "TWD": "TWD", "NTD": "TWD", "NT$": "TWD", "新台幣": "TWD", "新臺幣": "TWD", "新台币": "TWD",
    "USD": "USD", "US$": "USD", "美元": "USD", "美金": "USD",
}
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
                                      "dec"], 1)}


def currency(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip().upper()
    for k, v in CURRENCY.items():
        if k.upper() in s:
            return v
    return s or None


def amount(s) -> float | None:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    m = re.search(r"-?\d[\d.,]*", str(s).replace(" ", ""))
    if not m:
        return None
    num = m.group().rstrip(".,")
    neg, num = num.startswith("-"), num.lstrip("-")
    seps = [c for c in num if c in ".,"]
    if seps:
        last = max(num.rfind("."), num.rfind(","))
        tail = num[last + 1:]
        # 只有一種符號且出現多次、最後一段剛好 3 位 → 全是千分位（1.234.567、1,234,567）
        # 其餘情況最後一個符號是小數點（46,200.00、46.200,00、掃描誤讀的 46.200.00）
        if len(set(seps)) == 1 and (len(seps) > 1 or seps[0] == ",") and len(tail) == 3:
            num = re.sub(r"[.,]", "", num)
        else:
            num = re.sub(r"[.,]", "", num[:last]) + "." + tail
    v = float(num)
    return -v if neg else v


def iso_date(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    m = re.search(r"(\d{4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})", s)
    if m:
        return date(*map(int, m.groups())).isoformat()
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?,?\s+(\d{4})", s)
    if m and m.group(2).lower() in MONTHS:
        return date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
    try:
        return datetime.fromisoformat(s).date().isoformat()
    except ValueError:
        return None


def pattern(s: str | None, regex: str) -> str | None:
    if not s:
        return None
    m = re.search(regex, str(s).upper().replace(" ", ""))
    return m.group() if m else str(s).strip()


def text(s: str | None) -> str | None:
    return re.sub(r"\s+", " ", s).strip() if s else None


def integer(s) -> int | None:
    if s is None:
        return None
    m = re.search(r"\d{1,3}(?:[.,]\d{3})+(?!\d)|\d+", str(s).replace(" ", ""))
    return int(re.sub(r"[.,]", "", m.group())) if m else None


def squash(s: str) -> str:
    # 簡繁一律轉成繁體再比對，主檔用繁體、大陸廠商文件用簡體也能對上
    s = t(unicodedata.normalize("NFKC", s or ""))
    return re.sub(r"\s+", "", re.sub(r"[‐-―−]", "-", s)).lower()
