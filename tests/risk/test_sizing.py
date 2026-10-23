import pytest
from hypothesis import given
from hypothesis import strategies as st

from tradesys.risk.sizing import PairRules, SizingBlocked, size_position

RULES = PairRules(qty_step=0.01, min_qty=0.01, min_notional=1.0, mmr=0.005)


def test_size_example_from_spec():
    r = size_position(500, 0.01, 100, 99, 0.0, 0.0002, 0.01, RULES, 3, 3)
    assert r.qty == pytest.approx(4.85)
    assert r.notional == pytest.approx(485.0)
    assert r.leverage == 3
    assert r.margin == pytest.approx(161.6667, rel=1e-4)
    assert r.risk_usdt == pytest.approx(5.0)
    assert r.loss_at_stop <= 5.0


def test_rounds_down_never_up():
    r = size_position(500, 0.01, 100, 99, 0, 0, 0, RULES, 3, 3)
    assert r.qty == pytest.approx(5.0)


def test_short_side_symmetric():
    r = size_position(500, 0.01, 100, 101, 0, 0, 0, RULES, 3, 3)
    assert r.qty == pytest.approx(5.0)


def test_min_size_blocks():
    with pytest.raises(SizingBlocked, match="MIN_SIZE"):
        size_position(10, 0.0025, 100, 50, 0, 0, 0, RULES, 3, 3)


def test_min_notional_blocks():
    rules = PairRules(qty_step=0.01, min_qty=0.01, min_notional=10.0, mmr=0.005)
    with pytest.raises(SizingBlocked, match="MIN_SIZE"):
        size_position(500, 0.0025, 100, 50, 0, 0, 0, rules, 3, 3)  # qty 0.02 -> 2 USDT


def test_leverage_over_mode_max_blocks():
    with pytest.raises(SizingBlocked, match="LEVERAGE"):
        size_position(500, 0.01, 100, 99.9, 0, 0, 0, RULES, 3, 3)


def test_zero_risk_blocks():
    with pytest.raises(SizingBlocked, match="MIN_SIZE"):
        size_position(500, 0.0, 100, 99, 0, 0, 0, RULES, 3, 3)


@given(
    equity=st.floats(10, 10_000),
    risk=st.floats(0.0025, 0.15),
    entry=st.floats(1, 100_000),
    dist=st.floats(0.001, 0.2),
    fee=st.floats(0, 0.001),
)
def test_loss_at_stop_never_exceeds_risk(equity, risk, entry, dist, fee):
    stop = entry * (1 - dist)
    try:
        r = size_position(equity, risk, entry, stop, fee, fee, 0.0, RULES, 3, 50)
    except SizingBlocked:
        return
    assert r.loss_at_stop <= r.risk_usdt + 1e-9
    assert r.qty >= RULES.min_qty
