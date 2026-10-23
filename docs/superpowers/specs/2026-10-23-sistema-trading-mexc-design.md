# Sistema de Trading MEXC + TradingView — Diseño y Plan Maestro (v2)

> **Estado:** BORRADOR PARA APROBACIÓN. No se ha construido nada. La ejecución empieza cuando el repo esté en el Mac del dueño y él apruebe este documento.
> **Versión:** v2 · 2026-10-23
> **Convenciones:** todas las horas internas en **UTC**; importes en **USDT**; "R" = la cantidad arriesgada en una operación (distancia entrada→stop × tamaño). Las marcas *(decisión de Claude)* indican elecciones del diseñador que el dueño puede cambiar. Las marcas **[VERIFICAR F0]** son datos externos que se comprueban en la Fase 0 antes de construir encima.

---

## Índice
1. Intención, metas y anti-metas
2. Objetivo de rendimiento y lo que implica
3. Realidades técnicas verificadas
4. Enfoques considerados y elección
5. Arquitectura: 10 departamentos
6. Especificación por departamento
7. Contratos de datos
8. Metodología: embudo de validación
9. Motor de riesgo: fórmulas, modos y disyuntores
10. Ejecución en MEXC
11. Integración con TradingView
12. Departamentos como agentes de Claude Code
13. Operación en el Mac (24/7, seguridad, recuperación)
14. Estrategia de pruebas
15. Fases, tareas y criterios de aceptación
16. Logística: checklist del dueño y costes
17. Riesgos del proyecto y mitigaciones
18. Lo que queda a criterio del constructor
19. Preguntas abiertas para el dueño
20. Glosario
21. Fuentes

---

## 1. Intención, metas y anti-metas

**Intención.** Construir un sistema de trading de cripto **propio y privado** para operar en **MEXC** (spot y futuros perpetuos USDT-M), con **TradingView** para gráficos, indicadores propios y señales. Está organizado en **departamentos** (módulo de código + agente de Claude) y sigue una **metodología propia** que decide con pruebas qué estrategia merece dinero real y cuánto riesgo puede asumir.

**Referencia.** [`dan-ai-lab/day-trader-fr`](https://github.com/dan-ai-lab/day-trader-fr): 11 skills de Claude para acciones de EE. UU. Tomamos de ella:
- la cadena de decisión `scanner → news → entry → exit → timemachine → budget → risk → broker`;
- el **veto de riesgo** (`PASS`/`BLOCK`);
- la simulación de 10 000 caminos antes de cada operación;
- la confirmación explícita por ticket;
- los tests offline con fixtures.

Lo que descartamos: el mercado (acciones), los datos (Yahoo/SEC), los brókers (Alpaca/IBKR), el horario NYSE y la restricción a largos.

**Metas**
1. Datos completos, limpios y auditables de MEXC, más contexto externo.
2. Gráficos precisos: los indicadores propios deben coincidir con TradingView (error < 0,1 %).
3. Simulación realista: comisiones, slippage, funding, ambigüedad intravela, walk-forward, Monte Carlo y estrés.
4. Ejecución segura en MEXC, con riesgo que se adapta al mercado (modos) y que nadie puede saltarse.
5. Funcionamiento 24/7 con alertas en el móvil y botón de emergencia.
6. Diario completo y mejora continua semanal.

**No-metas (por ahora):** alta frecuencia o market making; otros exchanges (la arquitectura los permitirá vía ccxt); modelos de IA "caja negra" que no se puedan explicar ni validar.

**Anti-metas (fracaso aunque "funcione"):**
- Una estrategia con dinero real sin pasar el embudo (§8).
- Cualquier vía para **retirar fondos**, operar sin stop en el exchange o saltarse el veto.
- Subir el riesgo para "recuperar" pérdidas.
- Un backtest brillante que muere en vivo (sobreoptimización).
- Que el dueño no entienda por qué se abrió una posición.

---

## 1b. Principio rector: NO PERDER el capital

**Decisión del dueño:** el plan es **no perder**; el control de riesgo es la prioridad absoluta. Orden de prioridades del sistema, que resuelve cualquier conflicto entre reglas:

1. **Preservar el capital** (los 500 USDT iniciales).
2. **Consistencia:** semanas positivas pequeñas antes que semanas enormes.
3. **Objetivo de rendimiento** (+800–1000/semana): se persigue **solo con ganancias ya obtenidas**, nunca con el capital inicial.

Honestidad: ningún sistema puede garantizar que *nunca* se pierda una operación ni una semana. Lo que este diseño garantiza es que **la pérdida máxima del capital inicial está limitada y es conocida de antemano** (el suelo, §9.4), y que no se arriesga dinero real hasta que una estrategia haya demostrado ventaja en simulación y en papel, donde perder cuesta 0.

### Cómo se traduce
- **Capital protegido (500 USDT):** solo modos Escudo y Normal, con riesgo bajo por operación y **suelo duro** de −10 % (450 USDT): si se toca, el sistema se detiene por completo (HALT) hasta una revisión con el dueño.
- **Bolsa de ganancias ("dinero de la casa"):** al cierre de cada semana positiva, el 50 % de la ganancia realizada sobre el capital protegido pasa a la bolsa. **Solo la bolsa** puede usar Ataque o Turbo. Si la bolsa se pierde entera, el capital inicial sigue intacto.
- **El otro 50 % de la ganancia** se queda en el capital protegido (que crece) o se retira, a elección del dueño.
- **Primera semana en vivo = 0 en la bolsa:** el modo agresivo solo existe cuando ya se ha ganado algo.

### Qué significa el suelo con distintas calidades de estrategia
12 semanas, 30 operaciones/semana, capital protegido al 1 % por operación, suelo en 450. Script: `docs/analisis/mc_capital_protegido.py`.

| Ventaja de la estrategia | P(tocar el suelo −10 %) | P(acabar por debajo de 500) |
|---|---|---|
| Excepcional (55 %, 2,5R) | 0,2 % | 0,2 % |
| Buena (50 %, 2R) | 2,4 % | 1,9 % |
| Realista justa (45 %, 1,5R, casi sin ventaja tras costes) | 80 % | 66 % |
| Sin ventaja (40 %, 1,5R) | 99 % | 98 % |

**Lectura:** el suelo convierte "perderlo todo" en "perder como mucho 50 USDT". Pero la única forma de **no perder** de verdad es no llevar a dinero real una estrategia sin ventaja clara. Por eso el embudo (§8) es la pieza principal del control de riesgo, y sus umbrales se endurecen (ver §8).

---

## 2. Objetivo de rendimiento y lo que implica

**Objetivo del dueño:** empezar con **500 USDT** y ganar **+800 a +1000 USDT o más por semana**, es decir, multiplicar el capital por 2,6–3 cada semana (≈ +115–145 USDT/día). Se acepta más riesgo cuando el mercado lo permita, y el sistema debe saber reducirlo cuando no.

### 2.1 Simulación del objetivo
Monte Carlo de 100 000 caminos, riesgo fijo del 10 % por operación y coste de 0,1R por operación. Scripts: `docs/analisis/mc_objetivo.py` y `docs/analisis/mc_objetivo_800.py`.

| Ventaja de la estrategia | P(+800 en 1 semana), 20 ops | P(+800), 40 ops | P(perder >50 % esa semana), 40 ops |
|---|---|---|---|
| Excepcional (55 % de acierto, 2,5R) | 75 % | 96 % | 2 % |
| Buena (50 %, 2R) | 25 % | 56 % | 11 % |
| Realista (45 %, 1,5R) | 2 % | 8 % | 44 % |

Con ventaja realista y 20 % de riesgo, el 46 % de los caminos termina en 4 semanas con menos del 10 % del capital.

**Con los topes de la versión anterior (70/30)** (base 350 al 2 %, ataque 150 al 10 %, operaciones repartidas a medias; script `docs/analisis/mc_objetivo_topes.py`):

| Ventaja | P(+800 en 1 semana), 20 ops | P(+800), 40 ops | Ganancia semanal mediana (40 ops) |
|---|---|---|---|
| Excepcional | 1,8 % | 29 % | +540 |
| Buena | 0 % | 2,9 % | +177 |
| Realista | 0 % | 0 % | −9 |

**Resolución (decisión del dueño: no perder, §1b):** el capital inicial ya no se arriesga en modo agresivo. El objetivo de +800/semana se persigue solo con la bolsa de ganancias, así que llegar a él es **progresivo**: primero hay que acumular ganancias con riesgo bajo, y solo después el modo Ataque puede multiplicarlas.

### 2.2 Consecuencias de diseño
1. **El motor del objetivo es la ventaja (edge), no el apalancamiento.** Por eso la misión n.º 1 del sistema es *encontrar y demostrar* ventaja (§8) antes de apostar fuerte.
2. **El riesgo permitido se deriva de la ventaja medida** (½ Kelly sobre el límite inferior del intervalo de confianza, §9.2), nunca del objetivo.
3. **El objetivo exige muchas operaciones** (scalping o intradía activo), y con 500 USDT **las comisiones son decisivas**. Ejemplo: con 10x de apalancamiento (5000 USDT nocionales) y 0,02 % de taker en entrada y salida, cada operación cuesta 2 USDT; 40 operaciones a la semana suman 80 USDT, el **16 % del capital**. Si la entrada y los objetivos se ejecutan como *maker* (0 % [VERIFICAR F0]), el coste se reduce aproximadamente a la mitad. Las salidas por stop siguen siendo taker y el slippage no desaparece. Por tanto la ejecución es **maker-first** (§10, punto 3).
4. El objetivo se trata como **meta semanal medida**, no como promesa: el sistema informa del avance contra la meta, y estar por debajo **nunca** sube el riesgo.

---

## 3. Realidades técnicas verificadas

| Tema | Dato | Estado | Consecuencia |
|---|---|---|---|
| Dominio API de futuros MEXC | Desde el 12-ene-2026 la API de futuros está en `https://api.mexc.com`. `contract.mexc.com` dejó de funcionar el 19-ene-2026 a las 16:00 UTC. Parámetros y firma, sin cambios. | Fuente oficial MEXC | Configurar `api.mexc.com`; ignorar ejemplos antiguos con `contract.mexc.com`. |
| Órdenes de futuros por API | Hubo épocas con la creación restringida. Un tercero afirma que se reabrió el 31-mar-2026 (salvo la Zona de Innovación). | **[VERIFICAR F0]** | Prueba real en F0: crear y cancelar una orden mínima. **Prohibido** usar "bypasses" no oficiales. Si no funciona, se empieza en spot. |
| Comisiones de futuros USDT-M | Maker 0 %, taker 0,02 % en el nivel base (varias fuentes; una dice 0,02/0,06). Zona de Innovación: 0,04/0,10. Las liquidaciones no tienen tarifa cero. Puede variar por región. | **[VERIFICAR F0]** en la cuenta | Las comisiones se leen de la API/cuenta, nunca se escriben a mano. Se excluye la Zona de Innovación por defecto. |
| Comisiones spot | Se suelen citar maker 0 % / taker 0,05 %. | **[VERIFICAR F0]** | Igual que arriba. |
| Mínimos spot | Orden mínima ≈ 1 USDT; cada par tiene sus reglas. | Help center MEXC | Leer reglas por par de `exchangeInfo` y validar antes de enviar. |
| Límite de órdenes spot | Órdenes batch limitadas a 5/s (anuncio de mar-2025); batch de hasta 20 órdenes. | **[VERIFICAR F0]** | Limitador de peticiones centralizado (§10.6). |
| ccxt + MEXC swap | Soporta swap con `defaultType: swap`. Error conocido 7002 ("Position mode mismatch") si `openType`/`leverage` o el modo de posición no coinciden con la cuenta. | Docs ccxt + issue | Al arrancar se leen y fijan explícitamente el modo de posición, el tipo de margen y el apalancamiento. Hay tests para cada tipo de orden. |
| Webhooks de TradingView | Solo puertos 80/443, sin IPv6, **la petición se cancela a los 3 s**. Salen de 4 IPs: 52.89.214.238, 34.212.75.30, 54.218.53.128, 52.32.178.7. Requieren plan de pago (Essential o superior) y probablemente 2FA. | Oficial (red); terceros (plan/2FA) | El receptor responde en < 100 ms y procesa en cola (§11). Allowlist de esas IPs. |
| Mac doméstico | Se duerme, cambia de IP, se actualiza, pierde red. | — | Hasta la Fase 3, Mac con `launchd`/`pmset`. Desde la Fase 4, motor en VPS con IP fija; el Mac queda como laboratorio y panel (§13). |

---

## 4. Enfoques considerados y elección

| Enfoque | Qué es | Pros | Contras |
|---|---|---|---|
| A. TradingView + servicio de terceros (AlgoWay, 3Commas…) | Pine Script genera alertas; un tercero ejecuta en MEXC. | Rápido. | Tus claves en un tercero; datos y simulación limitados; sin departamentos ni metodología propia. |
| **B. Sistema propio en Python + TradingView como capa visual y de señales** ✅ | Motor propio de datos, análisis, simulación, riesgo y ejecución. TradingView para gráficos y como fuente opcional de señales. Claude Code coordina los departamentos. | Control total, auditable, simulación seria, ampliable, privado. | Más trabajo inicial. |
| C. Adaptar un framework (Freqtrade, Hummingbot, Nautilus) | Partir de un bot open source. | Backtest y dry-run hechos. | Metodología ajena; soporte irregular de MEXC futuros; no es "nuestro". |

**Elegido: B** *(decisión de Claude, coherente con "crea nuestro propio sistema")*. Se toman ideas de C: el dry-run de Freqtrade y el diseño event-driven de Nautilus, sin depender de ellos.

---

## 5. Arquitectura: 10 departamentos

```
                ┌──────────────── DIRECCIÓN (orquestador Claude) ─────────────────┐
                │ briefing · prioriza · explica en español · nunca envía órdenes  │
                └──────────────────────────────────────────────────────────────────┘
 ┌─────────┐   ┌───────────┐   ┌────────────┐   ┌────────────┐   ┌──────────┐   ┌───────────┐
 │1 DATOS  │──▶│2 ANÁLISIS │──▶│4 ESTRATEGIA│──▶│5 SIMULACIÓN│──▶│6 RIESGO  │──▶│7 EJECUCIÓN│──▶ MEXC
 └─────────┘   │  TÉCNICO  │   └────────────┘   └────────────┘   │ (VETO)   │◀─┐└───────────┘
      │        └───────────┘         ▲  ▲       ┌────────────┐   └──────────┘  │      │ fill
      │                              │  │       │5b ESCENARIOS│◀────────────────┼──────┘
      │                              │  │       │ en posición │─────────────────┘ (gestiona vía Riesgo)
      │                              │  │       └────────────┘
      │        ┌───────────┐         │  └── TradingView webhook (receptor §11)        ▼
      └───────▶│3 CONTEXTO │─────────┘                                       ┌──────────────┐
               └───────────┘                                                 │8 MONITOREO   │
 ┌───────────┐                       ┌─────────────┐                         │ Telegram/KILL│
 │9 GRÁFICOS │◀─── todos             │10 AUDITORÍA │◀─── todos (solo añade)  └──────────────┘
 └───────────┘                       └─────────────┘
```

**Principios de arquitectura**
- **Event-driven:** un bus interno de eventos (`MarketEvent`, `SignalEvent`, `SetupEvent`, `RiskDecision`, `OrderEvent`, `FillEvent`, `ScenarioEvent`, `ManageEvent`, `AlertEvent`). **El mismo código** corre en backtest, papel y vivo; solo cambia la fuente de datos y el adaptador de ejecución.
- **Separación de poderes:** solo el Dept. 7 habla con la API de órdenes, y solo con un `RiskDecision=PASS` firmado (hash del ticket + caducidad de 60 s).
- **Todo se registra:** cada evento se escribe en el diario antes de producir efectos.
- **Configuración declarativa:** estrategias, riesgo y modos en YAML versionado. Cambiar un límite queda en git.

---

## 6. Especificación por departamento

### Dept. 1 — Datos
- **Fuentes MEXC:** velas 1m, 5m, 15m, 1h, 4h y 1D (REST para histórico, WebSocket en vivo), trades, libro L2 (top 20 niveles, snapshot cada 1 s + deltas), funding (actual, previsto e histórico), open interest, mark price e index price, reglas de cada par (`exchangeInfo` / contract detail).
- **Histórico profundo:** si MEXC no da suficiente histórico de 1m, se usan los volcados públicos de Binance (`data.binance.vision`) **solo para investigación** en BTC/ETH, marcados `source=binance_proxy`. Toda estrategia debe re-validarse con datos de MEXC antes de la puerta G6.
- **Calidad:** detección de huecos, duplicados, velas con volumen 0 y saltos > 10 desviaciones estándar. Relleno de huecos por REST. Informe diario `data_quality`.
- **Almacenamiento:** Parquet particionado `data/{exchange}/{market}/{symbol}/{tf}/YYYY-MM.parquet`, con vistas DuckDB encima.
- **Universo por defecto** *(decisión de Claude)*: BTCUSDT y ETHUSDT, más hasta 8 pares del top 20 por volumen de futuros, con spread medio < 0,05 % y fuera de la Zona de Innovación.
- **Aceptación:** 12 meses de 1m sin huecos sin explicar en el universo; latencia WS→bus < 500 ms (p95).

### Dept. 2 — Análisis técnico
- **Indicadores** (implementación propia, con tests "golden" contra exportaciones CSV de TradingView): EMA/SMA, VWAP (anclado por sesión y por evento), RSI, MACD, ATR, ADX/DMI, Bollinger + ancho de banda, Keltner, Ichimoku, Supertrend, Choppiness Index, OBV.
- **Estructura de mercado:** pivotes (máximos y mínimos), BOS/CHoCH (rotura y cambio de estructura), zonas de oferta y demanda, gaps de valor (FVG), barridos de liquidez.
- **Vistas alternativas del precio:** Heikin Ashi, Renko (tamaño de ladrillo = ATR), velas de rango, velas de volumen.
- **Volumen y order flow:** perfil de volumen (POC, VAH/VAL, nodos de bajo volumen), delta por vela, CVD, footprint construido a partir de los trades y desequilibrio del libro.
- **Clasificador de régimen** (por símbolo y temporalidad; umbrales iniciales que se calibran en el Laboratorio):

| Régimen | Regla inicial |
|---|---|
| TENDENCIA_ALCISTA / BAJISTA | ADX(14) > 25 y EMA50 con pendiente en la dirección y precio del mismo lado de EMA200 |
| RANGO | ADX < 20 y Choppiness > 61,8 |
| COMPRESIÓN | Ancho de Bollinger en percentil < 10 de los últimos 90 días |
| EXPANSIÓN | ATR en percentil > 90 y rotura de estructura reciente |
| CAOS | ATR en percentil > 98, o movimiento > 5 % en 15 min, o spread > 3× la media |

- **Multi-timeframe:** cada análisis produce una lectura por marco superior / medio / inferior y una puntuación de alineación de 0 a 3.
- **Salida:** `Features` por símbolo, temporalidad y vela cerrada. **Solo se usan velas cerradas**, sin mirar al futuro (comprobado por test).

### Dept. 3 — Contexto y sentimiento
- **MEXC:** funding (nivel y percentil), OI (cambio en 1h/4h/24h), basis entre perpetuo y spot.
- **Externos gratuitos** *(decisión de Claude)*: Fear & Greed (alternative.me), dominancia de BTC y capitalización (CoinGecko), calendario macro (FOMC, CPI, NFP; fuente por decidir en F2), desbloqueos de tokens del universo.
- **Opcionales de pago** (se deciden en F2 según presupuesto): mapas de liquidaciones agregadas (p. ej. Coinglass), noticias en tiempo real.
- **Salida:** `Context`, con banderas: `macro_event_window` (±30 min de un evento de alto impacto), `funding_extreme` (percentil > 95 o < 5), `oi_spike`.

### Dept. 4 — Estrategia / Research
- Cada estrategia es una clase con `on_bar(features, context) → Setup | None` y una ficha YAML: `id`, hipótesis, temporalidades, regímenes permitidos, modos permitidos, parámetros, estado en el embudo (G0–G8).
- **Setup** = dirección, tipo de entrada (límite/stop), precio de entrada, stop, objetivos (TP1/TP2), invalidación, caducidad, calidad (A+/A/B), razón en texto.
- **Calidad del setup** *(decisión de Claude)*: A+ = alineación 3/3 + régimen permitido + contexto sin banderas en contra + R:R ≥ 2. A = alineación ≥ 2/3 y R:R ≥ 1,5. B = el resto, que **nunca** se opera en vivo.
- **Cartera de estrategias** *(decisión de Claude por delegación del dueño; todas son hipótesis que deben pasar el embudo)*:

| ID | Estrategia | Marcos (dirección / setup / entrada) | Régimen | Idea | Stop | Salida base |
|---|---|---|---|---|---|---|
| **S1** | Retroceso en tendencia MTF (núcleo) | 4h / 1h / 15m | TENDENCIA | Entrar a favor de la tendencia mayor en el retroceso a EMA21/zona de demanda con vela de rechazo | Bajo el mínimo del retroceso − 0,25 ATR | TP1 1,5R; runner con trailing por estructura |
| **S2** | Ruptura de sesión | 1h / 15m / 5m | COMPRESIÓN → EXPANSIÓN | Rango de Asia (00–07 UTC) roto en la apertura de Europa o EE. UU. con volumen > 1,5× y CVD a favor | Mitad del rango | TP1 1R; runner hasta 3R o fin de sesión |
| **S3** | Squeeze de volatilidad | 4h / 1h / 15m | COMPRESIÓN | Bollinger dentro de Keltner ≥ N velas; entrar en la primera vela de expansión a favor del marco mayor | Lado opuesto del squeeze | Trailing por ATR desde el inicio |
| **S4** | Squeeze por funding/OI | 1h / 15m / 5m | Cualquiera menos CAOS | Funding en percentil extremo + OI subiendo + rotura **contra** la masa posicionada | Más allá del extremo previo | Rápida: TP1 1R, TP2 2,5R |
| **S5** | Barrido de liquidez | 1h / 15m / 5m | RANGO o TENDENCIA | Barrido de un máximo/mínimo de sesión o día seguido de CHoCH en 5m | Más allá de la mecha del barrido | TP1 en el lado opuesto del rango; runner |
| **S6** | Reversión a VWAP (scalping maker) | 15m / 5m / 1m | RANGO | Desviación ≥ 2σ del VWAP de sesión con agotamiento; solo órdenes maker | 3σ | VWAP; sin runner |
| **S7** *(fase posterior)* | Order flow: absorción y divergencia de CVD | 15m / 5m / 1m | Cualquiera | Precio hace un nuevo extremo y CVD no; absorción en el libro | Más allá del extremo | Por definir tras ≥ 3 meses de datos grabados |
| **TV** | Señales TradingView del dueño | Según el script | Según la ficha | Entran como setups y pasan Simulación y Riesgo | Las del script | Política del motor de escenarios |

- **Asignador por régimen (meta-estrategia):** cada régimen activa solo las estrategias compatibles. Si dos estrategias dan señal en el mismo símbolo, se queda la de mayor R esperado según la simulación. La exposición correlacionada se limita a nivel de cartera (§9.4).

### Dept. 5 — Simulación
- **Backtest event-driven** con el mismo código que en vivo:
  - Comisiones maker/taker reales por par.
  - Slippage: un modelo proporcional al spread y la volatilidad para órdenes taker; probabilidad de ejecución para las maker (solo se ejecuta si el precio *atraviesa* el límite).
  - Funding cada 8 h [VERIFICAR F0 intervalo por par].
  - Latencia simulada de 300 ms.
  - Mínimos y redondeos de cada par.
- **Ambigüedad intravela:** si el stop y el objetivo caen dentro de la misma vela, se resuelve con datos de 1m. Si sigue siendo ambiguo, se asume **el stop** (pesimista).
- **Precio de disparo:** en vivo, los stops se disparan por *mark price* (§10). El backtest usa la serie de mark price cuando existe; si no, el último precio más un margen de ±0,05 % *(decisión de Claude)*. En G6 se mide la diferencia real.
- **Datos de order flow:** los trades y el libro L2 se **graban desde el primer día de la F1**, porque MEXC no da histórico profundo de ellos. Las estrategias que dependen de CVD, footprint o desequilibrio del libro se aplazan hasta tener ≥ 3 meses grabados, y para ellas G1 exige ≥ 3 meses en lugar de 12 *(decisión de Claude)*.
- **Walk-forward:** ventanas deslizantes (p. ej. 6 meses de entrenamiento y 1 de prueba), con métrica de eficiencia WFE = rendimiento fuera de muestra / rendimiento en muestra.
- **Robustez:** barrido de parámetros ±20 % (mapa de calor), otros pares y otros regímenes.
- **Estadística anti-sobreoptimización:** Deflated Sharpe Ratio, Probabilidad de Sobreajuste del Backtest (PBO por CSCV) e intervalo de confianza por bootstrap de la expectativa en R.
- **Monte Carlo:** (a) remuestreo de la secuencia de operaciones (10 000 caminos) para la distribución del drawdown y de la ruina; (b) bootstrap por bloques de velas para el abanico de caminos de precio de un setup concreto: P(objetivo primero), P(stop primero), P(ninguno al caducar).
- **Estrés:** −20 % en 1 h; gap de 3 % a través del stop; funding 10× el normal durante 3 días; API caída 15 min con posición abierta; spread 10×.
- **Salida:** `SimReport` (métricas, intervalos de confianza, gráficos y veredicto por puerta).

### Dept. 5b — Motor de escenarios en posición ("sala de guerra")
**Requisito del dueño:** en cuanto se ejecuta una orden, se generan **todos los escenarios posibles** para gestionar la operación con la máxima efectividad.

**Disparo y tiempos:**
- Se activa con cada `FillEvent` de entrada, usando el precio real de ejecución.
- **Vía rápida (< 1 s):** escenarios precalculados durante la evaluación del setup, reajustados al precio real.
- **Vía completa (< 5 s):** recálculo entero.
- **Actualización** en cada vela cerrada de la temporalidad de entrada y ante eventos: precio cruza un nivel clave, pico de OI, ventana macro, hora de funding, ejecución parcial.

**Cuatro generadores combinados:**
1. **Análogos históricos:** búsqueda k-NN de las N (≥ 500) situaciones pasadas más parecidas (régimen, alineación multi-timeframe, ATR, funding, OI, sesión, distancia a niveles) y sus caminos de precio reales posteriores.
2. **Bootstrap por bloques** de los rendimientos recientes, condicionado al régimen actual.
3. **Modelo paramétrico con saltos:** volatilidad actual más saltos calibrados con las mechas históricas del par.
4. **Escenarios de evento deterministas:** ventana macro, cobro de funding, cascada de liquidaciones hacia los clústeres cercanos, gap del 3 %, API caída.

En total 10 000 caminos o más, ponderados por la calidad histórica de cada generador (se mide en el diario).

**Seis escenarios canónicos**, cada uno con probabilidad, camino típico, MFE/MAE esperados y tiempo esperado:

| Escenario | Señal que lo confirma en vivo | Jugada pre-planificada |
|---|---|---|
| 🚀 Continuación fuerte | Rompe TP1 rápido, CVD a favor, estructura intacta | Trailing por estructura/ATR; **piramidar con la bolsa de ganancias** (stop en BE, riesgo total ≤ R inicial) |
| 📈 Continuación lenta | Avanza sin impulso | Parcial en TP1, stop a BE + costes, runner con trailing amplio |
| ↩️ Retroceso sano | Vuelve a la zona de entrada sin romper la invalidación | Mantener; **no mover el stop**; no añadir |
| ➖ Rango / estancamiento | No llega a +0,5R en N velas | **Stop por tiempo:** salir cerca de 0R en lugar de esperar al stop |
| ❌ Reversión | CHoCH en contra, CVD girando, régimen cambia | **Salida anticipada** antes del stop (pérdida < 1R) |
| ⚡ Evento extremo | Mecha > 3 ATR, cascada de liquidaciones, ventana macro | El stop del exchange protege; antes de un evento programado se reduce o se cierra la posición |

**Selección de la política de salida óptima:**
- Para cada operación se evalúan sobre los caminos simulados unas 50 combinaciones de salida: % en TP1, distancia de TP1, tipo y distancia del trailing, stop por tiempo, mover a BE sí/no.
- Se elige la que **maximiza el R esperado** con estas condiciones: P(pérdida > 1R) = 0, garantizado por el stop; y percentil 5 del resultado ≥ el de la política por defecto de la estrategia.
- **Nunca se elige una política solo porque "suene mejor":** cada estrategia valida en backtest (G1–G3) que la selección dinámica supera a su política fija. Si no la supera, usa la fija.

**Reglas duras del motor (no negociables):**
- Solo puede **reducir** riesgo: mover el stop a favor, salidas parciales, cierre anticipado.
- **Nunca aleja el stop** ni añade riesgo por encima del R inicial.
- Las piramidaciones solo con la bolsa de ganancias, en modo Ataque/Turbo y con el stop de toda la posición en BE.
- Todas sus acciones pasan por Riesgo como un setup más (`ManageEvent → RiskDecision`).

**Salidas:**
- Telegram: "Operación abierta: escenarios 🚀 22 % · 📈 25 % · ↩️ 18 % · ➖ 15 % · ❌ 17 % · ⚡ 3 %; R esperado +0,6; política elegida …".
- Panel: abanico de caminos y escenarios dibujados sobre el gráfico.
- Diario: escenario previsto frente a escenario ocurrido, para mejorar los pesos de los generadores.

### Dept. 6 — Riesgo (con veto)
Se detalla en §9. Es la única autoridad que emite `PASS`/`BLOCK` y fija el tamaño. Su configuración (`config/risk.yaml`) solo la cambia el dueño. Un hook de Claude impide editarla sin confirmación (§12).

### Dept. 7 — Ejecución
Se detalla en §10. Tiene adaptadores `PaperBroker` (simulado con datos en vivo) y `MexcBroker` (ccxt + REST oficial de respaldo).

### Dept. 8 — Monitoreo y alertas
- **Heartbeat** cada 30 s. Alarmas: WS sin datos > 10 s, error de API > 3/min, reloj desviado > 500 ms, posición sin stop en el exchange, discrepancia entre posiciones locales y las del exchange.
- **Telegram:** notifica entradas, salidas, cambios de modo, vetos importantes, alarmas, informe diario (00:00 UTC) e informe semanal (domingo).
- **Comandos de Telegram** (solo responde al chat ID del dueño): `/estado`, `/posiciones`, `/modo`, `/pausa`, `/reanudar`, `/kill`, `/si <ticket>`, `/no <ticket>`, `/turbo <horas>`.
- **KILL:** cancela todas las órdenes, cierra todas las posiciones a mercado, pone el motor en `HALTED` y exige un `/reanudar` manual. Se prueba en cada fase.

### Dept. 9 — Gráficos
- **TradingView (Pine Script v6):**
  - `TS-Regime`: régimen y alineación multi-timeframe.
  - `TS-Structure`: BOS/CHoCH, zonas y FVG.
  - `TS-Flow`: delta/CVD aproximado.
  - `TS-Signals`: estrategias del Dept. 4 portadas a Pine, para verlas y para alertas.
  - Plantilla de alerta JSON (§11).
- **Panel propio** (FastAPI + TradingView Lightweight Charts, o Streamlit *(decisión de Claude: se decide en F1 con un prototipo)*):
  - Velas + indicadores.
  - Entradas, stops y objetivos reales.
  - Abanico Monte Carlo (percentiles 5/50/95) sobre el gráfico.
  - Curva de capital base y de ataque, meta semanal frente a lo real.
  - Modo actual y registro de vetos.

### Dept. 10 — Auditoría / Diario
- **Diario:** SQLite/DuckDB *append-only*. Cada señal, setup, simulación, decisión de riesgo, orden, ejecución, cambio de modo y comando, con la marca de tiempo y la versión de configuración (hash de git).
- **Informe semanal:** PnL por estrategia, modo, régimen y sesión; vivo frente a simulado (¿dentro del intervalo?); coste de comisiones y slippage; las 3 mejores y las 3 peores operaciones con su gráfico; recomendaciones (bajar una estrategia a papel, etc.).
- **Degradación automática:** si una estrategia en vivo queda fuera del percentil 5 de su simulación durante 2 semanas, vuelve a G6 (papel).

---

## 7. Contratos de datos (resumen)

```text
Candle      {symbol, tf, ts_open, o, h, l, c, v, quote_v, n_trades, source}
Trade       {symbol, ts, price, qty, side, trade_id}
BookSnap    {symbol, ts, bids[[p,q]x20], asks[[p,q]x20]}
Funding     {symbol, ts, rate, next_ts, predicted_rate}
OpenInt     {symbol, ts, oi}
Features    {symbol, tf, ts, indicators{...}, regime, mtf_alignment, structure{...}}
Context     {ts, fear_greed, btc_dom, flags{macro_event_window, funding_extreme, oi_spike}}
Setup       {setup_id, strategy_id, symbol, side, entry_type, entry, stop, tp[], invalidation,
             expires_at, quality, reason, source: internal|tradingview}
SimReport   {setup_id|strategy_id, p_target_first, p_stop_first, p_none, exp_R, ci95_exp_R, ...}
RiskDecision{setup_id, verdict: PASS|BLOCK, reasons[], mode, risk_usdt, qty, leverage,
             margin_bucket: base|ataque, liq_price, ticket_hash, valid_until}
ScenarioRep {position_id, ts, n_paths, scenarios[{name, prob, mfe_R, mae_R, eta}], exp_R,
             chosen_exit_policy, generator_weights}
ManageAction{position_id, action: move_stop|partial|close|add, params, reason, scenario}
Order       {client_order_id, ticket_hash, symbol, side, type, price, qty, reduce_only, post_only}
Fill        {client_order_id, exch_order_id, ts, price, qty, fee, fee_asset}
```

Todos los modelos se definen con `pydantic` y tienen tests de serialización.

---

## 8. Metodología: embudo de validación

Ninguna estrategia toca dinero sin pasar **todas** las puertas en orden. *(Umbrales iniciales: decisión de Claude; los ajusta el dueño en `config/gates.yaml`.)*

| Puerta | Prueba | Criterio para pasar |
|---|---|---|
| **G0 Hipótesis** | Regla escrita: qué ineficiencia explota y por qué existe. | Explicable en 3 frases; ≤ 5 parámetros libres. |
| **G1 Backtest** | ≥ 12 meses (ideal 24), costes reales, solo velas cerradas. | ≥ 200 operaciones; **IC95 inferior de la expectativa ≥ +0,15 R** después de costes (no basta con > 0: una ventaja "justa" toca el suelo, §1b); profit factor > 1,5; drawdown máx. < 15 % con el riesgo del modo Normal. |
| **G2 Walk-forward** | ≥ 6 ventanas. | WFE ≥ 0,5; ≥ 2/3 de las ventanas rentables. |
| **G3 Robustez** | Parámetros ±20 %, ≥ 3 pares, regímenes separados. | Sin "picos aislados"; rentable en ≥ 2/3 de las variantes. |
| **G4 Estadística** | Deflated Sharpe, PBO. | DSR > 0,95; PBO < 0,2. |
| **G5 Monte Carlo + estrés** | 10 000 caminos + escenarios del Dept. 5. | **P(tocar el suelo de 450 en 12 semanas) < 2 %** con el riesgo del modo Normal; ningún escenario de estrés supera los disyuntores (§9.4). |
| **G6 Papel** | 2–4 semanas en vivo con `PaperBroker`. | ≥ 30 operaciones; resultado dentro del IC90 simulado; coste real de ejecución ≤ el modelado. |
| **G7 Vivo mínimo** | Dinero real, modo Normal, tamaño mínimo. | ≥ 30 operaciones dentro del IC90; sin incidentes de ejecución. |
| **G8 Escalar** | Habilita Ataque/Turbo para esa estrategia. | Revisión semanal sin degradación (§6, Dept. 10). |

Cada estrategia tiene su ficha con el estado y la evidencia (enlaces a `SimReport`). Ninguna estrategia se "promociona" a mano saltándose una puerta. **Pasar G6 da el estado `G7-en-curso`**, que permite operar en vivo solo en modo Normal y con el tamaño mínimo del par. `MexcBroker` rechaza cualquier setup de una estrategia por debajo de `G7-en-curso`.

---

## 9. Motor de riesgo: fórmulas, modos y disyuntores

### 9.1 Tamaño de posición (futuros lineales USDT-M)
```
riesgo_usdt   = capital_del_bucket × riesgo_pct(modo, estrategia)
coste_por_ud  = entrada × fee_entrada + stop × fee_salida + slippage_estimado
cantidad      = riesgo_usdt / (|entrada − stop| + coste_por_ud)   → redondeo hacia ABAJO al paso del par
nocional      = cantidad × entrada
margen_máx    = capital_del_bucket / posiciones_máx (3)          # cada posición puede usar como mucho 1/3 del bucket
apalancamiento= ceil(nocional / margen_máx)                      # el MÍNIMO apalancamiento que cabe en ese margen
margen_asignado = nocional / apalancamiento                      # margen aislado real que se bloquea
Requisito: apalancamiento ≤ apalancamiento_máx(modo); si no → BLOCK
```
El apalancamiento no decide cuánto se arriesga (eso lo decide el stop). Solo decide cuánto margen se inmoviliza. Por eso se usa el mínimo posible.
Si la cantidad redondeada queda por debajo del mínimo del par → `BLOCK` (motivo: "tamaño mínimo excede el riesgo").

### 9.2 Tope de riesgo derivado de la ventaja (Kelly prudente)
```
p_low = límite inferior Wilson 95 % de la tasa de acierto (operaciones de G1–G7)
b_low = límite inferior bootstrap 95 % de (ganancia media / pérdida media)
kelly = p_low − (1 − p_low) / b_low
fracción_kelly(modo) = 0,5 en Escudo/Normal/Ataque · 0,75 en Turbo
tope_estrategia = max(0, fracción_kelly(modo) × kelly)   # sobre la estimación pesimista
riesgo_pct = min(tope_estrategia, techo_del_modo)
```
Turbo usa ¾ de Kelly a propósito: es la única excepción, solo en el bucket de ataque y con permiso explícito del dueño por sesión. Nunca se usa Kelly completo.
Si `kelly ≤ 0`, la estrategia no opera en vivo.

### 9.3 Comprobación de liquidación (margen aislado)
```
liq_long  ≈ entrada × (1 − 1/apal + mmr)      liq_short ≈ entrada × (1 + 1/apal − mmr)
Regla: |entrada − stop| ≤ 0,5 × |entrada − liq|   (el stop debe saltar mucho antes que la liquidación)
```
`mmr` (margen de mantenimiento) se lee por par desde la API. Si falla la regla, se baja el apalancamiento; si aun así falla → `BLOCK`.

### 9.4 Estructura de capital y disyuntores
*(Porcentajes iniciales: decisión de Claude. El dueño los fija en la F0.)*

*(Sustituye al reparto 70/30 anterior: ver el principio §1b.)*

| Bucket | Capital inicial | Modos permitidos | Pérdida diaria máx. | Pérdida semanal máx. | Suelo absoluto |
|---|---|---|---|---|---|
| **Base = capital protegido** | 500 USDT (100 %) | Escudo, Normal | 2 % → pausa hasta 00:00 UTC + Escudo al día siguiente | 4 % → pausa + revisión humana | **450 USDT (−10 %) → HALT total** hasta revisión con el dueño |
| **Ataque = bolsa de ganancias** | 0 USDT; se alimenta con el 50 % de la ganancia semanal realizada | Escudo, Normal, Ataque, Turbo | 30 % de la bolsa → pausa hasta 00:00 UTC | 100 % de la bolsa → pausa; **nunca se rellena desde la base** | — (perder la bolsa no toca el capital) |

**Separación física** *(decisión de Claude)*: si MEXC lo permite, la bolsa de ganancias vive en **otra subcuenta**. Así un error de software en Ataque no puede consumir margen del capital protegido. Si no es posible, la separación es contable y la impone Riesgo.

**Cómo se reparten modos y buckets:**
- **Cada bucket tiene su propio modo y sus propios contadores** (racha, drawdown desde el pico, pérdida diaria y semanal). El "drawdown ≥ 15 %" se mide sobre el pico del propio bucket.
- **Disparadores globales** (`macro_event_window`, salud del sistema degradada) ponen **ambos** buckets en Escudo. El régimen CAOS pone en Escudo solo las operaciones de **ese símbolo**.
- **Asignación de un setup a un bucket** (la hace Riesgo): si el setup es A+, la estrategia está en G8 y el bucket de ataque está en Ataque o Turbo → bucket de ataque. En cualquier otro caso → bucket base con su modo. Si el bucket elegido está en pausa, el setup no se reasigna al otro: BLOCK.

- **Trinquete:** cuando la bolsa de ganancias se duplica respecto a su máximo anterior, el 50 % de lo ganado vuelve al capital protegido (o se retira, a elección del dueño).
- **Racha:** 2 pérdidas seguidas en el capital protegido (3 en la bolsa) → Escudo durante 4 h.
- **Bloqueo de beneficios intradía:** si el día va en +2 % del capital protegido, el riesgo de las siguientes operaciones del día se reduce a la mitad. Si después se devuelve la mitad de esa ganancia, se para el día.
- **Exposición:** máximo 3 posiciones abiertas; exposición correlacionada (correlación de 1h a 30 días > 0,7) que cuenta como una sola posición a efectos de riesgo; nocional total ≤ 10× el capital total.
- **Sin promediar a la baja:** nunca se añade a una posición perdedora. Piramidación solo en Ataque, con el stop ya en break-even y el riesgo total de la posición ≤ el riesgo inicial.

### 9.4b Elegir las pérdidas, priorizar las ganancias (asimetría)
Principio del dueño: **las pérdidas se eligen de antemano, las ganancias se dejan correr.**
- **Pérdida elegida:** cada operación nace con su pérdida máxima fijada (1R = stop en el exchange) y una salida anticipada si el escenario ❌ se confirma. La pérdida media realizada objetivo es ≤ 0,8R.
- **Ganancia sin techo fijo:** por defecto ≥ 50 % de la posición queda como *runner* con trailing por estructura/ATR, en régimen de tendencia o expansión. La relación mínima R:R planificada es 1,5 (A) o 2 (A+).
- **Piramidación de ganadoras** con la bolsa de ganancias (§9.4), nunca promediar perdedoras.
- **Medición:** el informe semanal mide la asimetría real (ganancia media / pérdida media, MFE capturado, MAE soportado) y alerta si las pérdidas medias superan 1R (señal de slippage o de stops mal ejecutados).

### 9.5 Modos de riesgo (máquina de estados)

| Modo | Techo de riesgo/op | Apalancamiento máx. | Calidad mínima | Entrar | Salir |
|---|---|---|---|---|---|
| 🛡️ **Escudo** | 0,25 % | 2x | A+ | Cualquiera: disyuntor diario, 3 pérdidas seguidas, drawdown desde el pico ≥ 15 %, régimen CAOS, `macro_event_window`, salud del sistema degradada | A las 00:00 UTC o cuando haya pasado el motivo y lleven 4 h sin disparadores |
| ⚖️ **Normal** | 1 % (capital protegido) · 2 % (bolsa) | 3x | A | Por defecto | — |
| ⚔️ **Ataque** | ½ Kelly (máx. 10 %) | 10x | A+ con alineación 3/3 | **Todas:** estrategia en G8, régimen TENDENCIA o EXPANSIÓN, sin disparadores de Escudo en 24 h, PnL semanal del bucket ≥ −10 % (nunca para recuperar), salud OK | Cualquier condición deja de cumplirse, o una pérdida |
| 🚀 **Turbo** | ¾ Kelly (máx. 15 %) | 20x | A+ | Las de Ataque + `/turbo <horas>` del dueño (máx. 4 h por sesión) | Fin de la sesión, pérdida ≥ 15 % del bucket en la sesión, o cualquier disparador de Escudo |

**Bajar es inmediato; subir exige todas las condiciones.** Cada cambio de modo se notifica y se registra.

### 9.6 Lista de comprobación PASS/BLOCK (en orden)
1. Estado HALTED o pausa → BLOCK
2. Estrategia por debajo de `G7-en-curso` en vivo → BLOCK (en `G7-en-curso`: solo modo Normal y tamaño mínimo)
3. Calidad del setup < mínima del modo → BLOCK
4. Régimen no permitido por la estrategia → BLOCK
5. Disyuntores del bucket → BLOCK
6. Exposición/correlación excedida → BLOCK
7. Tamaño: mínimo del par > riesgo permitido → BLOCK
8. Liquidación (§9.3) imposible de cumplir → BLOCK
9. Simulación del setup: exp_R ≤ 0 tras costes → BLOCK
10. Precio actual a > 0,3 × |entrada − stop| de la entrada (setup "caducado") → BLOCK
11. → PASS con `ticket_hash` y `valid_until = ahora + 60 s`

**Vida del ticket:**
- `valid_until` cubre solo el **envío de la primera orden de entrada**. Las re-cotizaciones maker posteriores están permitidas mientras el setup no haya caducado (`expires_at`) y siga cumpliendo la regla 10.
- **En L2**, el "sí" del dueño **no** reutiliza el ticket: al confirmar, Riesgo **repite la lista completa** con el precio y el estado del momento. Si el resultado cambia (tamaño, modo o BLOCK), se informa y no se ejecuta sin un nuevo "sí".

---

## 10. Ejecución en MEXC

1. **Arranque:** sincronizar la hora (NTP, desviación < 500 ms) y leer las reglas de cada par, las comisiones de la cuenta, el modo de posición, el tipo de margen y el apalancamiento. Se fijan explícitamente: **margen aislado** y modo de posición acordado [VERIFICAR F0, hedge u one-way]. **Reconciliación:** las posiciones y órdenes del exchange mandan sobre el estado local.
2. **Órdenes idempotentes:** `client_order_id = {ticket_hash[:16]}-{n}`. Si se reintenta, se consulta antes de reenviar.
3. **Maker-first:** la entrada va como límite *post-only*. Si no se ejecuta en `T` segundos (por estrategia; scalping 20 s, intradía 120 s), se re-cotiza hasta 2 veces. Pasar a taker solo si el setup lo permite y la expectativa en R tras el coste taker sigue siendo > 0.
4. **Protección inmediata:** con la primera ejecución parcial se coloca el **stop en el exchange** (orden stop por *mark price*, reduce-only). Objetivos como límites reduce-only (TP1 50 %, TP2 resto). Mover el stop a break-even tras TP1 *(decisión de Claude, configurable por estrategia)*.
5. **Watchdog:** si una posición pasa > 5 s sin stop confirmado en el exchange, se cierra a mercado y se alerta.
6. **Limitador** centralizado por endpoint con margen del 50 % sobre los límites publicados; backoff exponencial ante 429/5xx.
7. **Spot** usa el mismo flujo, sin apalancamiento ni liquidación y solo en largo. **Problema conocido:** es probable que la API spot v3 de MEXC **no acepte órdenes stop ni OCO** [VERIFICAR F0]. En ese caso, la regla "stop siempre en el exchange" no se puede cumplir en spot, y se aplica esta excepción documentada:
   - **stop por software** vigilado por el motor y por el watchdog;
   - motor obligatoriamente en el VPS (no en el Mac);
   - solo modos Escudo/Normal;
   - riesgo por operación reducido a la mitad, por el riesgo de gap o de caída del motor.

   El dueño debe aceptar esta excepción antes de operar spot real.

---

## 11. Integración con TradingView

- **Endpoint:** `POST https://<túnel>/tv/<ruta-secreta-aleatoria>`.
- **Túnel:** Cloudflare Tunnel *(decisión de Claude; ngrok es la alternativa)*. Detrás del túnel, la IP real llega en `CF-Connecting-IP` y se comprueba contra las 4 IPs de TradingView.
- **Respuesta en < 100 ms:** se valida el esquema, se encola, se responde `200`. El procesamiento sigue en asíncrono (límite de 3 s de TradingView).
- **Mensaje de alerta:** lo construye **el propio script Pine** con `alert()` (mensaje dinámico), no una plantilla fija, para poder enviar stop y objetivos calculados. Ejemplo de lo que genera:
```json
{
  "secret": "<cadena literal generada en la F3 y pegada en el script/alerta>",
  "alert_id": "tv_mi_estrategia_v1-BTCUSDT.P-1729700000000",
  "strategy_id": "tv_mi_estrategia_v1",
  "symbol": "BTCUSDT.P",
  "tf": "15",
  "action": "entry",
  "side": "long",
  "price": 67250.5,
  "stop": 66900.0,
  "targets": [67950.0, 68600.0],
  "ts": "2026-10-23T14:15:00Z"
}
```
  - `secret` es un **texto literal** (TradingView no tiene variables secretas). Se rota si se filtra.
  - `alert_id` = estrategia + ticker + `time` de la vela, construido en Pine; sirve para deduplicar.
  - **Mapeo de símbolos:** TradingView usa nombres como `BTCUSDT.P` (perpetuo) o `BTCUSDT` (spot). Una tabla en `config/symbols.yaml` los traduce a los símbolos de MEXC (p. ej. `BTC_USDT` en futuros) y decide el mercado.
  - Para alertas de *strategies* de Pine, se pueden usar los placeholders `{{strategy.order.*}}`. Para *indicators*, solo `alert()` con mensaje dinámico.
- **Reglas:**
  - `secret` comparado en tiempo constante.
  - `alert_id` deduplicado durante 24 h.
  - El símbolo debe estar en la lista permitida.
  - Se descarta si `ts` tiene más de 30 s de antigüedad.
  - **Una alerta de TradingView es un `Setup` más:** pasa por Simulación y Riesgo como cualquier otro, nunca va directa a Ejecución.

---

## 12. Departamentos como agentes de Claude Code

**Estructura:**
- `.claude/agents/`: `director.md`, `datos.md`, `analista.md`, `contexto.md`, `estratega.md`, `simulador.md`, `riesgo.md`, `ejecucion.md`, `monitor.md`, `graficos.md`, `auditor.md`. Cada uno incluye su rol, sus herramientas permitidas, los comandos `tradesys` que puede usar y **lo que tiene prohibido**.
- `.claude/skills/` (comandos del dueño):

| Comando | Qué hace |
|---|---|
| `/briefing` | Estado del mercado, régimen, modo y meta semanal |
| `/analizar <par>` | Análisis multi-timeframe con gráfico |
| `/escanear` | Setups activos en todo el universo |
| `/simular <setup>` | Abanico y probabilidades |
| `/laboratorio <estrategia>` | Corre el embudo G1–G5 |
| `/riesgo` | Estado de los buckets, modos y disyuntores |
| `/operar <setup>` | Genera el ticket y pide "sí" en modo L2 |
| `/diario` | Resumen del diario |
| `/semana` | Informe semanal |
| `/kill` | Botón de emergencia |

**Barreras técnicas (no dependen de que el agente "se porte bien"):**
- Hook `PreToolUse` en `.claude/settings.json`: bloquea cualquier comando que invoque la ejecución real (`tradesys exec live …`) si no viene del flujo `/operar` con un ticket `PASS` vigente, y bloquea editar `config/risk.yaml` y `config/gates.yaml` sin confirmación.
- Las claves de MEXC nunca están en variables visibles para Claude: el proceso del motor las lee del Llavero de macOS.
- El agente "director" no tiene permiso de ejecución; solo coordina y explica.

**Niveles de autonomía:**

| Nivel | Comportamiento |
|---|---|
| L0 Analista | Solo analiza y simula |
| L1 Papel | Opera en simulación con datos en vivo, 24/7 |
| L2 Copiloto | Cada operación real necesita `/si <ticket>` en Telegram o "sí" en Claude, para ese ticket (como en la referencia) |
| L3 Automático | Solo estrategias en G8, dentro de modos y disyuntores; el dueño recibe todo por Telegram |

---

## 13. Operación en el Mac (24/7, seguridad, recuperación)

- **Procesos** (agentes `launchd` en `~/Library/LaunchAgents/`, con `KeepAlive`): `tradesys-data`, `tradesys-engine`, `tradesys-webhook`, `tradesys-monitor`, `cloudflared`.
- **Energía:** `sudo pmset -c sleep 0 disksleep 0` con el cargador conectado. Con la tapa cerrada (portátil), solo funciona con monitor externo; recomendado Mac de sobremesa o mini.
- **Logs:** `~/tradesys/logs/` rotados. El panel muestra el estado de cada proceso.
- **Recuperación tras caída o reinicio:** al arrancar, reconciliación (§10.1). Las posiciones abiertas mantienen su stop en el exchange aunque el Mac esté apagado; esa es la razón del stop en el exchange.
- **Seguridad:**
  - Clave API de MEXC **sin retiros**, solo lectura + trading, en una **subcuenta** dedicada con solo el capital del bot.
  - **IP en lista blanca:** con IP doméstica dinámica no es viable de forma fiable; por eso el motor pasa a un VPS con IP fija en la Fase 4. MEXC puede imponer caducidad a claves sin IP vinculada [VERIFICAR F0].
  - Secretos en el Llavero (`keyring`); `.env` y `data/` en `.gitignore`; escaneo de secretos (`gitleaks`) en el hook de pre-commit.
  - Telegram: el bot solo responde al chat ID del dueño.
  - 2FA en MEXC, TradingView, GitHub y Cloudflare.
- **Copias:** el diario y la configuración se copian a diario (Time Machine + copia cifrada opcional).

### 13.1 Reparto Mac / VPS desde la Fase 4
| Dónde | Qué corre | Secretos |
|---|---|---|
| **VPS** (Linux, IP fija, `systemd`) | Datos en vivo, Estrategia, Simulación por setup, Riesgo, Ejecución, Monitoreo/Telegram, receptor de webhooks, diario de producción | Clave MEXC con IP vinculada a la del VPS, en un fichero cifrado (`systemd-creds` o `age`), legible solo por el usuario del servicio. Nunca en git. |
| **Mac** | Claude Code y sus agentes, Laboratorio (backtests, walk-forward, Monte Carlo), panel, copia del diario | Sin clave de trading de MEXC: si acaso, una clave **solo lectura** para datos. |

- **Confirmaciones en L2:** la autoridad es **Telegram** (`/si <ticket>`), que llega directo al VPS. Desde Claude en el Mac, `/operar` llama a la **API de control del VPS** (HTTPS por el túnel, con token propio de solo-control) para crear el ticket; la confirmación final sigue siendo `/si` en Telegram.
- **Hooks de Claude:** siguen en el Mac y bloquean llamar a la API de control para cosas distintas de crear tickets, pausar o hacer KILL. La API de control **no permite** cambiar `risk.yaml`: eso se hace con commit + despliegue revisado.
- **Despliegue:** `git pull` + reinicio del servicio desde una etiqueta aprobada. El VPS nunca ejecuta código sin commit.

---

## 14. Estrategia de pruebas

| Tipo | Qué cubre |
|---|---|
| Unitarias (`pytest`) | Cada indicador, la fórmula de tamaño, la liquidación, Kelly, cada regla de PASS/BLOCK, cada transición de modo |
| Propiedades (`hypothesis`) | "El riesgo real nunca supera el permitido"; "nunca existe una posición sin stop"; "nunca se mira al futuro" |
| Golden | Indicadores frente a CSV exportados de TradingView (error < 0,1 %) |
| Replay | Sesiones grabadas de WebSocket reproducidas por el motor completo; resultado idéntico entre ejecuciones |
| Caos | Desconexión de WS, 429/5xx, ejecución parcial, stop rechazado, reinicio con posición abierta, reloj desviado |
| Integración (opt-in) | Contra MEXC real con tamaño mínimo; solo se ejecutan con `TS_LIVE_TESTS=1` y confirmación |
| Contrato de webhook | Mensajes válidos, inválidos, duplicados, antiguos, de IP no permitida |

Regla: **ningún test por defecto toca la red ni dinero**. Toda la suite corre offline con fixtures, como en la referencia.

---

## 15. Fases, tareas y criterios de aceptación

Cada fase termina con: tests en verde, demostración en vivo al dueño y su aprobación para pasar a la siguiente. Varias partes de una fase se construyen en paralelo con agentes (un agente por departamento independiente), con revisión de código antes de integrar.

| Fase | Tareas principales | Criterio de aceptación | Autonomía |
|---|---|---|---|
| **F0 Preparación** | Entorno (`uv`, Python 3.12, repo, pre-commit), Llavero, `tradesys doctor`; verificar todo lo marcado [VERIFICAR F0]; prueba real de crear y cancelar una orden mínima en spot y futuros; fijar `risk.yaml` con el dueño | `doctor` en verde; informe "qué permite tu cuenta MEXC" con comisiones, mínimos, modos y límites reales | — |
| **F1 Datos + Gráficos** | Dept. 1, 2 y 9: descarga histórica, WS en vivo, calidad, indicadores con golden tests, clasificador de régimen, Pine `TS-Regime`/`TS-Structure`, prototipo de panel | 12 meses de datos del universo; golden tests < 0,1 %; panel mostrando velas, régimen y estructura en vivo | L0 |
| **F2 Laboratorio** | Dept. 3, 4 y 5: contexto, 5 estrategias candidatas, backtest event-driven, walk-forward, robustez, DSR/PBO, Monte Carlo, estrés, informes | Fichas de las 5 candidatas con veredicto G1–G5 y evidencia; al menos 1 estrategia que pase G5 (si ninguna pasa, se itera G0 y **no se avanza**) | L0 |
| **F3 Riesgo + Papel 24/7** | Dept. 6, 7 (`PaperBroker`), 8 y 10; receptor de webhooks + Cloudflare Tunnel; Telegram; `launchd`; hooks de Claude | 2–4 semanas en papel 24/7 sin caídas sin explicar; KILL probado; estrategias evaluadas en G6 | L1 |
| **F4 Copiloto real** | `MexcBroker`, maker-first, stops en el exchange, watchdog, reconciliación; migración del motor a VPS con IP fija | Primeras ≥ 30 operaciones reales con tamaño mínimo y confirmación por ticket; cero posiciones sin stop; G7 evaluado | L2 |
| **F5 Automático + Ataque** | Habilitar L3 y modos Ataque/Turbo solo para estrategias en G8; informes semanales automáticos; degradación automática | 4 semanas en L3 sin violar ninguna regla dura; informe semanal vivo frente a simulado | L3 |
| **Continuo** | Nuevas hipótesis por G0; revisión semanal; recalibración trimestral del régimen | — | — |

---

## 16. Logística: checklist del dueño y costes

### 16.1 Antes de la Fase 0
- [ ] Mac (modelo: Apple Silicon M1–M4 o Intel), macOS actualizado, ≥ 50 GB libres para datos.
- [ ] Homebrew, Git y Claude Code instalados; este repo clonado.
- [ ] Repo privado propio creado en GitHub (pendiente: `mexc-trading-system`).
- [ ] Cuenta MEXC con KYC + **subcuenta** para el bot + 2FA.
- [ ] Clave API de la subcuenta: lectura + trading, **sin retiros** (se crea en la F0 junto con Claude; nunca se pega en el chat).
- [ ] Comprobar que MEXC y sus futuros están permitidos en tu país de residencia.
- [ ] TradingView con plan que incluya webhooks (Essential o superior) + 2FA.
- [ ] Bot de Telegram (BotFather) + tu chat ID.
- [ ] Cuenta gratuita de Cloudflare.
- [ ] Respuestas a §19.

### 16.2 Costes recurrentes (aproximados; confirmar precios actuales)
| Concepto | Necesario desde |
|---|---|
| TradingView con webhooks | F3 |
| VPS con IP fija (aprox. 5–15 USD/mes) | F4 |
| Claude (tu suscripción actual) | F0 |
| Datos opcionales de liquidaciones/noticias | F2, si se decide |
| Comisiones de trading | F4 (las controla el Dept. 5/7) |

---

## 17. Riesgos del proyecto y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Ninguna estrategia demuestra ventaja suficiente para el objetivo | El embudo lo detecta **antes** de perder dinero; se sigue en papel e investigando. El objetivo se reporta, no se fuerza. |
| La API de futuros de MEXC no permite órdenes | Se verifica en F0; se empieza en spot (sin cortos ni apalancamiento) y se reevalúa. |
| Sobreoptimización | Walk-forward, DSR, PBO, robustez, papel obligatorio y degradación automática. |
| Caída del Mac o de la red con posición abierta | Stop siempre en el exchange; VPS desde F4; watchdog y alertas. |
| Robo o fuga de claves | Sin retiros, subcuenta, Llavero, IP fija en VPS, gitleaks. |
| Error de programación que dispara órdenes | Separación de poderes, ticket firmado con caducidad, hooks, tests de propiedades, tamaño mínimo en G7. |
| Cambios de la API de MEXC (como el de ene-2026) | Capa de adaptador única, tests de contrato y suscripción a los anuncios de API de MEXC. |
| Comisiones y slippage se comen la ventaja | Maker-first, coste modelado en G1 y comparado con el real en G6/G7. |

---

## 18. Lo que queda a criterio del constructor
- Versiones exactas de librerías; elección final entre Streamlit y FastAPI + Lightweight Charts tras el prototipo de F1.
- Esquema físico de las tablas y particiones.
- Diseño visual del panel y de los mensajes de Telegram.
- Los parámetros concretos de cada estrategia (los decide el embudo, no se eligen a ojo).
- Fuente concreta del calendario macro.

---

## 18a. Mejoras del plan (v3, 2026-10-23)
Incorporadas tras construir y revisar la Fase 0:

1. **Presupuesto de riesgo vivo** (ya implementado): ninguna operación nueva puede arriesgar más que lo que queda antes del suelo o de los límites diario y semanal, descontando el riesgo ya abierto. Es la garantía central de §1b.
2. **Sombra permanente:** toda estrategia en vivo corre a la vez en papel con las mismas señales. Si vivo y sombra divergen más de 0,3R de media en 20 operaciones, se audita la ejecución (slippage, rechazos, latencia) antes de culpar a la estrategia.
3. **Simulacros de emergencia:** cada lunes, en papel, el sistema ejecuta un KILL, una caída de WebSocket y un reinicio con posición abierta, y registra cuánto tardó en quedar protegido. Si algo falla, el lunes no se opera en vivo.
4. **Sala de Mando visual:** panel único para el dueño con capital protegido frente al suelo, bolsa de ganancias, modo de cada bucket, puerta de riesgo y escenarios de cada posición abierta. El prototipo navegable ya existe como artefacto y en la F1 se convierte en el panel real con datos de MEXC.
5. **Revisión de escenarios:** el diario compara el escenario previsto con el ocurrido (matriz de confusión semanal). Los generadores que fallan pierden peso automáticamente.
6. **Calendario de riesgo:** las ventanas macro, las horas de funding y los desbloqueos de tokens se cargan una vez al día y se muestran en el panel 24 h antes, para que Escudo no llegue por sorpresa.

## 18b. Decisiones cerradas (2026-10-23)
El dueño delegó en Claude el diseño del sistema y de las estrategias ("como veas mejor"). Quedan fijadas:

| Tema | Decisión |
|---|---|
| Prioridad | No perder el capital (§1b) > consistencia > objetivo de rendimiento |
| Suelo | 450 USDT (−10 %) → HALT total |
| Ganancias semanales | 50 % a la bolsa de ganancias (modo agresivo), 50 % se queda en el capital protegido (interés compuesto); el dueño puede retirar cuando quiera |
| Mercado | Futuros perpetuos USDT-M (permiten cortos), margen aislado; spot como respaldo con la excepción de §10 |
| Apalancamiento | ≤ 3x en el capital protegido; ≤ 10x (Ataque) y ≤ 20x (Turbo) solo en la bolsa de ganancias |
| Autonomía | L2 (confirmación por ticket) desde la F4; L3 solo para estrategias en G8 |
| Universo | BTC y ETH + hasta 8 pares líquidos del top 20 (§6, Dept. 1) |
| Estrategias | Cartera S1–S7 + TV (§6, Dept. 4) |
| Gestión en posición | Motor de escenarios (§6, Dept. 5b) + asimetría (§9.4b) |

## 19. Preguntas abiertas para el dueño (logística; no bloquean el diseño)
Se responden en la Fase 0, en el Mac:
1. **Mac:** ¿modelo? ¿Puede estar encendido 24/7 hasta la Fase 4?
2. **TradingView:** ¿qué plan tienes? ¿Tienes indicadores o estrategias Pine propias que integrar?
3. **País de residencia y zona horaria:** acceso a MEXC y sus futuros, y horario de los informes.
4. **Disponibilidad en L2:** ¿en qué franjas horarias podrás confirmar tickets por Telegram? Fuera de ellas, el sistema solo opera en papel o no opera.

---

## 20. Glosario
- **R:** riesgo de una operación. Ganar "2R" = ganar el doble de lo arriesgado.
- **Edge / ventaja:** expectativa positiva demostrada tras costes.
- **Kelly:** fórmula del tamaño de apuesta óptimo según la ventaja. Usamos la mitad y sobre la estimación pesimista.
- **Maker / taker:** maker añade liquidez al libro (orden límite que espera); taker la quita (se ejecuta al instante). En MEXC futuros, maker ≈ 0 %.
- **Funding:** pago periódico entre largos y cortos en perpetuos.
- **OI (open interest):** contratos abiertos en total.
- **CVD / delta:** volumen comprador menos vendedor (por vela / acumulado).
- **BOS / CHoCH:** rotura de estructura / cambio de carácter (estructura de mercado).
- **Walk-forward:** optimizar en el pasado y probar en el periodo siguiente que no se vio.
- **DSR / PBO:** pruebas estadísticas que penalizan haber probado muchas variantes.
- **Margen aislado:** cada posición solo puede perder su propio margen.

---

## 21. Fuentes
- [Anuncios de API de MEXC (cambio de dominio de futuros, ene-2026)](https://www.mexc.com/bn-BD/announcements/api-updates)
- [MEXC: ajuste del límite de órdenes spot por API (mar-2025)](https://www.mexc.com/ru-RU/announcements/article/mexc-to-adjust-api-spot-order-rate-limit-effective-mar-25-2025-17827791522801)
- [MEXC: guía de comisiones 2026](https://www.mexc.com/ru-RU/crypto-pulse/article/mexc-trading-fees-complete-guide-39643)
- [Datawallet: comisiones MEXC (ES)](https://www.datawallet.com/es/cripto/mexc-fees)
- [MEXC help center: reglas de orden mínima](https://www.mexc.com/learn/article/17827791510411)
- [CCXT vs MEXC API](https://docs.ccxt.com/docs/comparisons/ccxt-vs-mexc-api)
- [ccxt: error 7002 en MEXC swap](https://lightrun.com/answers/ccxt-ccxt-mexc-swap-error-code-7002)
- [TradingView: cómo configurar alertas webhook](https://www.tradingview.com/support/solutions/43000529348-webhooks)
- [PickMyTrade: IPs de webhooks de TradingView](https://blog.pickmytrade.io/how-to-allowlist-tradingviews-4-webhook-ips/)
- [TechBullion: TradingView → MEXC futuros 2026](https://techbullion.com/how-to-automate-tradingview-strategies-to-mexc-futures-in-2026/)

---

*Aviso: este sistema es una herramienta, no un consejo financiero. No garantiza beneficios. El trading de cripto con apalancamiento puede hacer perder todo el capital asignado. El embudo y el motor de riesgo existen para reducir ese riesgo, no para eliminarlo.*
