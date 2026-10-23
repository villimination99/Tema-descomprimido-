"""Hook PreToolUse de Claude Code: barreras técnicas del sistema de trading (spec §12).

- Bloquea la ejecución real (`tradesys exec live`) fuera del flujo /operar.
- Bloquea la orden de prueba de la sonda de MEXC (la lanza el dueño en su terminal).
- Bloquea la lectura de secretos del Llavero.
- Pide confirmación antes de editar config/risk.yaml o config/gates.yaml.
"""

import json
import re
import sys

_DENY_BASH = [
    (
        re.compile(r"\btradesys\s+exec\s+live\b"),
        "La ejecución real solo se hace por /operar con un ticket PASS vigente.",
    ),
    (
        re.compile(r"\btradesys\s+mexc\s+probe\b.*--order"),
        "La orden de prueba en MEXC la lanza el dueño en su propia terminal.",
    ),
    (
        re.compile(r"\bsecurity\s+find-generic-password\b|\bkeyring\s+get\b"),
        "Claude no puede leer secretos del Llavero.",
    ),
]
_PROTECTED_FILES = re.compile(r"(^|/)config/(risk|gates)\.yaml$")
_EDIT_TOOLS = {"Edit", "Write", "MultiEdit"}


def _out(decision: str, reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }


def decide(event: dict) -> dict | None:
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    if tool == "Bash":
        command = tool_input.get("command", "")
        for pattern, reason in _DENY_BASH:
            if pattern.search(command):
                return _out("deny", reason)
    if tool in _EDIT_TOOLS and _PROTECTED_FILES.search(tool_input.get("file_path", "")):
        return _out("ask", "Cambiar los límites de riesgo necesita la confirmación del dueño.")
    return None


def main() -> None:
    result = decide(json.load(sys.stdin))
    if result is not None:
        sys.stdout.write(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
