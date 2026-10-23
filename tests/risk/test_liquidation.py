import pytest

from tradesys.risk.liquidation import liq_price, safe_leverage, stop_is_safe


def test_liq_long():
    assert liq_price(100, 10, 0.005, "long") == pytest.approx(90.5)


def test_liq_short():
    assert liq_price(100, 10, 0.005, "short") == pytest.approx(109.5)


def test_stop_safe():
    assert stop_is_safe(100, 96, 90.5)


def test_stop_unsafe():
    assert not stop_is_safe(100, 95, 90.5)


def test_safe_leverage_lowers():
    lev = safe_leverage(100, 95, 0.005, "long", start=10)
    assert lev is not None and lev < 10
    assert stop_is_safe(100, 95, liq_price(100, lev, 0.005, "long"))


def test_safe_leverage_short():
    lev = safe_leverage(100, 105, 0.005, "short", start=10)
    assert lev is not None and lev < 10


def test_none_when_impossible():
    assert safe_leverage(100, 40, 0.005, "long", start=3) is None
