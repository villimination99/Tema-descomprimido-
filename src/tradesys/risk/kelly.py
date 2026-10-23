"""Tope de riesgo por la ventaja medida: medio Kelly sobre estimaciones pesimistas (§9.2)."""

import math


def wilson_lower(wins: int, n: int, z: float = 1.96) -> float:
    """Límite inferior del intervalo de Wilson para la tasa de acierto."""
    if n <= 0:
        return 0.0
    p = wins / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (center - margin) / denom


def kelly(p: float, b: float) -> float:
    """Fracción de Kelly para acierto `p` y relación ganancia/pérdida `b`."""
    if b <= 0:
        return 0.0
    return p - (1 - p) / b


def kelly_cap(p_low: float, b_low: float, fraction: float) -> float:
    return max(0.0, fraction * kelly(p_low, b_low))


def risk_pct(p_low: float, b_low: float, fraction: float, ceiling: float) -> float:
    return min(kelly_cap(p_low, b_low, fraction), ceiling)
