from typer.testing import CliRunner

from tradesys.cli import app


def test_version():
    r = CliRunner().invoke(app, ["--version"])
    assert r.exit_code == 0
    assert "tradesys 0.1.0" in r.stdout
