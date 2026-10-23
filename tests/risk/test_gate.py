from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from tradesys.core.models import Bucket, Mode, Quality, Setup, Stage, Verdict
from tradesys.risk.gate import (
    GateContext,
    OpenPosition,
    choose_bucket,
    evaluate,
    is_ticket_valid,
)
from tradesys.risk.ledger import LedgerStatus
from tradesys.risk.modes import ModeState
from tradesys.risk.sizing import PairRules

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)
P, B = Bucket.PROTECTED, Bucket.BOLSA
RULES = PairRules(qty_step=0.01, min_qty=0.01, min_notional=1.0, mmr=0.005)


def mode(m: Mode) -> ModeState:
    return ModeState(mode=m, since=NOW - timedelta(days=1), shield_until=None)


def setup(**kw) -> Setup:
    base = dict(
        setup_id="s1",
        strategy_id="S1",
        symbol="BTC_USDT",
        side="long",
        entry_type="limit",
        entry=100.0,
        stop=99.0,
        tp=[102.0],
        invalidation=98.5,
        expires_at=NOW + timedelta(hours=1),
        quality=Quality.A,
        reason="test",
        source="internal",
    )
    base.update(kw)
    return Setup(**base)


@pytest.fixture
def ok_ctx() -> GateContext:
    return GateContext(
        setup=setup(),
        exp_R=0.5,
        current_price=100.0,
        now=NOW,
        ledger=LedgerStatus(halted=False, paused={P: False, B: False}),
        equities={P: 500.0, B: 0.0},
        modes={P: mode(Mode.NORMAL), B: mode(Mode.NORMAL)},
        strategy_stage=Stage.G7,
        strategy_regimes={"TENDENCIA_ALCISTA"},
        regime="TENDENCIA_ALCISTA",
        open_positions=[],
        rules=RULES,
        fee_in=0.0,
        fee_out=0.0002,
        slippage_per_unit=0.01,
        kelly_p_low=0.5,
        kelly_b_low=2.0,
        intraday_multiplier=1.0,
    )


def blocked(ctx, cfg) -> str:
    d = evaluate(ctx, cfg)
    assert d.verdict is Verdict.BLOCK
    return d.reasons[0]


def test_pass_has_ticket(ok_ctx, cfg):
    d = evaluate(ok_ctx, cfg)
    assert d.verdict is Verdict.PASS, d.reasons
    assert d.bucket is P and d.mode is Mode.NORMAL
    assert d.qty == pytest.approx(4.85)
    assert d.leverage == 3
    assert d.risk_usdt == pytest.approx(5.0)
    assert d.ticket_hash is not None and len(d.ticket_hash) == 64
    assert d.valid_until == NOW + timedelta(seconds=60)


def test_ticket_expired_at_boundary(ok_ctx, cfg):
    d = evaluate(ok_ctx, cfg)
    assert is_ticket_valid(d, d.valid_until - timedelta(microseconds=1))
    assert not is_ticket_valid(d, d.valid_until)


def test_hash_changes_with_qty(ok_ctx, cfg):
    a = evaluate(ok_ctx, cfg)
    b = evaluate(replace(ok_ctx, equities={P: 400.0, B: 0.0}), cfg)
    assert a.ticket_hash != b.ticket_hash


def test_halted(ok_ctx, cfg):
    ctx = replace(ok_ctx, ledger=LedgerStatus(halted=True, paused={P: True, B: True}))
    assert blocked(ctx, cfg).startswith("HALTED")


def test_stage(ok_ctx, cfg):
    assert blocked(replace(ok_ctx, strategy_stage=Stage.G6), cfg).startswith("STAGE")


def test_quality_b_never(ok_ctx, cfg):
    ctx = replace(ok_ctx, setup=setup(quality=Quality.B))
    assert blocked(ctx, cfg).startswith("QUALITY")


def test_quality_a_in_escudo(ok_ctx, cfg):
    ctx = replace(ok_ctx, modes={P: mode(Mode.ESCUDO), B: mode(Mode.NORMAL)})
    assert blocked(ctx, cfg).startswith("QUALITY")


def test_regime(ok_ctx, cfg):
    assert blocked(replace(ok_ctx, regime="RANGO"), cfg).startswith("REGIME")


def test_breaker(ok_ctx, cfg):
    ctx = replace(ok_ctx, ledger=LedgerStatus(halted=False, paused={P: True, B: False}))
    assert blocked(ctx, cfg).startswith("BREAKER")


def test_intraday_day_stopped_is_breaker(ok_ctx, cfg):
    assert blocked(replace(ok_ctx, intraday_multiplier=0.0), cfg).startswith("BREAKER")


def test_exposure_max_positions(ok_ctx, cfg):
    opens = [OpenPosition(f"X{i}", P, 1.0, 0.0) for i in range(3)]
    assert blocked(replace(ok_ctx, open_positions=opens), cfg).startswith("EXPOSURE")


def test_exposure_correlated(ok_ctx, cfg):
    opens = [OpenPosition("ETH_USDT", P, 4.0, 0.8)]
    assert blocked(replace(ok_ctx, open_positions=opens), cfg).startswith("EXPOSURE")


def test_uncorrelated_allowed(ok_ctx, cfg):
    opens = [OpenPosition("ETH_USDT", P, 4.0, 0.2)]
    assert evaluate(replace(ok_ctx, open_positions=opens), cfg).verdict is Verdict.PASS


def test_min_size(ok_ctx, cfg):
    rules = PairRules(qty_step=0.01, min_qty=10.0, min_notional=1.0, mmr=0.005)
    assert blocked(replace(ok_ctx, rules=rules), cfg).startswith("MIN_SIZE")


def test_leverage(ok_ctx, cfg):
    ctx = replace(
        ok_ctx, setup=setup(stop=99.9, invalidation=99.8), fee_out=0.0, slippage_per_unit=0
    )
    assert blocked(ctx, cfg).startswith("LEVERAGE")


def test_liquidation(ok_ctx, cfg):
    ctx = replace(ok_ctx, setup=setup(stop=40.0, invalidation=39.0))
    assert blocked(ctx, cfg).startswith("LIQUIDATION")


def test_negative_expectancy(ok_ctx, cfg):
    assert blocked(replace(ok_ctx, exp_R=0.0), cfg).startswith("NEG_EXPECTANCY")


def test_kelly_non_positive(ok_ctx, cfg):
    ctx = replace(ok_ctx, kelly_p_low=0.3, kelly_b_low=1.0)
    assert blocked(ctx, cfg).startswith("NEG_EXPECTANCY")


def test_stale(ok_ctx, cfg):
    assert blocked(replace(ok_ctx, current_price=100.31), cfg).startswith("STALE")
    assert evaluate(replace(ok_ctx, current_price=100.3), cfg).verdict is Verdict.PASS


def test_order_of_rules(ok_ctx, cfg):
    ctx = replace(
        ok_ctx,
        ledger=LedgerStatus(halted=True, paused={P: True, B: True}),
        setup=setup(quality=Quality.B),
    )
    assert blocked(ctx, cfg).startswith("HALTED")


def test_g7_in_progress_min_size_normal_only(ok_ctx, cfg):
    d = evaluate(replace(ok_ctx, strategy_stage=Stage.G7_IN_PROGRESS), cfg)
    assert d.verdict is Verdict.PASS
    assert d.qty == pytest.approx(RULES.min_qty)
    assert d.mode is Mode.NORMAL
    ctx = replace(
        ok_ctx,
        strategy_stage=Stage.G7_IN_PROGRESS,
        setup=setup(quality=Quality.A_PLUS),
        modes={P: mode(Mode.ESCUDO), B: mode(Mode.NORMAL)},
    )
    assert blocked(ctx, cfg).startswith("STAGE")


def test_choose_bucket_bolsa_only_when_attack(ok_ctx):
    attack = replace(
        ok_ctx,
        setup=setup(quality=Quality.A_PLUS),
        strategy_stage=Stage.G8,
        equities={P: 500.0, B: 50.0},
        modes={P: mode(Mode.NORMAL), B: mode(Mode.ATAQUE)},
    )
    assert choose_bucket(attack) is B
    assert choose_bucket(replace(attack, setup=setup(quality=Quality.A))) is P
    assert choose_bucket(replace(attack, strategy_stage=Stage.G7)) is P
    assert choose_bucket(replace(attack, equities={P: 500.0, B: 0.0})) is P
    assert choose_bucket(replace(attack, modes={P: mode(Mode.NORMAL), B: mode(Mode.NORMAL)})) is P


def test_attack_bucket_uses_bolsa_equity(ok_ctx, cfg):
    ctx = replace(
        ok_ctx,
        setup=setup(quality=Quality.A_PLUS, stop=90.0, invalidation=89.0),
        strategy_stage=Stage.G8,
        equities={P: 500.0, B: 50.0},
        modes={P: mode(Mode.NORMAL), B: mode(Mode.ATAQUE)},
        fee_out=0.0,
        slippage_per_unit=0.0,
    )
    d = evaluate(ctx, cfg)
    assert d.verdict is Verdict.PASS, d.reasons
    assert d.bucket is B and d.mode is Mode.ATAQUE
    assert d.risk_usdt == pytest.approx(50 * 0.10)  # medio Kelly 0.125 > techo 0.10


def test_risk_uses_kelly_and_intraday(ok_ctx, cfg):
    d = evaluate(replace(ok_ctx, intraday_multiplier=0.5), cfg)
    assert d.risk_usdt == pytest.approx(2.5)
    d = evaluate(replace(ok_ctx, kelly_p_low=0.34, kelly_b_low=2.0), cfg)
    assert d.risk_usdt == pytest.approx(500 * 0.005)
