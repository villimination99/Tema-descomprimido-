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

## 6b. Objetivo de rendimiento: cuentas hechas

**Objetivo del dueño:** empezar con 500 $ y ganar **+800 a +1000 $ o más por semana** (x2,6–x3 semanal, ≈ +115–145 $/día), aceptando más riesgo cuando el mercado lo permita y bajándolo cuando no.

Probabilidad de lograr +800 $ en una semana (simulación, script `docs/analisis/mc_objetivo_800.py`):

| Ventaja de la estrategia | 20 ops/sem, 10 % riesgo | 40 ops/sem, 10 % riesgo | Riesgo de perder >50 % esa semana (40 ops, 10 %) |
|---|---|---|---|
| Excepcional (55 %, 2,5R) — rara, pocas veces sostenible | 75 % | 96 % | 2 % |
| Buena (50 %, 2R) | 25 % | 56 % | 11 % |
| Realista (45 %, 1,5R) | 2 % | 8 % | 44 % |

Lectura: el objetivo **solo es alcanzable con una ventaja excepcional + muchas operaciones por semana** (scalping/intradía activo). Por tanto la misión n.º 1 del sistema es **encontrar y demostrar esa ventaja** (G1–G6) antes de apostar; el modo Ataque se habilita solo cuando la ventaja medida lo justifica. Con 500 $ además pesan los mínimos de orden y las comisiones: el Dept. 5 debe simular con las comisiones maker/taker reales de MEXC.

Simulación previa con objetivo x2 semanal (100 000 caminos, 20 operaciones/semana, coste 0,1R por operación, script en `docs/analisis/mc_objetivo.py`):

Simulación Monte Carlo (100 000 caminos, 20 operaciones/semana, coste 0,1R por operación, script en `docs/analisis/mc_objetivo.py`):

| Riesgo por operación | Ventaja **buena** (50 % acierto, 2R): P(x2 en 1 semana) · P(caer >50 % en 4 semanas) | Ventaja **realista** (45 %, 1,5R): P(x2 en 1 semana) · P(caer >50 % en 4 semanas) |
|---|---|---|
| 1 % | 0 % · 0 % | 0 % · 0 % |
| 5 % | 13 % · 1 % | 0,6 % · 22 % |
| 10 % | 41 % · 13 % | 6 % · 62 % |
| 20 % | 59 % · 46 % | 13 % · 91 % (46 % acaba con <10 % del capital) |

**Conclusiones que cambian el diseño:**
1. **El motor del objetivo es la ventaja (edge), no el apalancamiento.** Con una ventaja normal, subir el riesgo no acerca el x2: acelera la ruina. Con una ventaja fuerte y verificada, el x2 semanal es *posible* algunas semanas, nunca constante.
2. Por eso **el riesgo permitido se calcula a partir de la ventaja medida**, no del deseo: tope = ½ Kelly sobre el *límite inferior* de la ventaja estimada en las puertas G1–G6. Ejemplo: 45 %/1,5R → Kelly 8 % → tope 4 %; 50 %/2R → Kelly 25 % → tope 12 %.
3. **El objetivo se trata como "semana objetivo", no como promesa.** El sistema mide la semana contra el objetivo y ajusta el modo; nunca sube el riesgo para "recuperar".

### Modos de riesgo adaptativos

| Modo | Cuándo se activa | Riesgo/op | Apalanc. máx. | Setups permitidos |
|---|---|---|---|---|
| 🛡️ **Escudo** | Tras pérdida diaria, régimen confuso, noticia macro, o drawdown > 15 % | 0,5 % | 2x | Solo A+ o ninguno |
| ⚖️ **Normal** | Por defecto | 1–2 % | 5x | A y A+ |
| ⚔️ **Ataque** | Régimen de tendencia claro + estrategia en G7 + racha dentro de lo esperado | hasta el tope ½ Kelly | 10x | A+ con confluencia multi-timeframe |
| 🚀 **Turbo** | Solo con el **capital de ataque** (abajo), aprobado por el dueño para esa sesión | hasta 2× el tope ½ Kelly | 20x | A+ en momentos de expansión de volatilidad |

Cambio de modo automático por el Departamento de Riesgo con reglas explícitas (régimen, volatilidad ATR, racha, drawdown, calendario). **Bajar de modo es inmediato; subir requiere que se cumplan todas las condiciones** y en Turbo además tu "sí".

### Estructura de capital (para buscar el x2 sin arriesgar todo)
- **Capital base** (p. ej. 70 %): solo modos Escudo/Normal. Crece despacio y protege la cuenta.
- **Capital de ataque** (p. ej. 30 %): puede ir a Ataque/Turbo. Se asume que puede perderse entero; si se pierde, se para hasta la revisión semanal (no se rellena desde la base automáticamente).
- **Trinquete de beneficios:** cada vez que el capital de ataque se duplica, la mitad de la ganancia pasa a la base (o se retira). Así una buena semana no se devuelve en la siguiente.
- **Piramidación:** en Ataque, añadir a posiciones ganadoras con el stop ya en break-even, nunca promediar perdedoras.

### Adaptación a distintas temporalidades
Cada estrategia y cada modo declaran su temporalidad; el sistema elige según régimen y volatilidad:

| Estilo | Marcos | Cuándo encaja | Riesgo típico |
|---|---|---|---|
| Scalping | 1m–5m (contexto 15m) | Alta volatilidad, sesiones solapadas UE/EE. UU., spread bajo | Comisiones pesan mucho: solo con taker/maker calculados |
| Intradía | 15m–1h (contexto 4h) | Tendencia diaria definida | Normal/Ataque |
| Swing | 4h–1D (contexto 1W) | Tendencias de varios días, menor ruido | Normal; tamaño menor por stops anchos |

Confluencia multi-timeframe obligatoria: el marco superior define la dirección, el medio el setup, el inferior la entrada.

### Otras formas de ver el gráfico (Dept. 2 y 9)
Para el modo agresivo no basta con velas y medias. El sistema incluirá:
- **Heikin Ashi, Renko y velas de rango**: filtran ruido para ver tendencia limpia.
- **Perfil de volumen / Market Profile**: POC, áreas de valor, zonas de bajo volumen donde el precio se acelera.
- **Order flow**: delta, CVD (volumen acumulado comprador vs vendedor), footprint a partir de los trades de MEXC.
- **Libro de órdenes**: muros de liquidez, desequilibrio bid/ask.
- **Mapas de liquidaciones y OI**: dónde se concentran stops y liquidaciones (imanes de precio).
- **Funding y basis**: posicionamiento extremo de la masa → combustible para squeezes.
- **Clasificador de régimen** (tendencia / rango / expansión / compresión) que decide qué vista y qué estrategia mandan.
- **Abanico de escenarios**: el Dept. 5 dibuja sobre el gráfico los caminos simulados (percentiles 5/50/95) y las probabilidades de tocar objetivo vs stop.

---

## 7. Riesgo y seguridad (reglas duras)

**Valores por defecto (el dueño los fija en la Fase 0; los modos de §6b los ajustan dentro de estos techos):**
- Riesgo por operación: según modo (0,5 % Escudo → tope ½ Kelly en Ataque).
- Pérdida máxima diaria: 3 % del capital base / 30 % del capital de ataque → se para hasta el día siguiente y pasa a Escudo.
- Pérdida máxima semanal: 6 % del capital base / 100 % del de ataque → se para y exige revisión humana.
- Apalancamiento máximo: según modo, margen **aislado** siempre; el stop debe quedar lejos de la liquidación (validado antes de cada orden).
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
3. **Capital:** 500 $ iniciales, objetivo +800–1000 $/semana (confirmado). ¿Qué reparto base/ataque (propuesta 70/30)? ¿Cuánto aceptas perder entero antes de parar todo?
4. **Pares:** ¿BTC/ETH solamente, top 20, o también altcoins pequeñas?
5. **Estilo y temporalidad:** ¿scalping (minutos), intradía (horas) o swing (días)?
6. **TradingView:** ¿qué plan tienes? ¿Tienes ya indicadores o estrategias Pine propias que quieras integrar?
7. **Mac:** ¿qué modelo? ¿Puede quedarse encendido 24/7 o prefieres un VPS desde el principio?

---

*Aviso: este sistema es una herramienta. No garantiza beneficios; los mercados cripto con apalancamiento pueden hacer perder todo el capital asignado. Las puertas de validación existen para reducir ese riesgo, no para eliminarlo.*
