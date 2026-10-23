import json

import pytest

from tradesys.exchange.probe import probe_order, probe_private, probe_public, write_report

MARKETS = {
    "BTC/USDT": {
        "symbol": "BTC/USDT",
        "precision": {"amount": 0.000001, "price": 0.01},
        "limits": {"amount": {"min": 0.000001}, "cost": {"min": 1.0}},
        "info": {},
    },
    "BTC/USDT:USDT": {
        "symbol": "BTC/USDT:USDT",
        "precision": {"amount": 1, "price": 0.1},
        "limits": {"amount": {"min": 1}, "cost": {"min": None}},
        "contractSize": 0.0001,
        "info": {"maintenanceMarginRate": 0.004},
    },
}


class FakeExchange:
    apiKey = "KEY123"
    secret = "SECRET456"
    has = {"createStopOrder": True, "createOrderWithTakeProfitAndStopLoss": False}

    def __init__(self, fail_fetch: bool = False):
        self.markets = MARKETS
        self.fail_fetch = fail_fetch
        self.created: list[dict] = []
        self.cancelled: list[str] = []

    def load_markets(self):
        return self.markets

    def market(self, symbol):
        return self.markets[symbol]

    def fetch_balance(self):
        return {"total": {"USDT": 500.0, "BTC": 0.0}}

    def fetch_trading_fees(self):
        return {"BTC/USDT": {"maker": 0.0, "taker": 0.0005}}

    def fetch_ticker(self, symbol):
        return {"last": 60000.0}

    def price_to_precision(self, symbol, price):
        return f"{price:.2f}"

    def amount_to_precision(self, symbol, amount):
        return f"{amount:.6f}"

    def create_order(self, symbol, type, side, amount, price=None, params=None):
        order = {
            "id": "o1",
            "symbol": symbol,
            "type": type,
            "side": side,
            "amount": amount,
            "price": price,
            "params": params or {},
        }
        self.created.append(order)
        return order

    def fetch_order(self, order_id, symbol):
        if self.fail_fetch:
            raise RuntimeError("fallo al consultar")
        return {"id": order_id, "status": "open"}

    def cancel_order(self, order_id, symbol):
        self.cancelled.append(order_id)
        return {"id": order_id, "status": "canceled"}


def test_probe_public_extracts_limits():
    r = probe_public(FakeExchange())
    assert r["n_markets"] == 2
    assert r["markets"]["BTC/USDT"]["min_cost"] == 1.0
    assert r["markets"]["BTC/USDT:USDT"]["mmr"] == 0.004
    assert r["markets"]["BTC/USDT:USDT"]["contract_size"] == 0.0001


def test_probe_private_reports_fees_and_nonzero_balances():
    r = probe_private(FakeExchange())
    assert r["balances"] == {"USDT": 500.0}
    assert r["fees"]["BTC/USDT"]["taker"] == 0.0005
    assert r["stop_supported"] is True


def test_probe_order_requires_SI():
    with pytest.raises(PermissionError):
        probe_order(FakeExchange(), "BTC/USDT", confirm="si")


def test_probe_order_post_only_far_below_market():
    ex = FakeExchange()
    r = probe_order(ex, "BTC/USDT", confirm="SI")
    assert r == {"created": True, "cancelled": True, "error": None}
    o = ex.created[0]
    assert o["type"] == "limit" and o["side"] == "buy"
    assert o["params"]["postOnly"] is True
    assert float(o["price"]) == pytest.approx(30000.0)
    assert float(o["amount"]) * float(o["price"]) >= 1.0


def test_probe_order_cancels_even_if_check_fails():
    ex = FakeExchange(fail_fetch=True)
    r = probe_order(ex, "BTC/USDT", confirm="SI")
    assert ex.cancelled == ["o1"]
    assert r["created"] is True and r["cancelled"] is True
    assert "fallo al consultar" in r["error"]


def test_report_written_without_secrets(tmp_path):
    ex = FakeExchange()
    data = {"public": probe_public(ex), "private": probe_private(ex), "apiKey": ex.apiKey}
    path = tmp_path / "mexc_capabilities.json"
    write_report(data, path)
    text = path.read_text()
    assert "KEY123" not in text and "SECRET456" not in text
    assert json.loads(text)["public"]["n_markets"] == 2
