"""Puerta de riesgo PASS/BLOCK (spec §9.6). Única autoridad que autoriza y dimensiona órdenes.

Las reglas se comprueban en orden y se devuelve el primer motivo que falla.
"""

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from tradesys.config.risk import RiskConfig
from tradesys.core.models import Bucket, Mode, Quality, RiskDecision, Setup, Stage, Verdict
from tradesys.risk.kelly import kelly_cap
from tradesys.risk.ledger import LedgerStatus
from tradesys.risk.liquidation import liq_price, safe_leverage
from tradesys.risk.modes import ModeState
from tradesys.risk.sizing import PairRules, SizeResult, SizingBlocked, size_position

_QUALITY_RANK = {Quality.B: 0, Quality.A: 1, Quality.A_PLUS: 2}
_ATTACK_MODES = (Mode.ATAQUE, Mode.TURBO)


@dataclass(frozen=True)
class OpenPosition:
    symbol: str
    bucket: Bucket
    risk_usdt: float
    corr_with_new: float


@dataclass(frozen=True)
class GateContext:
    setup: Setup
    exp_R: float
    current_price: float
    now: datetime
    ledger: LedgerStatus
    equities: dict[Bucket, float]
    modes: dict[Bucket, ModeState]
    strategy_stage: Stage
    strategy_regimes: set[str]
    regime: str
    open_positions: list[OpenPosition]
    rules: PairRules
    fee_in: float
    fee_out: float
    slippage_per_unit: float
    kelly_p_low: float
    kelly_b_low: float
    intraday_multiplier: float


def choose_bucket(ctx: GateContext) -> Bucket:
    """La bolsa de ganancias solo recibe setups A+ de estrategias en G8 con la bolsa en ataque."""
    if (
        ctx.setup.quality is Quality.A_PLUS
        and ctx.strategy_stage is Stage.G8
        and ctx.modes[Bucket.BOLSA].mode in _ATTACK_MODES
        and ctx.equities[Bucket.BOLSA] > 0
    ):
        return Bucket.BOLSA
    return Bucket.PROTECTED


def ticket_hash(d: RiskDecision, setup: Setup) -> str:
    payload = {
        "setup": setup.model_dump(mode="json"),
        "decision": d.model_dump(mode="json", exclude={"ticket_hash"}),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def is_ticket_valid(d: RiskDecision, now: datetime) -> bool:
    return d.verdict is Verdict.PASS and d.valid_until is not None and now < d.valid_until


def evaluate(ctx: GateContext, cfg: RiskConfig) -> RiskDecision:
    s = ctx.setup

    def block(reason: str, **extra) -> RiskDecision:
        return RiskDecision(setup_id=s.setup_id, verdict=Verdict.BLOCK, reasons=[reason], **extra)

    # 1. Sistema detenido
    if ctx.ledger.halted:
        return block("HALTED: sistema detenido (suelo o KILL)")

    bucket = choose_bucket(ctx)
    mode = ctx.modes[bucket].mode
    tag = {"mode": mode, "bucket": bucket}

    # 2. Estado de la estrategia en el embudo
    if ctx.strategy_stage.rank() < Stage.G7_IN_PROGRESS.rank():
        return block(f"STAGE: estrategia en {ctx.strategy_stage}, no apta para vivo", **tag)
    in_g7 = ctx.strategy_stage is Stage.G7_IN_PROGRESS
    if in_g7 and mode is not Mode.NORMAL:
        return block("STAGE: G7 en curso solo opera en modo NORMAL", **tag)

    # 3. Calidad mínima del modo (B nunca se opera)
    min_q = cfg.modes[mode].min_quality
    if s.quality is Quality.B or _QUALITY_RANK[s.quality] < _QUALITY_RANK[min_q]:
        return block(f"QUALITY: {s.quality} por debajo de {min_q} en {mode}", **tag)

    # 4. Régimen permitido
    if ctx.regime not in ctx.strategy_regimes:
        return block(f"REGIME: {ctx.regime} no permitido para {s.strategy_id}", **tag)

    # 5. Disyuntores del bucket y bloqueo intradía
    if ctx.ledger.paused[bucket]:
        return block(f"BREAKER: bucket {bucket} en pausa", **tag)
    intraday = ctx.intraday_multiplier if bucket is Bucket.PROTECTED else 1.0
    if intraday <= 0:
        return block("BREAKER: día parado por devolver ganancias", **tag)

    # Riesgo permitido: medio Kelly pesimista, techo del modo, bloqueo intradía
    equity = ctx.equities[bucket]
    ceiling = cfg.risk_ceiling(mode, bucket)
    cap = kelly_cap(ctx.kelly_p_low, ctx.kelly_b_low, cfg.modes[mode].kelly_fraction)
    risk_pct = min(cap, ceiling) * intraday
    risk_usdt = equity * risk_pct

    # 6. Exposición: número de posiciones y riesgo correlacionado
    if len(ctx.open_positions) >= cfg.max_positions:
        return block(f"EXPOSURE: ya hay {len(ctx.open_positions)} posiciones abiertas", **tag)
    corr_risk = sum(p.risk_usdt for p in ctx.open_positions if p.corr_with_new > cfg.corr_threshold)
    if corr_risk > 0 and corr_risk + risk_usdt > ceiling * equity + 1e-9:
        return block("EXPOSURE: riesgo correlacionado por encima del techo del modo", **tag)

    # 7. Tamaño (Kelly <= 0: la estrategia no tiene ventaja demostrada)
    if cap <= 0:
        return block("NEG_EXPECTANCY: Kelly <= 0 con la estimación pesimista", **tag)
    try:
        size = size_position(
            equity,
            risk_pct,
            s.entry,
            s.stop,
            ctx.fee_in,
            ctx.fee_out,
            ctx.slippage_per_unit,
            ctx.rules,
            cfg.max_positions,
            cfg.modes[mode].max_leverage,
        )
    except SizingBlocked as e:
        return block(f"{e.reason}: {e}", **tag)
    if in_g7:
        size = _min_size(size, s, ctx, cfg)

    # 8. Liquidación lejos del stop
    safe = safe_leverage(s.entry, s.stop, ctx.rules.mmr, s.side, size.leverage, cfg.liq_stop_ratio)
    if safe is None or safe < size.leverage:
        return block("LIQUIDATION: el stop queda demasiado cerca de la liquidación", **tag)

    # 9. Expectativa tras costes
    if ctx.exp_R <= 0:
        return block(f"NEG_EXPECTANCY: R esperado {ctx.exp_R:.3f} <= 0", **tag)

    # 10. Setup caducado por el precio
    if abs(ctx.current_price - s.entry) > cfg.stale_setup_fraction * abs(s.entry - s.stop) + 1e-9:
        return block("STALE: el precio se alejó de la entrada", **tag)

    # 11. PASS con ticket firmado
    decision = RiskDecision(
        setup_id=s.setup_id,
        verdict=Verdict.PASS,
        reasons=[],
        mode=mode,
        bucket=bucket,
        risk_usdt=size.risk_usdt,
        qty=size.qty,
        leverage=size.leverage,
        liq_price=liq_price(s.entry, size.leverage, ctx.rules.mmr, s.side),
        valid_until=ctx.now + timedelta(seconds=cfg.ticket_ttl_seconds),
    )
    return decision.model_copy(update={"ticket_hash": ticket_hash(decision, s)})


def _min_size(size: SizeResult, s: Setup, ctx: GateContext, cfg: RiskConfig) -> SizeResult:
    """G7 en curso: siempre el tamaño mínimo del par (nunca mayor que el calculado)."""
    qty = ctx.rules.min_qty
    notional = qty * s.entry
    max_margin = ctx.equities[Bucket.PROTECTED] / cfg.max_positions
    leverage = max(1, math.ceil(notional / max_margin - 1e-9))
    return SizeResult(
        qty=qty,
        notional=notional,
        leverage=leverage,
        margin=notional / leverage,
        risk_usdt=size.risk_usdt,
        loss_at_stop=qty * size.loss_at_stop / size.qty,
    )
