"""Configuración del motor de riesgo (spec §9). Se carga desde config/risk.yaml."""

from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from tradesys.core.models import Bucket, Mode, Quality


class _Cfg(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BucketConfig(_Cfg):
    daily_loss_pct: float
    weekly_loss_pct: float
    loss_streak_to_shield: int
    allowed_modes: list[Mode]


class ModeConfig(_Cfg):
    risk_ceiling: float | dict[Bucket, float]
    max_leverage: int
    min_quality: Quality
    kelly_fraction: float
    max_session_hours: float | None = None


class IntradayLock(_Cfg):
    trigger_gain_pct: float
    risk_multiplier: float
    giveback_stop_pct: float


class RiskConfig(_Cfg):
    protected_initial_usdt: float
    floor_usdt: float
    week_starts: Literal["monday"]
    weekly_profit_to_bolsa_pct: float
    shield_duration_hours: float
    max_positions: int
    corr_threshold: float
    ticket_ttl_seconds: int
    stale_setup_fraction: float
    liq_stop_ratio: float
    drawdown_to_shield_pct: float
    ataque_min_week_pnl_pct: float
    max_total_notional_x: float = 10.0
    buckets: dict[Bucket, BucketConfig]
    modes: dict[Mode, ModeConfig]
    intraday_lock: IntradayLock

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not 0 < self.floor_usdt < self.protected_initial_usdt:
            raise ValueError("floor_usdt debe estar entre 0 y protected_initial_usdt")
        if set(self.buckets) != set(Bucket) or set(self.modes) != set(Mode):
            raise ValueError("faltan buckets o modos en la configuración")
        return self

    def risk_ceiling(self, mode: Mode, bucket: Bucket) -> float:
        if mode not in self.buckets[bucket].allowed_modes:
            raise ValueError(f"el modo {mode} no está permitido en el bucket {bucket}")
        ceiling = self.modes[mode].risk_ceiling
        return ceiling[bucket] if isinstance(ceiling, dict) else ceiling


def load_risk_config(path: Path) -> RiskConfig:
    return RiskConfig.model_validate(yaml.safe_load(Path(path).read_text()))
