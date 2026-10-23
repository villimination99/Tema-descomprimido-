# Sistema de Trading MEXC + TradingView — Diseño y Plan Maestro

> Estado: **BORRADOR PARA APROBACIÓN.** No se ha construido nada. La ejecución empieza cuando el repo esté en el Mac y el dueño apruebe este documento.
> Fecha: 2026-10-23

---

## 1. Intención (el porqué)

Construir nuestro propio sistema de trading de cripto para operar en **MEXC**, usando **TradingView** para gráficos y señales. Debe tener los mejores análisis, gráficos muy precisos, todos los datos disponibles y simulación de escenarios y direcciones del precio. Se organiza en **departamentos** (agentes de Claude + módulos de código), cada uno con una responsabilidad clara, y sigue una **metodología propia** que decide qué estrategias merecen dinero real.

La referencia es [`dan-ai-lab/day-trader-fr`](https://github.com/dan-ai-lab/day-trader-fr). De ella tomamos:
- la cadena `scanner → news → entry → exit → timemachine → budget → risk → broker`;
- que el riesgo tenga **poder de veto** (`PASS` / `BLOCK`);
- la simulación de 10 000 escenarios antes de operar;
- los tests offline con fixtures, para que nada toque dinero real durante el desarrollo.

Lo que **no sirve** de la referencia: el mercado (acciones de EE. UU.), los datos (Yahoo/SEC), los brókers (Alpaca/IBKR), el horario de NYSE y la restricción a posiciones largas. MEXC es cripto 24/7, con spot y futuros perpetuos (largos y cortos, con apalancamiento).

### Metas
1. Datos completos y limpios de MEXC (velas, libro de órdenes, trades, funding, open interest) más contexto externo.
2. Gráficos precisos en TradingView (Pine Script propio) y en un panel propio.
3. Simulación seria: backtest con costes reales, walk-forward, Monte Carlo y escenarios de estrés.
4. Ejecución en MEXC con controles de riesgo que nadie (ni el bot) puede saltarse.
5. Un diario de operaciones y un ciclo de mejora continua.

### No-metas (por ahora)
- Alta frecuencia o market making (latencia de Mac doméstico + comisiones = no compite).
- Operar en otros exchanges (la arquitectura lo permitirá después vía ccxt).
- Predicción con IA "caja negra" que no se pueda explicar ni validar.

### Anti-metas (fracaso aunque "funcione")
- Un bot que opera dinero real con una estrategia que no pasó las puertas de validación (§6).
- Cualquier camino por el que se pueda **retirar** fondos o saltarse el stop.
- Sobreoptimizar: estrategias que brillan en el backtest y mueren en vivo.
- Que el usuario no entienda por qué el bot abrió una posición.

---

## 2. Realidades técnicas verificadas (oct 2026)

| Tema | Realidad | Consecuencia en el diseño |
|---|---|---|
| TradingView → MEXC | TradingView no ejecuta en MEXC. Las alertas envían un **webhook** (plan de pago) a un servidor nuestro. | Montamos un receptor de webhooks propio en el Mac, expuesto con un túnel seguro. |
| API de futuros MEXC | MEXC cambió el dominio de acceso a la API de futuros el 12-ene-2026. Hubo épocas con la creación de órdenes de futuros por API restringida; hay repos no oficiales que "la saltan". | **Fase 0 incluye una prueba real** de crear/cancelar una orden mínima por API. Nunca usamos "bypasses" no oficiales. Si futuros no está disponible, empezamos en spot. |
| ccxt + MEXC swap | ccxt soporta MEXC spot y swap (`defaultType: swap`). Hay errores conocidos de modo de posición (código 7002) si no coinciden `openType`/`leverage` con la cuenta. | Capa de ejecución propia sobre ccxt, con fallback al SDK oficial, y tests de cada tipo de orden. |
| Mac doméstico | Se duerme, pierde red, se actualiza. | Fase 1–3 en el Mac (con `launchd` + `caffeinate`). Antes de dinero serio, migrar el motor a un VPS barato; el Mac queda como panel y laboratorio. |

Fuentes: [anuncios API MEXC](https://www.mexc.com/bn-BD/announcements/api-updates), [CCXT vs MEXC API](https://docs.ccxt.com/docs/comparisons/ccxt-vs-mexc-api), [ccxt issue 7002](https://lightrun.com/answers/ccxt-ccxt-mexc-swap-error-code-7002).

---

## 3. Enfoques considerados

| Enfoque | Qué es | Pros | Contras |
|---|---|---|---|
| **A. Solo TradingView + servicio de terceros** (AlgoWay, 3Commas…) | Pine Script genera alertas; un servicio externo ejecuta en MEXC. | Rápido, poco código. | Datos limitados a lo que ve Pine; simulación pobre; dependes de un tercero con tus claves; sin "departamentos". |
| **B. Sistema propio en Python + TradingView como capa visual y de señales** ✅ | Nuestro motor de datos, análisis, simulación, riesgo y ejecución. TradingView para gráficos, indicadores Pine propios y como fuente opcional de señales vía webhook. Claude Code orquesta los departamentos. | Control total, datos completos, simulación seria, auditable, ampliable. | Más trabajo inicial. |
| **C. Framework existente** (Freqtrade / Hummingbot / NautilusTrader) | Adaptar un bot open source. | Mucho hecho ya (backtest, dry-run). | Metodología y departamentos ajenos; soporte MEXC futuros irregular; menos "nuestro". |

**Recomendación: B**, tomando ideas probadas de C (el modo dry-run de Freqtrade, el diseño event-driven de Nautilus) sin depender de ellos. *(Decisión de Claude; el dueño pidió "nuestro propio sistema").*

---

## 4. Arquitectura: los departamentos

Cada departamento = **un módulo Python** (lo que hace el trabajo, testeable) + **un agente/skill de Claude Code** (lo que interpreta, explica y coordina). Así funciona igual con o sin Claude.

```
                 ┌──────────────────────── DIRECCIÓN (Claude orquestador) ────────────────────────┐
                 │  briefing diario · decide qué departamentos consultar · explica en español      │
                 └───────────────────────────────────────────────────────────────────────────────────┘
   ┌──────────┐   ┌────────────┐   ┌─────────────┐   ┌────────────┐   ┌──────────┐   ┌───────────┐
   │ 1 DATOS  │──▶│ 2 ANÁLISIS │──▶│ 4 ESTRATEGIA│──▶│ 5 SIMULAC. │──▶│ 6 RIESGO │──▶│ 7 EJECUC. │──▶ MEXC
   └──────────┘   │  TÉCNICO   │   │ / RESEARCH  │   └────────────┘   │  (VETO)  │   └───────────┘
        │         └────────────┘   └─────────────┘                    └──────────┘         │
        │         ┌────────────┐          ▲                                                 ▼
        └────────▶│ 3 CONTEXTO │──────────┘                                         ┌───────────────┐
                  │ /SENTIMIENTO│        TradingView (webhooks) ──▶ entra por 4     │ 8 MONITOREO   │
                  └────────────┘                                                    │  Y ALERTAS    │
                  ┌────────────┐                                                    └───────────────┘
                  │ 9 GRÁFICOS │◀── todos                       ┌──────────────────┐
                  └────────────┘                                │ 10 AUDITORÍA /   │◀── todos
                                                                │   DIARIO         │
                                                                └──────────────────┘
```

| # | Departamento | Responsabilidad | Entradas → Salidas |
|---|---|---|---|
| 1 | **Datos** | Descargar y guardar histórico y tiempo real de MEXC: velas (1m→1D), trades, libro L2, funding, open interest, mark/index price. Validar huecos y duplicados. | API REST/WS MEXC → Parquet + DuckDB |
| 2 | **Análisis técnico** | Indicadores (EMA, VWAP, RSI, ATR, Bollinger, Ichimoku…), estructura de mercado (máximos/mínimos, BOS/CHoCH), soportes/resistencias, perfil de volumen, régimen (tendencia / rango / alta volatilidad), multi-timeframe. | velas → `features` |
| 3 | **Contexto y sentimiento** | Funding y OI agregados, liquidaciones, Fear & Greed, dominancia BTC, calendario macro (FOMC, CPI), noticias cripto, desbloqueos de tokens. | fuentes públicas → `context` |
| 4 | **Estrategia / Research** | Biblioteca de estrategias como reglas explícitas. Recibe también señales de TradingView. Propone *setups* (dirección, entrada, stop, objetivo, invalidación). | features + context (+ webhook) → `setup` |
| 5 | **Simulación** | Backtest event-driven con comisiones, slippage y funding; walk-forward; Monte Carlo (10 000 caminos por bootstrap de velas y de trades); escenarios de estrés (−20 % en 1 h, gap de liquidez, funding extremo). Da la probabilidad de objetivo/stop/ninguno. | setup + histórico → `sim_report` |
| 6 | **Riesgo (veto)** | Tamaño de posición por % de riesgo, límites diarios/semanales, exposición total, apalancamiento máximo, correlación entre posiciones, distancia a liquidación. Responde `PASS` / `BLOCK` + motivo. **Nadie puede saltárselo.** | setup + sim + cuenta → `PASS/BLOCK` |
| 7 | **Ejecución** | Órdenes en MEXC (spot/swap): límite/mercado, stop-loss y take-profit **en el exchange** (no solo en el bot), idempotencia, reintentos, reconciliación de posiciones al arrancar. | ticket aprobado → orden |
| 8 | **Monitoreo y alertas** | Seguimiento de posiciones, PnL, salud del sistema (WS caído, latencia, error de API), alertas a Telegram, **kill switch** (cerrar todo y parar). | estado → notificaciones |
| 9 | **Gráficos** | Indicadores/estrategias Pine Script v6 en TradingView + panel propio (TradingView Lightweight Charts) con entradas, stops, objetivos, escenarios simulados (abanico Monte Carlo) y equity. | todo → visual |
| 10 | **Auditoría / Diario** | Registro inmutable de cada señal, decisión, veto, orden y resultado. Informe semanal: qué funcionó, qué no, desviación vivo vs. backtest. | todo → `journal` + informes |

### Flujo de una operación
1. Datos actualiza → Análisis y Contexto calculan.
2. Estrategia (o una alerta de TradingView) propone un setup.
3. Simulación evalúa: probabilidades, R esperado, peor caso.
4. Riesgo decide `PASS`/`BLOCK` y calcula el tamaño.
5. **Según el nivel de autonomía (§7):** se pide confirmación al usuario o se ejecuta solo.
6. Ejecución coloca entrada + stop + objetivo en MEXC.
7. Monitoreo vigila; Auditoría registra; Gráficos lo muestra.

---

## 5. Stack tecnológico (Mac) — *decisiones de Claude, revisables*

| Capa | Elección | Motivo |
|---|---|---|
| Lenguaje | Python 3.12, gestor `uv` | Ecosistema cuant más completo; `uv` instala rápido y fija versiones. |
| Exchange | `ccxt` (+ SDK/REST oficial de MEXC como respaldo) | Unifica API; permite añadir exchanges luego. |
| Datos | Parquet + DuckDB; `polars`/`pandas` | Rápido en local, sin servidor de base de datos. |
| Indicadores | `pandas-ta` / implementaciones propias testeadas | Control y precisión verificable contra TradingView. |
| Backtest | Motor event-driven propio + `vectorbt` para barridos masivos | El propio para realismo (fills, funding); vectorbt para explorar parámetros rápido. |
| Webhooks | FastAPI + Cloudflare Tunnel (o ngrok) | HTTPS público seguro hacia el Mac sin abrir puertos. |
| Panel | Streamlit o FastAPI + Lightweight Charts | Gráficos estilo TradingView con nuestros datos. |
| Alertas | Bot de Telegram | Llega al móvil; permite confirmar con un botón. |
| Secretos | Llavero de macOS (`keyring`) + `.env` fuera de git | Las claves nunca en el repo ni en la conversación. |
| Procesos 24/7 | `launchd` + `caffeinate` (luego VPS) | Nativo en macOS. |
| Tests | `pytest` con fixtures offline | Igual que la referencia: nada toca dinero en tests. |
| Departamentos IA | Claude Code: skills en `.claude/skills/` + subagentes en `.claude/agents/` | Cada departamento consultable por nombre (`/datos`, `/riesgo`…). |

### Estructura del repo prevista
```
trading-system/
├── pyproject.toml
├── config/            # settings.example.yaml, risk.example.yaml, strategies/*.yaml
├── src/tradesys/
│   ├── data/          # 1 Datos
│   ├── analysis/      # 2 Análisis técnico
│   ├── context/       # 3 Contexto
│   ├── strategy/      # 4 Estrategias
│   ├── sim/           # 5 Simulación (backtest, walkforward, montecarlo, stress)
│   ├── risk/          # 6 Riesgo
│   ├── execution/     # 7 Ejecución (paper + mexc)
│   ├── monitor/       # 8 Monitoreo, telegram, kill switch
│   ├── charts/        # 9 Panel
│   ├── journal/       # 10 Auditoría
│   └── webhook/       # receptor TradingView
├── pine/              # Indicadores y estrategias Pine Script v6
├── .claude/agents/    # un agente por departamento
├── .claude/skills/    # comandos /datos /analisis /simular /riesgo /operar /diario
├── tests/ + tests/fixtures/
└── docs/
```

---

## 6. Metodología propia: "Embudo de validación"

Ninguna estrategia toca dinero sin pasar **todas** las puertas, en orden:

| Puerta | Prueba | Criterio para pasar *(valores iniciales, ajustables)* |
|---|---|---|
| G0 Hipótesis | Regla escrita en lenguaje claro: por qué debería funcionar. | Explicable en 3 frases; sin parámetros mágicos. |
| G1 Backtest | ≥ 2 años de datos, con comisiones MEXC reales, slippage y funding. | ≥ 100 operaciones; profit factor > 1,3; max drawdown < 20 %. |
| G2 Walk-forward | Optimiza en una ventana, prueba en la siguiente, repetido. | El resultado fuera de muestra conserva ≥ 50 % del de la muestra. |
| G3 Robustez | Parámetros ±20 %, otros pares, otros regímenes. | Sigue siendo rentable; sin "pico" aislado de parámetros. |
| G4 Monte Carlo | 10 000 remuestreos de operaciones y de velas. | Percentil 5 del drawdown aceptable para el capital; probabilidad de ruina < 1 %. |
| G5 Estrés | Escenarios: crash −20 %/1 h, gap, funding extremo, API caída. | Ningún escenario supera la pérdida máxima definida. |
| G6 Papel | 2–4 semanas en vivo sin dinero (paper / testnet). | Resultados dentro del rango previsto por la simulación. |
| G7 Vivo mínimo | Capital pequeño, tamaño mínimo. | 30+ operaciones dentro de lo esperado. |
| G8 Escalar | Subir tamaño poco a poco. | Revisión semanal sin desviaciones graves. |

Cada estrategia tiene una **ficha** (`config/strategies/<nombre>.yaml` + informe) con su estado en el embudo. Si en vivo se desvía del rango simulado, **baja automáticamente** a papel.

### Estrategias iniciales candidatas (a validar, no a confiar)
1. Seguimiento de tendencia multi-timeframe (EMA + estructura + ATR stop).
2. Ruptura de rango con confirmación de volumen (equivalente cripto del ORB de la referencia, usando sesiones Asia/Europa/EE. UU.).
3. Reversión a la media en rango (VWAP/Bollinger) solo con régimen "rango".
4. Filtros de contexto: funding extremo y OI como confirmación o veto.
5. Señales de TradingView del usuario, tratadas como una estrategia más (también pasan por el embudo).

---

## 7. Riesgo y seguridad (reglas duras)

**Valores por defecto (el dueño los fija en la Fase 0):**
- Riesgo por operación: 0,5–1 % del capital asignado.
- Pérdida máxima diaria: 3 % → el bot se para hasta el día siguiente.
- Pérdida máxima semanal: 6 % → se para y exige revisión humana.
- Apalancamiento máximo: 3x, margen **aislado**; el stop debe quedar lejos de la liquidación.
- Máximo de posiciones simultáneas y de exposición correlacionada (p. ej., no 3 largos de altcoins correlacionadas).
- Stop-loss **siempre colocado en el exchange** en el mismo momento que la entrada.

**Seguridad:**
- Clave API de MEXC **sin permiso de retiro**, con **lista blanca de IP**.
- Subcuenta de MEXC dedicada al bot, con solo el capital asignado.
- Claves en el Llavero de macOS; `.env` en `.gitignore`; escaneo de secretos antes de cada commit.
- Webhook de TradingView con secreto compartido + validación de esquema + lista de símbolos permitidos.
- Kill switch: comando de Telegram y `/kill` en Claude → cancela órdenes, cierra posiciones y detiene el motor.

**Niveles de autonomía** *(propuesta de Claude; el dueño decide a qué nivel llegar)*:
| Nivel | Comportamiento |
|---|---|
| L0 Analista | Solo analiza y simula. Sin órdenes. |
| L1 Papel | Opera en simulación con datos en vivo. |
| L2 Copiloto | Propone cada operación por Telegram; ejecuta solo tras "sí" para **ese** ticket (como la referencia). |
| L3 Piloto automático | Ejecuta solo las estrategias que pasaron G7, dentro de los límites duros. Avisa de todo. |

---

## 8. Logística: qué necesitas tener listo en el Mac

### Checklist del dueño (antes de ejecutar)
- [ ] Mac con macOS actualizado; saber si es Apple Silicon (M1–M4) o Intel.
- [ ] Instalados: Homebrew, Git, Python 3.12 (vía `uv`), VS Code (opcional).
- [ ] Claude Code instalado en el Mac y este repo clonado.
- [ ] Cuenta MEXC verificada (KYC) + **subcuenta** para el bot.
- [ ] Clave API de MEXC: lectura + trading, **sin retiros**, con IP fija si es posible.
- [ ] Plan de TradingView con webhooks (Essential o superior).
- [ ] Bot de Telegram creado (BotFather) + tu chat ID.
- [ ] Cuenta gratuita de Cloudflare (para el túnel) o ngrok.
- [ ] Respuestas a las preguntas de §10.

### Fases de ejecución
| Fase | Contenido | Entregable | Nivel |
|---|---|---|---|
| **0 Preparación** | Instalar entorno, guardar claves en el Llavero, verificar API MEXC (spot y futuros: crear y cancelar una orden mínima), fijar límites de riesgo. | `make doctor` en verde; informe "qué permite tu API". | — |
| **1 Datos + Gráficos** | Dept. 1, 2, 9: descarga histórica, WS en vivo, indicadores verificados contra TradingView, primer Pine Script, panel. | Gráficos propios = TradingView (diferencia < 0,1 %). | L0 |
| **2 Laboratorio** | Dept. 3, 4, 5: contexto, estrategias candidatas, backtest, walk-forward, Monte Carlo, estrés. | Fichas de estrategia con estado G0–G5. | L0 |
| **3 Riesgo + Papel** | Dept. 6, 7 (modo papel), 8, 10; receptor de webhooks de TradingView. | Bot en papel 24/7 con alertas en Telegram y diario. | L1 |
| **4 Copiloto** | Ejecución real en MEXC con confirmación por ticket; capital mínimo. | Primeras operaciones reales auditadas. | L2 |
| **5 Autónomo + VPS** | Migrar el motor a VPS; piloto automático solo para estrategias G7. | Sistema 24/7 con kill switch probado. | L3 |
| **Continuo** | Revisión semanal del Dept. 10; nuevas hipótesis entran por G0. | Mejora iterativa. | — |

Cada fase termina con: tests en verde, demostración en vivo, y tu aprobación para pasar a la siguiente.

### Cómo trabajarán los "departamentos" con Claude en el Mac
- Un subagente por departamento en `.claude/agents/` con su rol, sus herramientas y lo que **no** puede hacer (p. ej., solo Ejecución puede llamar a la API de órdenes, y solo con un `PASS` de Riesgo).
- Comandos: `/briefing` (resumen del mercado), `/analizar BTCUSDT`, `/simular <setup>`, `/riesgo`, `/operar` (genera ticket), `/diario`, `/kill`.
- Para construir el sistema usaremos varios agentes en paralelo por fase (uno por departamento independiente) y revisión de código antes de cada merge.

---

## 9. Qué queda a criterio del constructor
- Librerías exactas de indicadores y versión de vectorbt.
- Esquema detallado de las tablas DuckDB y del diario.
- Diseño visual del panel.
- Los parámetros concretos de cada estrategia (los decide el embudo, no nosotros a ojo).

---

## 10. Preguntas abiertas para el dueño (necesarias antes de la Fase 0)
1. **Autonomía final:** ¿hasta qué nivel quieres llegar (L2 copiloto o L3 automático)?
2. **Mercado:** ¿spot, futuros perpetuos o ambos? ¿Apalancamiento máximo que aceptas?
3. **Capital:** ¿cuánto asignarás al bot al principio y cuánto como máximo?
4. **Pares:** ¿BTC/ETH solamente, top 20, o también altcoins pequeñas?
5. **Estilo y temporalidad:** ¿scalping (minutos), intradía (horas) o swing (días)?
6. **TradingView:** ¿qué plan tienes? ¿Tienes ya indicadores o estrategias Pine propias que quieras integrar?
7. **Mac:** ¿qué modelo? ¿Puede quedarse encendido 24/7 o prefieres un VPS desde el principio?

---

*Aviso: este sistema es una herramienta. No garantiza beneficios; los mercados cripto con apalancamiento pueden hacer perder todo el capital asignado. Las puertas de validación existen para reducir ese riesgo, no para eliminarlo.*
