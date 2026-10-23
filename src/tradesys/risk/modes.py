"""Máquina de modos de riesgo por bucket: Escudo, Normal, Ataque, Turbo (spec §9.5).

Bajar es inmediato; subir exige todas las condiciones.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from tradesys.config.risk import RiskConfig
from tradesys.core.models import Bucket, Mode, Stage

ATTACK_REGIMES = frozenset({"TENDENCIA_ALCISTA", "TENDENCIA_BAJISTA", "EXPANSION"})


@dataclass(frozen=True)
class ModeSignals:
    loss_streak: int
    drawdown_from_peak: float
    daily_breaker: bool
    macro_window: bool
    health_ok: bool
    shield_trigger_last_24h: bool
    regime: str
    best_strategy_stage: Stage
    week_pnl_pct: float
    bucket_equity: float
    turbo_grant_until: datetime | None


@dataclass(frozen=True)
class ModeState:
    mode: Mode
    since: datetime
    shield_until: datetime | None


def shield_triggered(bucket: Bucket, s: ModeSignals, cfg: RiskConfig) -> bool:
    return (
        s.loss_streak >= cfg.buckets[bucket].loss_streak_to_shield
        or s.drawdown_from_peak >= cfg.drawdown_to_shield_pct - 1e-12
        or s.daily_breaker
        or s.macro_window
        or not s.health_ok
        or s.regime == "CAOS"
    )


def _attack_ok(s: ModeSignals, cfg: RiskConfig) -> bool:
    return (
        s.bucket_equity > 0
        and s.best_strategy_stage is Stage.G8
        and s.regime in ATTACK_REGIMES
        and not s.shield_trigger_last_24h
        and s.week_pnl_pct >= cfg.ataque_min_week_pnl_pct
        and s.loss_streak == 0
    )


def next_mode(
    bucket: Bucket, cur: ModeState, s: ModeSignals, cfg: RiskConfig, now: datetime
) -> ModeState:
    def to(mode: Mode, shield_until: datetime | None = None) -> ModeState:
        since = cur.since if mode is cur.mode else now
        return ModeState(mode=mode, since=since, shield_until=shield_until)

    if shield_triggered(bucket, s, cfg):
        return to(Mode.ESCUDO, now + timedelta(hours=cfg.shield_duration_hours))
    if cur.mode is Mode.ESCUDO and cur.shield_until is not None and now < cur.shield_until:
        return to(Mode.ESCUDO, cur.shield_until)

    allowed = cfg.buckets[bucket].allowed_modes
    candidates: list[Mode] = []
    if _attack_ok(s, cfg):
        turbo_cfg = cfg.modes[Mode.TURBO]
        session_ok = not (
            cur.mode is Mode.TURBO
            and turbo_cfg.max_session_hours is not None
            and now - cur.since > timedelta(hours=turbo_cfg.max_session_hours)
        )
        if s.turbo_grant_until is not None and now < s.turbo_grant_until and session_ok:
            candidates.append(Mode.TURBO)
        candidates.append(Mode.ATAQUE)
    candidates.append(Mode.NORMAL)
    for mode in candidates:
        if mode in allowed:
            return to(mode)
    return to(Mode.ESCUDO, cur.shield_until)
