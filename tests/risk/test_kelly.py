import pytest

from tradesys.risk.kelly import kelly, kelly_cap, risk_pct, wilson_lower


def test_wilson():
    assert wilson_lower(45, 100) == pytest.approx(0.35614, abs=1e-4)


def test_wilson_zero_n():
    assert wilson_lower(0, 0) == 0.0


def test_kelly_values():
    assert kelly(0.45, 1.5) == pytest.approx(0.08333, abs=1e-4)
    assert kelly(0.5, 2.0) == pytest.approx(0.25)


def test_negative_edge_gives_zero():
    assert kelly_cap(0.4, 1.0, 0.5) == 0.0


def test_zero_payoff_gives_zero():
    assert kelly_cap(0.6, 0.0, 0.5) == 0.0


def test_ceiling_applies():
    assert risk_pct(0.5, 2.0, 0.5, 0.01) == 0.01


def test_turbo_three_quarters():
    assert kelly_cap(0.5, 2.0, 0.75) == pytest.approx(0.1875)
