import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[2] / "scripts" / "hooks" / "guard.py"
spec = importlib.util.spec_from_file_location("guard", GUARD)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def bash(cmd: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


def edit(path: str, tool: str = "Edit") -> dict:
    return {"tool_name": tool, "tool_input": {"file_path": path}}


def decision(event):
    out = guard.decide(event)
    return None if out is None else out["hookSpecificOutput"]["permissionDecision"]


@pytest.mark.parametrize(
    "cmd",
    [
        "uv run tradesys exec live --ticket abc",
        "tradesys  exec   live",
        "cd x && tradesys exec live",
    ],
)
def test_live_execution_denied(cmd):
    assert decision(bash(cmd)) == "deny"


def test_probe_order_denied():
    assert decision(bash("uv run tradesys mexc probe --private --order swap")) == "deny"


def test_probe_without_order_allowed():
    assert decision(bash("uv run tradesys mexc probe --private")) is None


@pytest.mark.parametrize(
    "cmd",
    [
        "security find-generic-password -s tradesys -w",
        "python -m keyring get tradesys mexc_api_secret",
    ],
)
def test_secret_reading_denied(cmd):
    assert decision(bash(cmd)) == "deny"


@pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit"])
def test_risk_config_edit_asks(tool):
    assert decision(edit("/repo/config/risk.yaml", tool)) == "ask"
    assert decision(edit("config/gates.yaml", tool)) == "ask"


def test_other_file_edit_allowed():
    assert decision(edit("config/risk.example.yaml")) is None
    assert decision(edit("src/tradesys/risk/gate.py")) is None


def test_allows_normal_commands():
    assert decision(bash("uv run pytest -q")) is None


def test_reason_in_spanish():
    out = guard.decide(bash("tradesys exec live"))
    assert "ticket" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_main_reads_stdin():
    r = subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps(bash("tradesys exec live")),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_main_silent_when_allowed():
    r = subprocess.run(
        [sys.executable, str(GUARD)], input=json.dumps(bash("ls")), capture_output=True, text=True
    )
    assert r.returncode == 0 and r.stdout == ""
