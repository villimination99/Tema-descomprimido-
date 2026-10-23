import pytest
from typer.testing import CliRunner

from tradesys.cli import app
from tradesys.infra.secrets import get_secret, set_secret


def test_set_get():
    set_secret("mexc_api_key", "abc123")
    assert get_secret("mexc_api_key") == "abc123"


def test_missing_returns_none():
    assert get_secret("telegram_token") is None


def test_unknown_name_rejected():
    with pytest.raises(ValueError):
        set_secret("password_del_banco", "x")


def test_cli_never_echoes_secret():
    r = CliRunner().invoke(app, ["secrets", "set", "mexc_api_key"], input="SUPERSECRETO\n")
    assert r.exit_code == 0, r.output
    assert "SUPERSECRETO" not in r.output
    assert get_secret("mexc_api_key") == "SUPERSECRETO"


def test_cli_rejects_unknown_name():
    r = CliRunner().invoke(app, ["secrets", "set", "otro"], input="x\n")
    assert r.exit_code != 0
