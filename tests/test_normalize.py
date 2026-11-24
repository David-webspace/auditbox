import pytest

from auditbox import normalize as N


@pytest.mark.parametrize("raw,want", [
    ("46,200.00", 46200), ("USD 46,200.00", 46200), ("1,286,000.00", 1286000), ("NT$ 742,000", 742000),
    ("46.200,00", 46200),          # 歐式寫法
    ("46.200.00", 46200),          # 掃描檔把逗號誤讀成句點
    ("1.234.567", 1234567), ("1,234,567", 1234567),
    ("23750", 23750), ("0.05", 0.05), ("12,5", 12.5), ("-1,200.50", -1200.5),
])
def test_amount_formats(raw, want):
    assert N.amount(raw) == want


def test_squash_matches_simplified_and_traditional():
    assert N.squash("东莞恒岳精密模具有限公司") == N.squash("東莞恆岳精密模具有限公司")
