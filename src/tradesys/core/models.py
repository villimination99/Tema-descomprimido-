"""Contratos de datos compartidos por todos los departamentos (spec §7)."""

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

Side = Literal["long", "short"]


class Quality(StrEnum):
    A_PLUS = "A+"
    A = "A"
    B = "B"


class Mode(StrEnum):
    ESCUDO = "ESCUDO"
    NORMAL = "NORMAL"
    ATAQUE = "ATAQUE"
    TURBO = "TURBO"


class Bucket(StrEnum):
    PROTECTED = "protected"
    BOLSA = "bolsa"


class Verdict(StrEnum):
    PASS = "PASS"
    BLOCK = "BLOCK"


class Stage(StrEnum):
    """Estado de una estrategia en el embudo de validación (spec §8)."""

    G0 = "G0"
    G1 = "G1"
    G2 = "G2"
    G3 = "G3"
    G4 = "G4"
    G5 = "G5"
    G6 = "G6"
    G7_IN_PROGRESS = "G7_IN_PROGRESS"
    G7 = "G7"
    G8 = "G8"

    def rank(self) -> int:
        return list(Stage).index(self)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class Candle(_Frozen):
    symbol: str
    tf: str
    ts_open: AwareDatetime
    o: float
    h: float
    l: float  # noqa: E741
    c: float
    v: float
    quote_v: float
    n_trades: int
    source: str


class Trade(_Frozen):
    symbol: str
    ts: AwareDatetime
    price: float
    qty: float
    side: Literal["buy", "sell"]
    trade_id: str


class Funding(_Frozen):
    symbol: str
    ts: AwareDatetime
    rate: float
    next_ts: AwareDatetime
    predicted_rate: float | None = None


class OpenInterest(_Frozen):
    symbol: str
    ts: AwareDatetime
    oi: float


class Setup(_Frozen):
    setup_id: str
    strategy_id: str
    symbol: str
    side: Side
    entry_type: Literal["limit", "stop"]
    entry: float
    stop: float
    tp: list[float]
    invalidation: float
    expires_at: AwareDatetime
    quality: Quality
    reason: str
    source: Literal["internal", "tradingview"]

    @model_validator(mode="after")
    def _check_sides(self) -> Self:
        sign = 1 if self.side == "long" else -1
        if sign * (self.entry - self.stop) <= 0:
            raise ValueError("el stop debe estar en el lado de pérdida de la entrada")
        if any(sign * (t - self.entry) <= 0 for t in self.tp):
            raise ValueError("los objetivos deben estar en el lado de ganancia de la entrada")
        return self


class RiskDecision(_Frozen):
    setup_id: str
    verdict: Verdict
    reasons: list[str]
    mode: Mode | None = None
    bucket: Bucket | None = None
    risk_usdt: float = 0.0
    qty: float = 0.0
    leverage: int = 0
    liq_price: float | None = None
    ticket_hash: str | None = None
    valid_until: datetime | None = None


class Order(_Frozen):
    client_order_id: str
    ticket_hash: str
    symbol: str
    side: Literal["buy", "sell"]
    type: Literal["limit", "market", "stop"]
    price: float | None
    qty: float
    reduce_only: bool = False
    post_only: bool = False


class Fill(_Frozen):
    client_order_id: str
    exch_order_id: str
    ts: AwareDatetime
    price: float
    qty: float
    fee: float
    fee_asset: str


class ScenarioItem(_Frozen):
    name: str
    prob: float
    mfe_R: float
    mae_R: float
    eta_minutes: float


class ScenarioReport(_Frozen):
    position_id: str
    ts: AwareDatetime
    n_paths: int
    scenarios: list[ScenarioItem]
    exp_R: float
    chosen_exit_policy: str
    generator_weights: dict[str, float]


class ManageAction(_Frozen):
    position_id: str
    action: Literal["move_stop", "partial", "close", "add"]
    params: dict[str, float]
    reason: str
    scenario: str
