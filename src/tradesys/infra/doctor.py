"""Comprobaciones del entorno: `tradesys doctor`."""

import json
import sys
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tradesys.config.risk import load_risk_config
from tradesys.infra.secrets import get_secret

MEXC_TIME_URL = "https://api.mexc.com/api/v3/time"
MAX_SKEW_MS = 500
REQUIRED_SECRETS = ("mexc_api_key", "mexc_api_secret")


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def mexc_server_time_ms() -> float:
    with urllib.request.urlopen(MEXC_TIME_URL, timeout=5) as resp:
        return float(json.load(resp)["serverTime"])


def run_checks(
    offline: bool, server_time_ms: Callable[[], float] | None = None
) -> list[CheckResult]:
    results = [
        CheckResult(
            "python", sys.version_info >= (3, 12), f"Python {sys.version.split()[0]} (mín. 3.12)"
        )
    ]

    try:
        cfg = load_risk_config(Path("config/risk.yaml"))
        results.append(CheckResult("config", True, f"risk.yaml OK (suelo {cfg.floor_usdt} USDT)"))
    except Exception as e:  # noqa: BLE001 - se informa cualquier fallo de carga
        results.append(CheckResult("config", False, f"config/risk.yaml no carga: {e}"))

    missing = [n for n in REQUIRED_SECRETS if not get_secret(n)]
    results.append(
        CheckResult(
            "secretos",
            not missing,
            "claves de MEXC en el Llavero"
            if not missing
            else "; ".join(f"falta {n}" for n in missing),
        )
    )

    if not offline:
        fetch = server_time_ms or mexc_server_time_ms
        try:
            local_ms = time.time() * 1000
            skew = abs(fetch() - local_ms)
            results.append(
                CheckResult(
                    "reloj", skew < MAX_SKEW_MS, f"desfase con MEXC {skew:.0f} ms (máx. 500)"
                )
            )
        except Exception as e:  # noqa: BLE001
            results.append(
                CheckResult("reloj", False, f"no se pudo consultar la hora de MEXC: {e}")
            )

    return results
