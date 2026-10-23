"""Comprobación de distancia a liquidación con margen aislado (spec §9.3)."""

from tradesys.core.models import Side


def liq_price(entry: float, leverage: int, mmr: float, side: Side) -> float:
    if side == "long":
        return entry * (1 - 1 / leverage + mmr)
    return entry * (1 + 1 / leverage - mmr)


def stop_is_safe(entry: float, stop: float, liq: float, ratio: float = 0.5) -> bool:
    """El stop debe saltar mucho antes que la liquidación: |entrada-stop| <= ratio*|entrada-liq|."""
    return abs(entry - stop) <= ratio * abs(entry - liq)


def safe_leverage(
    entry: float, stop: float, mmr: float, side: Side, start: int, ratio: float = 0.5
) -> int | None:
    """Mayor apalancamiento <= `start` que cumple la regla; None si ni 1x la cumple."""
    for lev in range(start, 0, -1):
        if stop_is_safe(entry, stop, liq_price(entry, lev, mmr, side), ratio):
            return lev
    return None
