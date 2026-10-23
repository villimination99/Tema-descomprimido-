from datetime import UTC, datetime

import pytest

from tradesys.core.models import Bucket
from tradesys.risk.ledger import Ledger

P, B = Bucket.PROTECTED, Bucket.BOLSA


def t(day: int, h: int = 10, m: int = 0, s: int = 0) -> datetime:
    # 2026-10-19 es lunes
    return datetime(2026, 10, day, h, m, s, tzinfo=UTC)


@pytest.fixture
def led(cfg):
    return Ledger(cfg, t(19, 0))


def test_initial_state(led):
    assert led.equity(P) == 500
    assert led.equity(B) == 0
    assert not led.status(t(19)).halted


def test_floor_exact_halts(led):
    led.record_trade(P, -9, t(19))
    led.record_trade(P, -9, t(20))
    led.record_trade(P, -9, t(21))
    led.record_trade(P, -9, t(22))
    led.record_trade(P, -9, t(23))
    led.record_trade(P, -5, t(26))  # semana nueva, 455 -> 450
    st = led.status(t(26, 11))
    assert led.equity(P) == pytest.approx(450)
    assert st.halted
    assert any("FLOOR" in r for r in st.reasons)


def test_floor_survives_human_resume(led):
    led.record_trade(P, -9, t(19))
    led.record_trade(P, -9, t(20))
    led.record_trade(P, -9, t(21))
    led.record_trade(P, -9, t(22))
    led.record_trade(P, -9, t(23))
    led.record_trade(P, -5, t(26))
    led.human_resume(t(26, 12))
    assert led.status(t(26, 12)).halted


def test_daily_loss_protected_pauses_until_midnight(led):
    led.record_trade(P, -10, t(19, 10))
    assert led.status(t(19, 23, 59, 59)).paused[P]
    assert not led.status(t(20, 0, 0, 0)).paused[P]


def test_loss_at_235959_counts_for_that_day(led):
    led.record_trade(P, -6, t(19, 23, 59, 59))
    led.record_trade(P, -5, t(20, 0, 0, 0))
    assert not led.status(t(20, 0, 0, 1)).paused[P]


def test_weekly_loss_requires_human(led):
    led.record_trade(P, -9, t(19))
    led.record_trade(P, -9, t(20))
    led.record_trade(P, -2, t(21))
    st = led.status(t(21, 11))
    assert st.paused[P]
    assert any("WEEKLY_REVIEW" in r for r in st.reasons)
    assert led.status(t(27)).paused[P]  # ni el cambio de semana lo levanta
    led.human_resume(t(27))
    assert not led.status(t(27)).paused[P]


def test_weekly_profit_split(led):
    led.record_trade(P, 60, t(23))
    led.roll(t(26, 0))
    assert led.equity(P) == pytest.approx(530)
    assert led.equity(B) == pytest.approx(30)


def test_losing_week_no_transfer(led):
    led.record_trade(P, -10, t(23))
    led.roll(t(26, 0))
    assert led.equity(B) == 0


def test_bolsa_loss_never_touches_protected(led):
    led.record_trade(P, 60, t(23))
    led.roll(t(26, 0))
    led.record_trade(B, -30, t(26, 10))
    assert led.equity(B) == 0
    assert led.equity(P) == pytest.approx(530)
    assert led.status(t(26, 11)).paused[B]


def test_ratchet(led):
    led.record_trade(P, 60, t(23))
    led.roll(t(26, 0))  # bolsa base 30
    led.record_trade(B, 30, t(26, 10))  # bolsa 60 = 2x base
    assert led.equity(B) == pytest.approx(45)
    assert led.equity(P) == pytest.approx(545)


def test_intraday_lock(led):
    assert led.intraday_risk_multiplier(t(19, 9)) == 1.0
    led.record_trade(P, 10, t(19, 10))
    assert led.intraday_risk_multiplier(t(19, 10, 1)) == 0.5
    led.record_trade(P, -5, t(19, 11))
    assert led.intraday_risk_multiplier(t(19, 11, 1)) == 0.0
    assert led.intraday_risk_multiplier(t(20, 9)) == 1.0


def test_loss_streak_and_drawdown(led):
    led.record_trade(P, 10, t(19, 9))
    led.record_trade(P, -3, t(19, 10))
    led.record_trade(P, -3, t(19, 11))
    assert led.loss_streak(P) == 2
    assert led.drawdown_from_peak(P) == pytest.approx(6 / 510)
    led.record_trade(P, 1, t(19, 12))
    assert led.loss_streak(P) == 0


def test_persistence_roundtrip(led, cfg):
    led.record_trade(P, -10, t(19, 10))
    again = Ledger.from_json(cfg, led.to_json())
    assert again.equity(P) == led.equity(P)
    assert again.status(t(19, 12)).paused[P]
