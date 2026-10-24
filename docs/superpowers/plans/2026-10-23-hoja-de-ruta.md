# Hoja de ruta — Sistema de Trading MEXC + TradingView

**Spec:** `docs/superpowers/specs/2026-10-23-sistema-trading-mexc-design.md`

El spec cubre varios subsistemas independientes. Por eso hay **un plan detallado por fase**, y cada uno se escribe al empezar su fase, porque la Fase 0 verifica datos reales de MEXC que cambian los detalles de las siguientes. Esta hoja de ruta es la lista completa de lo que se construirá.

**Reglas comunes a todas las fases:**
- TDD: cada tarea empieza con un test que falla.
- Toda la suite por defecto es offline.
- Commits pequeños; revisión antes de integrar.
- Ninguna fase avanza sin tests en verde, una demostración y la aprobación del dueño.
- Las tareas marcadas ⇄ pueden ir en paralelo con agentes.

| Fase | Plan detallado | Estado |
|---|---|---|
| F0 Cimientos + motor de riesgo | `2026-10-23-f0-cimientos.md` | ✅ Escrito, listo para ejecutar en el Mac |
| F1 Datos + Análisis + Gráficos | `f1-datos-graficos.md` | Se escribe al cerrar la F0 |
| F2 Laboratorio (estrategias + simulación + escenarios) | `f2-laboratorio.md` | Se escribe al cerrar la F1 |
| F3 Papel 24/7 + TradingView + Telegram | `f3-papel.md` | Se escribe al cerrar la F2 |
| F4 Copiloto real + VPS | `f4-copiloto.md` | Se escribe al cerrar la F3 |
| F5 Automático + Ataque | `f5-automatico.md` | Se escribe al cerrar la F4 |

---

## F0 — Cimientos y motor de riesgo (en el Mac)
1. Esqueleto del proyecto (`uv`, Python 3.12, CLI `tradesys`, pre-commit con ruff y gitleaks).
2. Contratos de datos (§7) como modelos pydantic.
3. Configuración de riesgo (`config/risk.example.yaml`) con los valores del spec.
4. ⇄ Tamaño de posición y apalancamiento mínimo (§9.1).
5. ⇄ Kelly prudente con límite de Wilson (§9.2).
6. ⇄ Comprobación de liquidación (§9.3).
7. Libro de buckets: capital protegido, bolsa de ganancias, disyuntores, suelo de 450 y trinquete (§9.4).
8. Máquina de modos Escudo/Normal/Ataque/Turbo (§9.5).
9. Puerta PASS/BLOCK de 11 reglas con ticket firmado y caducidad (§9.6).
10. Secretos en el Llavero + `tradesys doctor`.
11. Sonda de MEXC: capacidades reales de la cuenta, con prueba de orden mínima solo tras confirmación.
12. Barreras de Claude Code (hook que bloquea ejecución real y cambios de riesgo).

**Aceptación:**
- `pytest` en verde.
- `tradesys doctor` en verde.
- `reports/mexc_capabilities.json` generado con la cuenta real.
- Todos los [VERIFICAR F0] del spec resueltos y anotados en el spec.

## F1 — Datos, análisis técnico y gráficos
1. ⇄ Cliente de datos MEXC REST + WebSocket (velas, trades, libro L2, funding, OI, mark/index).
2. Almacén Parquet + DuckDB, con detector y rellenador de huecos e informe `data_quality`.
3. Descarga histórica de 12 meses del universo + proxy de Binance marcado.
4. **Grabación de trades y libro desde el día 1** (para S7 y el order flow).
5. ⇄ Indicadores con golden tests contra CSV de TradingView (error < 0,1 %).
6. ⇄ Estructura de mercado (pivotes, BOS/CHoCH, zonas, FVG, barridos).
7. ⇄ Vistas alternativas (Heikin Ashi, Renko, velas de rango) y perfil de volumen, delta y CVD.
8. Clasificador de régimen y alineación multi-timeframe.
9. ⇄ Pine Script v6: `TS-Regime`, `TS-Structure`.
10. Prototipo de panel (Lightweight Charts frente a Streamlit) y elección.

11. **Aprendizaje (Dept. 11):** registro de `Prediction`/`Outcome` y puntuación automática del régimen en cada vela cerrada (primer marcador).

**Aceptación:** criterios del Dept. 1, 2 y 9 del spec; el marcador de régimen funciona con datos reales.

## F2 — Laboratorio
1. Bus de eventos + motor de backtest event-driven (mismo código que en vivo).
2. Modelos de coste: comisiones reales, slippage, probabilidad de ejecución maker, funding, latencia, mark price.
3. Resolución de ambigüedad intravela con 1m.
4. ⇄ Contexto (Fear & Greed, dominancia, calendario macro, banderas).
5. ⇄ Estrategias S1–S6 con sus fichas YAML.
6. Walk-forward, robustez, Deflated Sharpe, PBO y bootstrap de la expectativa.
7. Monte Carlo de cartera (suelo y ruina) + escenarios de estrés.
8. **Motor de escenarios (Dept. 5b):** análogos k-NN, bootstrap por bloques, modelo con saltos, escenarios de evento, 6 escenarios canónicos.
9. Selector de política de salida, validado frente a la política fija.
10. Informes de embudo G0–G5 por estrategia.
11. **Aprendizaje:**
    - esquema `TradeCard` y contrafactuales en el backtest;
    - calibración de probabilidades y pesos de generadores (nivel B) evaluados en walk-forward;
    - `config/learning.yaml` con rangos y presupuestos de cambio;
    - primer prototipo de meta-etiquetado (nivel D, como estrategia candidata).

**Aceptación:** fichas S1–S6 con veredicto. Si ninguna pasa G5, se itera y **no se avanza**.

## F3 — Papel 24/7
1. `PaperBroker` con datos en vivo.
2. Riesgo conectado al bus; motor de escenarios en posición en vivo.
3. Receptor de webhooks de TradingView + Cloudflare Tunnel + mapeo de símbolos.
4. Telegram: notificaciones, comandos y KILL.
5. Diario append-only + informes diario y semanal.
6. Servicios `launchd` + `pmset`.
7. Agentes y skills de Claude por departamento (`/briefing`, `/analizar`, `/simular`, `/operar`, `/kill`, …).
8. **Bucle de aprendizaje completo en papel:**
   - niveles A–C automáticos;
   - campeón frente a aspirante en sombra;
   - libro de lecciones semanal;
   - detección de deriva;
   - panel de aprendizaje en la Sala de Mando.

**Aceptación:** 2–4 semanas en papel 24/7, KILL probado y G6 evaluado.

## F4 — Copiloto real
1. `MexcBroker`: maker-first, stop en el exchange, watchdog, idempotencia y reconciliación.
2. Tests de caos (desconexión, 429, ejecución parcial, reinicio con posición).
3. VPS con IP fija + `systemd` + API de control + secretos cifrados.
4. Confirmación L2 por ticket desde Telegram.
5. **Aprendizaje en vivo:** modelo de slippage real por par y hora; sombra permanente vivo frente a papel; reversión automática de modelos.

**Aceptación:** ≥ 30 operaciones reales con tamaño mínimo, cero posiciones sin stop y G7 evaluado.

## F5 — Automático y modo Ataque
1. L3 para estrategias en G8.
2. Bolsa de ganancias en una subcuenta separada (si MEXC lo permite).
3. Ataque/Turbo con piramidación.
4. Degradación automática de estrategias y recalibración de pesos de escenarios.
5. **Asignación por Thompson** entre estrategias en G7 o más (nivel C) y revisión trimestral del propio embudo.

**Aceptación:** 4 semanas en L3 sin violar ninguna regla dura.
