# trading-bot-claude

Sistema de trading propio y privado para **MEXC** + **TradingView**, organizado en departamentos (datos, análisis, contexto, estrategia, simulación, escenarios, riesgo, ejecución, monitoreo, gráficos, auditoría y aprendizaje).

**Principio rector:** primero no perder el capital; después, dejar correr las ganancias. Capital protegido con suelo absoluto, bolsa de ganancias para el modo agresivo y una puerta de riesgo PASS/BLOCK por la que pasa cada orden.

- Diseño completo: [`docs/superpowers/specs/2026-10-23-sistema-trading-mexc-design.md`](docs/superpowers/specs/2026-10-23-sistema-trading-mexc-design.md)
- Hoja de ruta: [`docs/superpowers/plans/2026-10-23-hoja-de-ruta.md`](docs/superpowers/plans/2026-10-23-hoja-de-ruta.md)
- Sala de Mando (panel visual): [`docs/visual/sala-de-mando.html`](docs/visual/sala-de-mando.html)

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| F0 | Cimientos y motor de riesgo | ✅ hecha · 153 tests |
| F1 | Datos, análisis y gráficos | siguiente |
| F2–F5 | Laboratorio, papel 24/7, copiloto, automático | planificadas |

## Instalación (Mac)

```bash
brew install uv            # si no lo tienes
uv sync                    # crea el entorno e instala dependencias
uv run tradesys --version  # comprueba la instalación
uv run pytest              # tests offline (no tocan la red ni dinero)
uv run pre-commit install  # activa ruff y gitleaks en cada commit
```

## Primeros pasos con MEXC

1. Crea una subcuenta solo para el bot y una clave API con lectura y trading, **sin retiros**.
2. Guarda las claves en el Llavero (la entrada no se muestra):
   ```bash
   uv run tradesys secrets set mexc_api_key
   uv run tradesys secrets set mexc_api_secret
   ```
3. Comprueba el entorno y la cuenta:
   ```bash
   uv run tradesys doctor
   uv run tradesys mexc probe --private
   ```

Herramienta propia, no consejo financiero. El trading con apalancamiento puede hacer perder el capital asignado; el suelo y la puerta de riesgo existen para limitarlo.
