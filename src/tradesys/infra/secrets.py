"""Secretos en el Llavero del sistema (macOS Keychain). Nunca en el repo ni en la conversación."""

import keyring

SERVICE = "tradesys"
ALLOWED = frozenset(
    {
        "mexc_api_key",
        "mexc_api_secret",
        "mexc_readonly_key",
        "mexc_readonly_secret",
        "telegram_token",
        "telegram_chat_id",
    }
)


def _check(name: str) -> None:
    if name not in ALLOWED:
        raise ValueError(f"secreto desconocido: {name}. Permitidos: {', '.join(sorted(ALLOWED))}")


def get_secret(name: str) -> str | None:
    _check(name)
    return keyring.get_password(SERVICE, name)


def set_secret(name: str, value: str) -> None:
    _check(name)
    keyring.set_password(SERVICE, name, value)
