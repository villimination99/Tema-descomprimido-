import pytest
from pydantic import ValidationError

from tradesys.core.models import Setup, Stage


def test_setup_long_stop_must_be_below_entry(make_setup):
    with pytest.raises(ValidationError):
        make_setup(side="long", entry=100, stop=101)


def test_setup_short_stop_must_be_above_entry(make_setup):
    with pytest.raises(ValidationError):
        make_setup(side="short", entry=100, stop=99)


def test_setup_stop_equal_entry_invalid(make_setup):
    with pytest.raises(ValidationError):
        make_setup(side="long", entry=100, stop=100)


def test_setup_targets_on_profit_side(make_setup):
    with pytest.raises(ValidationError):
        make_setup(side="long", entry=100, stop=99, tp=[98])


def test_setup_requires_timezone(make_setup):
    from datetime import datetime

    with pytest.raises(ValidationError):
        make_setup(expires_at=datetime(2026, 10, 23, 12))


def test_roundtrip_json(make_setup):
    s = make_setup(side="long", entry=100, stop=99, tp=[102])
    assert Setup.model_validate_json(s.model_dump_json()) == s


def test_stage_order():
    assert Stage.G7_IN_PROGRESS.rank() > Stage.G6.rank()
    assert Stage.G8.rank() > Stage.G7.rank()
    assert Stage.G0.rank() == 0
