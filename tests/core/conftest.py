from datetime import UTC, datetime, timedelta

import pytest

from tradesys.core.models import Quality, Setup


def _make_setup(**overrides) -> Setup:
    base = dict(
        setup_id="s1",
        strategy_id="S1",
        symbol="BTC_USDT",
        side="long",
        entry_type="limit",
        entry=100.0,
        stop=99.0,
        tp=[102.0],
        invalidation=98.5,
        expires_at=datetime(2026, 10, 23, 12, tzinfo=UTC) + timedelta(hours=1),
        quality=Quality.A,
        reason="test",
        source="internal",
    )
    base.update(overrides)
    if base["side"] == "short" and "invalidation" not in overrides:
        base["invalidation"] = base["entry"] * 1.02
    if base["side"] == "short" and "tp" not in overrides:
        base["tp"] = [base["entry"] * 0.98]
    return Setup(**base)


@pytest.fixture
def make_setup():
    return _make_setup
