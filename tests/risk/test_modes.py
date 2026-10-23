from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from tradesys.core.models import Bucket, Mode, Stage
from tradesys.risk.modes import ModeSignals, ModeState, next_mode

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)
P, B = Bucket.PROTECTED, Bucket.BOLSA

CALM = ModeSignals(
    loss_streak=0,
    drawdown_from_peak=0.0,
    daily_breaker=False,
    macro_window=False,
    health_ok=True,
    shield_trigger_last_24h=False,
    regime="TENDENCIA_ALCISTA",
    best_strategy_stage=Stage.G8,
    week_pnl_pct=-0.05,
    bucket_equity=100.0,
    turbo_grant_until=None,
)
NORMAL = ModeState(mode=Mode.NORMAL, since=NOW - timedelta(days=1), shield_until=None)


def step(bucket, cfg, cur=NORMAL, **sig):
    return next_mode(bucket, cur, replace(CALM, **sig), cfg, NOW)


def test_two_losses_protected_to_shield_4h(cfg):
    s = step(P, cfg, loss_streak=2)
    assert s.mode is Mode.ESCUDO
    assert s.shield_until == NOW + timedelta(hours=4)


def test_bolsa_needs_three_losses(cfg):
    assert step(B, cfg, loss_streak=2, regime="RANGO").mode is Mode.NORMAL
    assert step(B, cfg, loss_streak=3).mode is Mode.ESCUDO


@pytest.mark.parametrize(
    "sig",
    [
        {"macro_window": True},
        {"health_ok": False},
        {"drawdown_from_peak": 0.15},
        {"daily_breaker": True},
        {"regime": "CAOS"},
    ],
)
def test_shield_triggers(cfg, sig):
    assert step(P, cfg, **sig).mode is Mode.ESCUDO
    assert step(B, cfg, **sig).mode is Mode.ESCUDO


def test_shield_exits_after_4h_without_triggers(cfg):
    cur = ModeState(Mode.ESCUDO, NOW - timedelta(hours=5), NOW - timedelta(seconds=1))
    assert step(P, cfg, cur=cur).mode is Mode.NORMAL


def test_shield_holds_before_4h(cfg):
    cur = ModeState(Mode.ESCUDO, NOW - timedelta(hours=1), NOW + timedelta(hours=3))
    assert step(P, cfg, cur=cur).mode is Mode.ESCUDO


def test_shield_does_not_exit_while_trigger_persists(cfg):
    cur = ModeState(Mode.ESCUDO, NOW - timedelta(hours=5), NOW - timedelta(seconds=1))
    s = step(P, cfg, cur=cur, macro_window=True)
    assert s.mode is Mode.ESCUDO
    assert s.shield_until == NOW + timedelta(hours=4)


def test_protected_never_ataque(cfg):
    assert step(P, cfg).mode is Mode.NORMAL
    assert step(P, cfg, turbo_grant_until=NOW + timedelta(hours=2)).mode is Mode.NORMAL


def test_ataque_when_all_conditions(cfg):
    assert step(B, cfg).mode is Mode.ATAQUE


@pytest.mark.parametrize(
    "sig",
    [
        {"bucket_equity": 0.0},
        {"best_strategy_stage": Stage.G7},
        {"regime": "RANGO"},
        {"shield_trigger_last_24h": True},
        {"week_pnl_pct": -0.11},
        {"loss_streak": 1},
    ],
)
def test_ataque_requires_all(cfg, sig):
    assert step(B, cfg, **sig).mode is Mode.NORMAL


def test_expansion_allows_ataque(cfg):
    assert step(B, cfg, regime="EXPANSION").mode is Mode.ATAQUE


def test_turbo_needs_grant_and_expires(cfg):
    assert step(B, cfg, turbo_grant_until=NOW + timedelta(hours=2)).mode is Mode.TURBO
    assert step(B, cfg, turbo_grant_until=NOW).mode is Mode.ATAQUE


def test_turbo_session_max_4h(cfg):
    cur = ModeState(Mode.TURBO, NOW - timedelta(hours=4, seconds=1), None)
    s = step(B, cfg, cur=cur, turbo_grant_until=NOW + timedelta(hours=8))
    assert s.mode is Mode.ATAQUE


def test_downgrade_immediate(cfg):
    cur = ModeState(Mode.ATAQUE, NOW - timedelta(hours=1), None)
    assert step(B, cfg, cur=cur, macro_window=True).mode is Mode.ESCUDO


def test_since_kept_when_unchanged(cfg):
    assert step(P, cfg).since == NORMAL.since
