"""Libro de capital: capital protegido + bolsa de ganancias, disyuntores, suelo y trinquete.

Spec §1b y §9.4. Todas las fechas en UTC; `now` siempre llega como parámetro.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta

from tradesys.config.risk import RiskConfig
from tradesys.core.models import Bucket

_EPS = 1e-9


@dataclass
class BucketState:
    equity: float
    peak: float
    day_start: float
    week_start: float
    loss_streak: int = 0
    paused_until: datetime | None = None
    weekly_review: bool = False
    ratchet_basis: float = 0.0


@dataclass
class LedgerStatus:
    halted: bool
    paused: dict[Bucket, bool]
    reasons: list[str] = field(default_factory=list)


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())  # lunes


def _next_midnight(now: datetime) -> datetime:
    return datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=UTC)


class Ledger:
    def __init__(self, cfg: RiskConfig, now: datetime) -> None:
        self.cfg = cfg
        init = cfg.protected_initial_usdt
        self.buckets: dict[Bucket, BucketState] = {
            Bucket.PROTECTED: BucketState(equity=init, peak=init, day_start=init, week_start=init),
            Bucket.BOLSA: BucketState(equity=0.0, peak=0.0, day_start=0.0, week_start=0.0),
        }
        self.day: date = now.date()
        self.day_peak_gain: float = 0.0
        self.day_locked: bool = False

    # --- consultas -------------------------------------------------------------------
    def equity(self, bucket: Bucket) -> float:
        return self.buckets[bucket].equity

    def loss_streak(self, bucket: Bucket) -> int:
        return self.buckets[bucket].loss_streak

    def drawdown_from_peak(self, bucket: Bucket) -> float:
        b = self.buckets[bucket]
        return 0.0 if b.peak <= 0 else (b.peak - b.equity) / b.peak

    def status(self, now: datetime) -> LedgerStatus:
        self.roll(now)
        reasons: list[str] = []
        prot = self.buckets[Bucket.PROTECTED]
        halted = prot.equity <= self.cfg.floor_usdt + _EPS
        if halted:
            reasons.append(f"FLOOR: capital protegido {prot.equity:.2f} <= {self.cfg.floor_usdt}")
        paused: dict[Bucket, bool] = {}
        for bucket, b in self.buckets.items():
            daily = b.paused_until is not None and now < b.paused_until
            if daily:
                reasons.append(f"DAILY_BREAKER: {bucket} hasta {b.paused_until.isoformat()}")
            if b.weekly_review:
                reasons.append(f"WEEKLY_REVIEW: {bucket} necesita revisión humana")
            paused[bucket] = halted or daily or b.weekly_review
        return LedgerStatus(halted=halted, paused=paused, reasons=reasons)

    def intraday_risk_multiplier(self, now: datetime) -> float:
        self.roll(now)
        if self.day_locked:
            return 0.0
        lock = self.cfg.intraday_lock
        prot = self.buckets[Bucket.PROTECTED]
        if self.day_peak_gain >= lock.trigger_gain_pct * prot.day_start - _EPS:
            return lock.risk_multiplier
        return 1.0

    # --- cambios ---------------------------------------------------------------------
    def record_trade(self, bucket: Bucket, pnl: float, ts: datetime) -> None:
        self.roll(ts)
        b = self.buckets[bucket]
        b.equity = max(0.0, b.equity + pnl)  # la bolsa nunca puede deber al capital protegido
        b.peak = max(b.peak, b.equity)
        if pnl < 0:
            b.loss_streak += 1
        elif pnl > 0:
            b.loss_streak = 0

        bcfg = self.cfg.buckets[bucket]
        if b.day_start - b.equity >= bcfg.daily_loss_pct * b.day_start - _EPS and pnl < 0:
            b.paused_until = _next_midnight(ts)
        if b.week_start - b.equity >= bcfg.weekly_loss_pct * b.week_start - _EPS and pnl < 0:
            b.weekly_review = True

        if bucket is Bucket.PROTECTED:
            self._update_intraday_lock(b)
        else:
            self._apply_ratchet()

    def roll(self, now: datetime) -> None:
        today = now.date()
        if today <= self.day:
            return
        if _week_start(today) > _week_start(self.day):
            self._close_week()
        for b in self.buckets.values():
            b.day_start = b.equity
        self.day = today
        self.day_peak_gain = 0.0
        self.day_locked = False

    def human_resume(self, now: datetime) -> None:
        """El dueño revisó: levanta las pausas semanales (el suelo se sigue comprobando)."""
        for b in self.buckets.values():
            b.weekly_review = False
            b.paused_until = None

    # --- internos --------------------------------------------------------------------
    def _close_week(self) -> None:
        prot = self.buckets[Bucket.PROTECTED]
        bolsa = self.buckets[Bucket.BOLSA]
        gain = prot.equity - prot.week_start
        if gain > 0:
            moved = gain * self.cfg.weekly_profit_to_bolsa_pct
            prot.equity -= moved
            bolsa.equity += moved
            bolsa.ratchet_basis += moved
            bolsa.peak = max(bolsa.peak, bolsa.equity)
        for b in self.buckets.values():
            b.week_start = b.equity

    def _apply_ratchet(self) -> None:
        bolsa = self.buckets[Bucket.BOLSA]
        if bolsa.ratchet_basis > 0 and bolsa.equity >= 2 * bolsa.ratchet_basis - _EPS:
            back = (bolsa.equity - bolsa.ratchet_basis) * 0.5
            bolsa.equity -= back
            self.buckets[Bucket.PROTECTED].equity += back
            bolsa.ratchet_basis = bolsa.equity

    def _update_intraday_lock(self, prot: BucketState) -> None:
        gain = prot.equity - prot.day_start
        self.day_peak_gain = max(self.day_peak_gain, gain)
        lock = self.cfg.intraday_lock
        triggered = self.day_peak_gain >= lock.trigger_gain_pct * prot.day_start - _EPS
        if triggered and gain <= self.day_peak_gain * (1 - lock.giveback_stop_pct) + _EPS:
            self.day_locked = True

    # --- persistencia ----------------------------------------------------------------
    def to_json(self) -> str:
        def enc(b: BucketState) -> dict:
            d = asdict(b)
            d["paused_until"] = b.paused_until.isoformat() if b.paused_until else None
            return d

        return json.dumps(
            {
                "buckets": {k.value: enc(v) for k, v in self.buckets.items()},
                "day": self.day.isoformat(),
                "day_peak_gain": self.day_peak_gain,
                "day_locked": self.day_locked,
            }
        )

    @classmethod
    def from_json(cls, cfg: RiskConfig, raw: str) -> "Ledger":
        data = json.loads(raw)
        day = date.fromisoformat(data["day"])
        led = cls(cfg, datetime.combine(day, datetime.min.time(), tzinfo=UTC))
        for k, v in data["buckets"].items():
            if v["paused_until"]:
                v["paused_until"] = datetime.fromisoformat(v["paused_until"])
            led.buckets[Bucket(k)] = BucketState(**v)
        led.day_peak_gain = data["day_peak_gain"]
        led.day_locked = data["day_locked"]
        return led
