"""Tamaño de posición y apalancamiento mínimo para futuros lineales USDT-M (spec §9.1)."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PairRules:
    qty_step: float
    min_qty: float
    min_notional: float
    mmr: float


@dataclass(frozen=True)
class SizeResult:
    qty: float
    notional: float
    leverage: int
    margin: float
    risk_usdt: float
    loss_at_stop: float


class SizingBlocked(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


def size_position(
    bucket_equity: float,
    risk_pct: float,
    entry: float,
    stop: float,
    fee_in: float,
    fee_out: float,
    slippage_per_unit: float,
    rules: PairRules,
    max_positions: int,
    max_leverage: int,
) -> SizeResult:
    """Calcula la cantidad que pierde como máximo `risk_pct` del bucket si salta el stop.

    La cantidad se redondea siempre hacia abajo; el apalancamiento es el mínimo que cabe
    en el margen máximo por posición (bucket / max_positions).
    """
    risk_usdt = bucket_equity * risk_pct
    cost_per_unit = entry * fee_in + stop * fee_out + slippage_per_unit
    loss_per_unit = abs(entry - stop) + cost_per_unit
    if risk_usdt <= 0 or loss_per_unit <= 0:
        raise SizingBlocked("MIN_SIZE", "riesgo nulo")

    steps = math.floor(risk_usdt / loss_per_unit / rules.qty_step + 1e-9)
    if steps * rules.qty_step * loss_per_unit > risk_usdt:
        steps -= 1
    qty = round(steps * rules.qty_step, 12)
    notional = qty * entry
    if qty < rules.min_qty or notional < rules.min_notional:
        raise SizingBlocked("MIN_SIZE", f"cantidad {qty} por debajo del mínimo del par")

    max_margin = bucket_equity / max_positions
    leverage = max(1, math.ceil(notional / max_margin - 1e-9))
    if leverage > max_leverage:
        raise SizingBlocked("LEVERAGE", f"necesita {leverage}x, máximo {max_leverage}x")

    return SizeResult(
        qty=qty,
        notional=notional,
        leverage=leverage,
        margin=notional / leverage,
        risk_usdt=risk_usdt,
        loss_at_stop=qty * loss_per_unit,
    )
