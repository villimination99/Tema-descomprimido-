# tradesys

Sistema de trading propio para MEXC + TradingView. Diseño: `docs/superpowers/specs/2026-10-23-sistema-trading-mexc-design.md`. Plan: `docs/superpowers/plans/`.

## Instalación (Mac)

```bash
brew install uv            # si no lo tienes
uv sync                    # crea el entorno e instala dependencias
uv run tradesys --version  # comprueba la instalación
uv run pytest              # tests offline (no tocan la red ni dinero)
uv run pre-commit install  # activa ruff y gitleaks en cada commit
```
