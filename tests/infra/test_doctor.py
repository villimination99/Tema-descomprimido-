import time

from typer.testing import CliRunner

from tradesys.cli import app
from tradesys.infra.doctor import run_checks
from tradesys.infra.secrets import set_secret


def by_name(results):
    return {r.name: r for r in results}


def test_doctor_offline_reports_missing_keys():
    res = by_name(run_checks(offline=True))
    assert res["python"].ok
    assert res["config"].ok
    assert not res["secretos"].ok
    assert "falta mexc_api_key" in res["secretos"].detail
    assert "reloj" not in res


def test_doctor_offline_all_ok_with_keys():
    set_secret("mexc_api_key", "k")
    set_secret("mexc_api_secret", "s")
    assert all(r.ok for r in run_checks(offline=True))


def test_clock_skew_check():
    res = by_name(run_checks(offline=False, server_time_ms=lambda: time.time() * 1000 + 600))
    assert not res["reloj"].ok
    res = by_name(run_checks(offline=False, server_time_ms=lambda: time.time() * 1000 + 100))
    assert res["reloj"].ok


def test_clock_unreachable_is_failure():
    def boom():
        raise OSError("sin red")

    res = by_name(run_checks(offline=False, server_time_ms=boom))
    assert not res["reloj"].ok


def test_cli_doctor_exit_code():
    r = CliRunner().invoke(app, ["doctor", "--offline"])
    assert r.exit_code == 1
    assert "falta mexc_api_key" in r.output


import pytest  # noqa: E402


@pytest.mark.network
def test_real_mexc_clock():
    res = by_name(run_checks(offline=False))
    assert res["reloj"].ok, res["reloj"].detail
