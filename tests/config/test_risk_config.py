from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from tradesys.config.risk import RiskConfig, load_risk_config
from tradesys.core.models import Bucket, Mode

EXAMPLE = Path(__file__).resolve().parents[2] / "config" / "risk.example.yaml"


@pytest.fixture
def cfg() -> RiskConfig:
    return load_risk_config(EXAMPLE)


def test_spec_values(cfg):
    assert cfg.floor_usdt == 450
    assert cfg.protected_initial_usdt == 500
    assert cfg.weekly_profit_to_bolsa_pct == 0.5
    assert cfg.ticket_ttl_seconds == 60
    assert cfg.buckets[Bucket.PROTECTED].daily_loss_pct == 0.02
    assert cfg.buckets[Bucket.BOLSA].weekly_loss_pct == 1.0


def test_risk_ceilings(cfg):
    assert cfg.risk_ceiling(Mode.NORMAL, Bucket.PROTECTED) == 0.01
    assert cfg.risk_ceiling(Mode.NORMAL, Bucket.BOLSA) == 0.02
    assert cfg.risk_ceiling(Mode.TURBO, Bucket.BOLSA) == 0.15
    assert cfg.risk_ceiling(Mode.ESCUDO, Bucket.PROTECTED) == 0.0025
    assert cfg.modes[Mode.TURBO].kelly_fraction == 0.75


def test_mode_not_allowed_in_bucket(cfg):
    with pytest.raises(ValueError):
        cfg.risk_ceiling(Mode.ATAQUE, Bucket.PROTECTED)


def test_floor_must_be_below_initial():
    data = yaml.safe_load(EXAMPLE.read_text())
    data["floor_usdt"] = 500
    with pytest.raises(ValidationError):
        RiskConfig.model_validate(data)


def test_real_config_matches_example():
    real = EXAMPLE.with_name("risk.yaml")
    assert load_risk_config(real) == load_risk_config(EXAMPLE)
