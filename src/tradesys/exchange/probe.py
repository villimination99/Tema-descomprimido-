"""Sonda de capacidades reales de la cuenta MEXC (Fase 0).

Comprueba mercados, comisiones, balances y, solo con confirmación explícita, que se puede
crear y cancelar una orden mínima post-only lejos del mercado.
"""

import json
from pathlib import Path
from typing import Any, Literal

_SECRET_KEYS = {"apikey", "secret", "password", "token", "api_key", "api_secret"}
_PROBE_SYMBOLS = ("BTC/USDT", "BTC/USDT:USDT")


def make_exchange(market: Literal["spot", "swap"], auth: bool):
    import ccxt

    from tradesys.infra.secrets import get_secret

    params: dict[str, Any] = {"options": {"defaultType": market}, "enableRateLimit": True}
    if auth:
        params["apiKey"] = get_secret("mexc_api_key")
        params["secret"] = get_secret("mexc_api_secret")
    return ccxt.mexc(params)


def probe_public(ex) -> dict:
    markets = ex.load_markets()
    out: dict[str, Any] = {"n_markets": len(markets), "markets": {}}
    for symbol in _PROBE_SYMBOLS:
        m = markets.get(symbol)
        if m is None:
            continue
        info = m.get("info") or {}
        out["markets"][symbol] = {
            "precision": m.get("precision"),
            "min_amount": (m.get("limits") or {}).get("amount", {}).get("min"),
            "min_cost": (m.get("limits") or {}).get("cost", {}).get("min"),
            "contract_size": m.get("contractSize"),
            "mmr": info.get("maintenanceMarginRate"),
        }
    return out


def probe_private(ex) -> dict:
    out: dict[str, Any] = {}
    totals = ex.fetch_balance().get("total") or {}
    out["balances"] = {k: v for k, v in totals.items() if v}
    try:
        out["fees"] = ex.fetch_trading_fees()
    except Exception as e:  # noqa: BLE001 - la API puede no ofrecerlo
        out["fees"] = f"unknown ({e})"
    try:
        out["position_mode"] = ex.fetch_position_mode()
    except Exception:  # noqa: BLE001
        out["position_mode"] = "unknown"
    has = getattr(ex, "has", {}) or {}
    out["stop_supported"] = bool(has.get("createStopOrder"))
    return out


def probe_order(ex, symbol: str, confirm: str) -> dict:
    """Crea y cancela una orden mínima post-only al 50 % del precio. Exige confirm == 'SI'."""
    if confirm != "SI":
        raise PermissionError("la orden de prueba necesita la confirmación exacta 'SI'")
    market = ex.market(symbol)
    limits = market.get("limits") or {}
    price = float(ex.price_to_precision(symbol, ex.fetch_ticker(symbol)["last"] * 0.5))
    min_amount = (limits.get("amount") or {}).get("min") or 0.0
    min_cost = (limits.get("cost") or {}).get("min")
    amount = max(min_amount, (min_cost / price) * 1.05 if min_cost else 0.0)
    amount = float(ex.amount_to_precision(symbol, amount))

    result: dict[str, Any] = {"created": False, "cancelled": False, "error": None}
    order = ex.create_order(symbol, "limit", "buy", amount, price, {"postOnly": True})
    result["created"] = True
    try:
        ex.fetch_order(order["id"], symbol)
    except Exception as e:  # noqa: BLE001
        result["error"] = str(e)
    finally:
        ex.cancel_order(order["id"], symbol)
        result["cancelled"] = True
    return result


def _scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items() if str(k).lower() not in _SECRET_KEYS}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj


def write_report(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_scrub(data), indent=2, ensure_ascii=False, default=str))
