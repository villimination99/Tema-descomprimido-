# trading-bot-claude — reglas del proyecto

Sistema de trading propio para MEXC + TradingView. El dueño habla español: toda respuesta, mensaje de CLI e informe va en español; los identificadores de código, en inglés.

## Documentos que mandan
- Diseño (autoridad): `docs/superpowers/specs/2026-10-23-sistema-trading-mexc-design.md`
- Hoja de ruta: `docs/superpowers/plans/2026-10-23-hoja-de-ruta.md` (un plan detallado por fase en `docs/superpowers/plans/`)
- Panel visual: `docs/visual/sala-de-mando.html`

## Principio rector: no perder el capital (§1b)
- Nunca cambies los límites de riesgo (`config/risk.yaml`, `config/gates.yaml`) sin que el dueño lo pida expresamente. Un hook pide confirmación.
- El aprendizaje automático (Dept. 11) puede ajustar modelos, nunca el suelo, los disyuntores, los techos de modo ni el apalancamiento.
- Nada envía órdenes reales fuera del flujo `/operar` con un ticket PASS vigente. El hook `scripts/hooks/guard.py` bloquea `tradesys exec live`, la orden de prueba de la sonda y la lectura de secretos.
- Ninguna estrategia opera en vivo sin pasar el embudo G0–G8 (§8).

## Cómo se trabaja
- TDD siempre: test que falla → código mínimo → test en verde. Cada fase tiene su plan con tareas y tests.
- `uv run pytest` debe pasar offline. Los tests que tocan la red llevan `@pytest.mark.network` y no se ejecutan por defecto.
- Todas las horas internas en UTC; el motor de riesgo recibe `now` como parámetro y nunca llama a `datetime.now()`.
- Importes en USDT; porcentajes como fracción (`0.01` = 1 %).
- Antes de commit: `uv run ruff check .`, `uv run ruff format .` y los tests. pre-commit ejecuta ruff y gitleaks.
- Secretos solo en el Llavero (`tradesys secrets set …`), nunca en el repo ni en la conversación.

## Comandos
```bash
uv sync                               # entorno
uv run pytest                         # tests offline
uv run tradesys doctor [--offline]    # comprobación del entorno
uv run tradesys secrets set <nombre>  # guardar un secreto en el Llavero
uv run tradesys mexc probe --private  # capacidades reales de la cuenta MEXC
```

## Estructura
- `src/tradesys/core/` — contratos de datos (§7)
- `src/tradesys/config/` — configuración de riesgo
- `src/tradesys/risk/` — tamaño, Kelly, liquidación, libro de capital, modos, puerta PASS/BLOCK
- `src/tradesys/infra/` — secretos y doctor
- `src/tradesys/exchange/` — sonda de MEXC (y, desde la F1, el cliente de datos)
- `scripts/hooks/guard.py` — barreras de Claude Code

## Estado
- F0 (cimientos y motor de riesgo): hecha. Pendiente en el Mac del dueño: claves de MEXC, `doctor` y `mexc probe`; después, anotar los resultados en el diseño (marcas [VERIFICAR F0]).
- Siguiente: plan detallado de la F1 (datos, análisis, gráficos y primer marcador de aprendizaje).
