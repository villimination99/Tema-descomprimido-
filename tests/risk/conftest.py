from pathlib import Path

import pytest

from tradesys.config.risk import RiskConfig, load_risk_config

EXAMPLE = Path(__file__).resolve().parents[2] / "config" / "risk.example.yaml"


@pytest.fixture
def cfg() -> RiskConfig:
    return load_risk_config(EXAMPLE)
