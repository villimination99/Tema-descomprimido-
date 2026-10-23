# F0 — Cimientos y motor de riesgo: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** dejar en el Mac del dueño un paquete Python `tradesys` con un motor de riesgo completo y probado offline: tamaño de posición, Kelly, liquidación, buckets con suelo, modos y puerta PASS/BLOCK. Además, las herramientas para verificar la cuenta real de MEXC y las barreras de Claude Code.

**Architecture:** el paquete vive en `src/tradesys/`. El motor de riesgo (`tradesys.risk`) es lógica pura sin red, con funciones y dataclasses deterministas que reciben `now` como parámetro, así que se prueba entero offline. La red solo aparece en `tradesys.exchange.probe` y en `tradesys doctor`, siempre detrás de flags explícitos.

**Tech Stack:** Python 3.12, `uv`, `pydantic` v2, `pyyaml`, `typer`, `ccxt`, `keyring`, `pytest`, `hypothesis`, `ruff`, `pre-commit`, `gitleaks`.

**Spec:** `docs/superpowers/specs/2026-10-23-sistema-trading-mexc-design.md` (secciones §1b, §7, §9, §10, §12, §13). Hoja de ruta: `docs/superpowers/plans/2026-10-23-hoja-de-ruta.md`.

## Global Constraints
- Python ≥ 3.12; dependencias gestionadas con `uv` (`uv sync`, `uv run`).
- Todas las horas en UTC (`datetime` con `tzinfo=UTC`). Ninguna función del motor de riesgo llama a `datetime.now()`: `now` siempre llega como parámetro.
- Importes en USDT; porcentajes como fracción (`0.01` = 1 %).
- La suite por defecto (`uv run pytest`) no toca la red ni el Llavero real. Los tests de red se marcan `@pytest.mark.network` y se excluyen por defecto (`-m "not network"` en `pyproject.toml`).
- Valores del spec que no se pueden cambiar sin editar `config/risk.yaml`: suelo 450 USDT; capital protegido inicial 500 USDT; pérdida diaria 2 % / semanal 4 % (protegido); 30 % / 100 % (bolsa); 50 % de la ganancia semanal a la bolsa; Escudo 4 h; máximo 3 posiciones; ticket de 60 s; regla de liquidación 0,5; setup caducado 0,3.
- Mensajes al usuario (CLI) en español; identificadores de código en inglés.
- Ningún secreto en el repo: `.env`, `data/`, `logs/` y `reports/` en `.gitignore`; gitleaks en pre-commit.

## Review Focus
1. **Cantidad que redondea a 0 o por debajo del mínimo del par:** debe dar `BLOCK` con el motivo `MIN_SIZE`, nunca una excepción ni una orden de 0 (Tarea 4 y Tarea 9).
2. **Stop en el lado equivocado o igual a la entrada:** el `Setup` debe ser inválido al construirse (Tarea 2).
3. **Fronteras de tiempo:** una pérdida a las 23:59:59 UTC cuenta para ese día y a las 00:00:00 para el siguiente; la semana empieza el lunes 00:00 UTC (Tarea 7).
4. **Ticket justo en la caducidad:** `now == valid_until` ya está caducado (Tarea 9).
5. **Suelo alcanzado exactamente** (`equity == 450`): HALT, no "todavía no" (Tarea 7).

---

### Task 1: Esqueleto del proyecto y CLI

**Files:**
- Create: `pyproject.toml`, `src/tradesys/__init__.py`, `src/tradesys/cli.py`, `.gitignore`, `.pre-commit-config.yaml`, `README.md`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `tradesys.cli.app` (`typer.Typer`) con el entry point `tradesys`; `tradesys.__version__ = "0.1.0"`.

- [ ] **Step 1: Escribir el test que falla**
```python
from typer.testing import CliRunner
from tradesys.cli import app

def test_version():
    r = CliRunner().invoke(app, ["--version"])
    assert r.exit_code == 0
    assert "tradesys 0.1.0" in r.stdout
```
- [ ] **Step 2:** `uv run pytest tests/test_cli.py -v` → FAIL (módulo no existe).
- [ ] **Step 3:** Crear `pyproject.toml`:
  - `requires-python = ">=3.12"`, layout `src/`, script `tradesys = "tradesys.cli:app"`;
  - dependencias del Tech Stack; grupo `dev` con pytest, hypothesis, ruff y pre-commit;
  - `[tool.pytest.ini_options] addopts = "-m 'not network'"` y markers `network`.

  `.gitignore` con `.env`, `data/`, `logs/`, `reports/`, `.venv/`. `.pre-commit-config.yaml` con ruff (lint + format) y gitleaks. `cli.py` con la opción `--version` que imprime `tradesys 0.1.0`. El README explica en español `uv sync` y `uv run tradesys --version`.
- [ ] **Step 4:** `uv sync && uv run pytest -v` → PASS; `uv run pre-commit run --all-files` → OK.
- [ ] **Step 5:** Commit `feat: esqueleto del proyecto tradesys`.

---

### Task 2: Contratos de datos (§7)

**Files:**
- Create: `src/tradesys/core/models.py`
- Test: `tests/core/test_models.py`

**Interfaces:**
- Produces (pydantic v2, `model_config = ConfigDict(frozen=True)`):
  - `Side = Literal["long","short"]`; enums `Quality(A_PLUS="A+", A="A", B="B")`, `Mode(ESCUDO, NORMAL, ATAQUE, TURBO)`, `Bucket(PROTECTED="protected", BOLSA="bolsa")`, `Verdict(PASS, BLOCK)`, `Stage(G0…G6, G7_IN_PROGRESS, G7, G8)` (ordenable con `Stage.rank()`).
  - `Candle`, `Trade`, `Funding`, `OpenInterest`, con los campos del §7.
  - `Setup(setup_id, strategy_id, symbol, side, entry_type: Literal["limit","stop"], entry: float, stop: float, tp: list[float], invalidation: float, expires_at: datetime, quality: Quality, reason: str, source: Literal["internal","tradingview"])`.
  - `RiskDecision(setup_id, verdict, reasons: list[str], mode: Mode | None, bucket: Bucket | None, risk_usdt: float, qty: float, leverage: int, liq_price: float | None, ticket_hash: str | None, valid_until: datetime | None)`.
  - `Order`, `Fill`, `ScenarioReport`, `ManageAction`, con los campos del §7.

- [ ] **Step 1: Tests que fallan**
```python
def test_setup_long_stop_must_be_below_entry():
    with pytest.raises(ValidationError): make_setup(side="long", entry=100, stop=101)

def test_setup_short_stop_must_be_above_entry():
    with pytest.raises(ValidationError): make_setup(side="short", entry=100, stop=99)

def test_setup_stop_equal_entry_invalid():
    with pytest.raises(ValidationError): make_setup(side="long", entry=100, stop=100)

def test_setup_targets_on_profit_side():
    with pytest.raises(ValidationError): make_setup(side="long", entry=100, stop=99, tp=[98])

def test_roundtrip_json():
    s = make_setup(side="long", entry=100, stop=99, tp=[102])
    assert Setup.model_validate_json(s.model_dump_json()) == s

def test_stage_order():
    assert Stage.G7_IN_PROGRESS.rank() > Stage.G6.rank()
    assert Stage.G8.rank() > Stage.G7.rank()
```
(`make_setup` es un helper en `tests/core/conftest.py` con valores por defecto válidos y `expires_at` en UTC.)
- [ ] **Step 2:** `uv run pytest tests/core -v` → FAIL.
- [ ] **Step 3:** Implementar los modelos; validadores `model_validator(mode="after")` en `Setup` para el lado del stop y de los objetivos, y `expires_at` con zona horaria.
- [ ] **Step 4:** → PASS.
- [ ] **Step 5:** Commit `feat: contratos de datos`.

---

### Task 3: Configuración de riesgo

**Files:**
- Create: `config/risk.example.yaml`, `src/tradesys/config/risk.py`
- Test: `tests/config/test_risk_config.py`

**Interfaces:**
- Produces: `RiskConfig` (pydantic) y `load_risk_config(path: Path) -> RiskConfig`. Campos (nombres exactos):
```yaml
protected_initial_usdt: 500
floor_usdt: 450
week_starts: monday            # 00:00 UTC
weekly_profit_to_bolsa_pct: 0.5
shield_duration_hours: 4
max_positions: 3
corr_threshold: 0.7
ticket_ttl_seconds: 60
stale_setup_fraction: 0.3
liq_stop_ratio: 0.5
buckets:
  protected: {daily_loss_pct: 0.02, weekly_loss_pct: 0.04, loss_streak_to_shield: 2, allowed_modes: [ESCUDO, NORMAL]}
  bolsa:     {daily_loss_pct: 0.30, weekly_loss_pct: 1.00, loss_streak_to_shield: 3, allowed_modes: [ESCUDO, NORMAL, ATAQUE, TURBO]}
modes:
  ESCUDO: {risk_ceiling: 0.0025, max_leverage: 2,  min_quality: "A+", kelly_fraction: 0.5}
  NORMAL: {risk_ceiling: {protected: 0.01, bolsa: 0.02}, max_leverage: 3, min_quality: "A", kelly_fraction: 0.5}
  ATAQUE: {risk_ceiling: 0.10, max_leverage: 10, min_quality: "A+", kelly_fraction: 0.5}
  TURBO:  {risk_ceiling: 0.15, max_leverage: 20, min_quality: "A+", kelly_fraction: 0.75, max_session_hours: 4}
intraday_lock: {trigger_gain_pct: 0.02, risk_multiplier: 0.5, giveback_stop_pct: 0.5}
drawdown_to_shield_pct: 0.15
ataque_min_week_pnl_pct: -0.10
```
- `RiskConfig.risk_ceiling(mode: Mode, bucket: Bucket) -> float`.

- [ ] **Step 1: Tests que fallan:** cargar el ejemplo y comprobar `floor_usdt == 450`, `risk_ceiling(NORMAL, PROTECTED) == 0.01`, `risk_ceiling(NORMAL, BOLSA) == 0.02`, `risk_ceiling(TURBO, BOLSA) == 0.15`, `modes[TURBO].kelly_fraction == 0.75`. Comprobar que `floor_usdt >= protected_initial_usdt` lanza `ValidationError` y que un modo no permitido en un bucket da `ValueError` en `risk_ceiling(ATAQUE, PROTECTED)`.
- [ ] **Step 2:** → FAIL.
- [ ] **Step 3:** Implementar el modelo y el cargador; `config/risk.yaml` real = copia del ejemplo (añadir `config/risk.yaml` a git; el hook de la Tarea 12 lo protege).
- [ ] **Step 4:** → PASS.
- [ ] **Step 5:** Commit `feat: configuración de riesgo`.

---

### Task 4: Tamaño de posición y apalancamiento (§9.1)

**Files:**
- Create: `src/tradesys/risk/sizing.py`
- Test: `tests/risk/test_sizing.py`

**Interfaces:**
- Consumes: nada.
- Produces:
```python
@dataclass(frozen=True)
class PairRules: qty_step: float; min_qty: float; min_notional: float; mmr: float
@dataclass(frozen=True)
class SizeResult: qty: float; notional: float; leverage: int; margin: float; risk_usdt: float; loss_at_stop: float
class SizingBlocked(Exception): reason: str  # "MIN_SIZE" | "LEVERAGE"
def size_position(bucket_equity: float, risk_pct: float, entry: float, stop: float,
                  fee_in: float, fee_out: float, slippage_per_unit: float,
                  rules: PairRules, max_positions: int, max_leverage: int) -> SizeResult
```

- [ ] **Step 1: Tests que fallan**
```python
RULES = PairRules(qty_step=0.01, min_qty=0.01, min_notional=1.0, mmr=0.005)

def test_size_example_from_spec():
    r = size_position(500, 0.01, 100, 99, 0.0, 0.0002, 0.01, RULES, 3, 3)
    assert r.qty == pytest.approx(4.85)
    assert r.notional == pytest.approx(485.0)
    assert r.leverage == 3
    assert r.margin == pytest.approx(161.6667, rel=1e-4)
    assert r.loss_at_stop <= 5.0

def test_rounds_down_never_up():
    r = size_position(500, 0.01, 100, 99, 0, 0, 0, RULES, 3, 3)
    assert r.qty == pytest.approx(5.0)          # 5/1 exacto → 5.00

def test_min_size_blocks():
    with pytest.raises(SizingBlocked, match="MIN_SIZE"):
        size_position(10, 0.0025, 100, 50, 0, 0, 0, RULES, 3, 3)   # qty 0.0005 → 0

def test_leverage_over_mode_max_blocks():
    with pytest.raises(SizingBlocked, match="LEVERAGE"):
        size_position(500, 0.01, 100, 99.9, 0, 0, 0, RULES, 3, 3)  # nocional 5000 > 3×166

@given(...)  # hypothesis: equity 10–10000, risk 0.0025–0.15, entry/stop válidos
def test_loss_at_stop_never_exceeds_risk(...):
    assert r.loss_at_stop <= r.risk_usdt + 1e-9
```
- [ ] **Step 2:** → FAIL.
- [ ] **Step 3:** Implementar con las fórmulas exactas del spec §9.1:
  - `coste_por_ud = entry*fee_in + stop*fee_out + slippage_per_unit`;
  - redondeo hacia abajo al `qty_step` con tolerancia de 1e-9;
  - `margen_máx = equity / max_positions`; `leverage = ceil(notional / margen_máx)` (mínimo 1);
  - `loss_at_stop = qty*(|entry−stop| + coste_por_ud)`.
- [ ] **Step 4:** → PASS.
- [ ] **Step 5:** Commit `feat: tamaño de posición`.

---

### Task 5: Kelly prudente (§9.2)

**Files:**
- Create: `src/tradesys/risk/kelly.py`
- Test: `tests/risk/test_kelly.py`

**Interfaces:**
- Produces: `wilson_lower(wins: int, n: int, z: float = 1.96) -> float`; `kelly(p: float, b: float) -> float`; `kelly_cap(p_low: float, b_low: float, fraction: float) -> float` (devuelve `max(0, fraction*kelly)`); `risk_pct(p_low, b_low, fraction, ceiling) -> float` (`min(kelly_cap, ceiling)`).

- [ ] **Step 1: Tests que fallan**
```python
def test_wilson(): assert wilson_lower(45, 100) == pytest.approx(0.35614, abs=1e-4)
def test_wilson_zero_n(): assert wilson_lower(0, 0) == 0.0
def test_kelly_values():
    assert kelly(0.45, 1.5) == pytest.approx(0.08333, abs=1e-4)
    assert kelly(0.5, 2.0) == pytest.approx(0.25)
def test_negative_edge_gives_zero(): assert kelly_cap(0.4, 1.0, 0.5) == 0.0
def test_ceiling_applies(): assert risk_pct(0.5, 2.0, 0.5, 0.01) == 0.01
def test_turbo_three_quarters(): assert kelly_cap(0.5, 2.0, 0.75) == pytest.approx(0.1875)
```
- [ ] **Step 2:** → FAIL. **Step 3:** Implementar. **Step 4:** → PASS.
- [ ] **Step 5:** Commit `feat: kelly prudente`.

---

### Task 6: Liquidación (§9.3)

**Files:**
- Create: `src/tradesys/risk/liquidation.py`
- Test: `tests/risk/test_liquidation.py`

**Interfaces:**
- Produces: `liq_price(entry: float, leverage: int, mmr: float, side: Side) -> float`; `stop_is_safe(entry, stop, liq, ratio=0.5) -> bool`; `safe_leverage(entry, stop, mmr, side, start: int, ratio=0.5) -> int | None` (baja desde `start` hasta 1; `None` si ninguno cumple).

- [ ] **Step 1: Tests que fallan**
```python
def test_liq_long(): assert liq_price(100, 10, 0.005, "long") == pytest.approx(90.5)
def test_liq_short(): assert liq_price(100, 10, 0.005, "short") == pytest.approx(109.5)
def test_stop_safe(): assert stop_is_safe(100, 96, 90.5)          # 4 ≤ 4.75
def test_stop_unsafe(): assert not stop_is_safe(100, 95, 90.5)    # 5 > 4.75
def test_safe_leverage_lowers(): assert safe_leverage(100, 95, 0.005, "long", start=10) < 10
def test_none_when_impossible(): assert safe_leverage(100, 40, 0.005, "long", start=3) is None
```
- [ ] **Step 2–4:** FAIL → implementar → PASS.
- [ ] **Step 5:** Commit `feat: comprobación de liquidación`.

---

### Task 7: Libro de buckets, disyuntores, suelo y trinquete (§1b, §9.4)

**Files:**
- Create: `src/tradesys/risk/ledger.py`
- Test: `tests/risk/test_ledger.py`

**Interfaces:**
- Consumes: `RiskConfig` (Tarea 3), `Bucket` (Tarea 2).
- Produces:
```python
@dataclass
class BucketState: equity: float; peak: float; day_start: float; week_start: float
                   loss_streak: int; paused_until: datetime | None; ratchet_basis: float
@dataclass
class LedgerStatus: halted: bool; paused: dict[Bucket, bool]; reasons: list[str]
class Ledger:
    def __init__(self, cfg: RiskConfig, now: datetime) -> None   # protegido=500, bolsa=0
    def record_trade(self, bucket: Bucket, pnl: float, ts: datetime) -> None
    def roll(self, now: datetime) -> None        # cierre de día/semana: reinicios + 50 % de la ganancia semanal a la bolsa
    def status(self, now: datetime) -> LedgerStatus
    def drawdown_from_peak(self, bucket: Bucket) -> float
    def intraday_risk_multiplier(self, now: datetime) -> float   # 1.0, 0.5, o 0.0 (día parado)
    def to_json(self) -> str / from_json(...)    # persistencia
```

- [ ] **Step 1: Tests que fallan** (todas las horas en UTC):
  - `test_floor_exact_halts`: pérdidas que dejan el protegido en 450,00 → `status().halted is True` y la razón contiene `"FLOOR"`.
  - `test_daily_loss_protected_pauses_until_midnight`: −10 USDT (2 % de 500) a las 10:00 → `paused[PROTECTED]` hasta las 00:00 del día siguiente; a las 23:59:59 sigue en pausa; tras `roll` a las 00:00:00 ya no.
  - `test_loss_at_235959_counts_for_that_day`: −6 a las 23:59:59 y −5 a las 00:00:00 → ninguno de los dos días alcanza el 2 %, no hay pausa.
  - `test_weekly_loss_requires_human`: −20 (4 %) a lo largo de la semana → pausa con la razón `"WEEKLY_REVIEW"` que **no** se levanta con `roll`; solo con `ledger.human_resume(now)`.
  - `test_weekly_profit_split`: protegido termina la semana en 560 → tras `roll` del lunes 00:00: protegido 530, bolsa 30.
  - `test_losing_week_no_transfer`: semana en 490 → bolsa sigue en 0.
  - `test_bolsa_loss_never_touches_protected`: la bolsa pierde 30 de 30 → bolsa 0 (pausada), protegido sin cambios.
  - `test_ratchet`: bolsa con base 30 llega a 60 → 15 vuelven al protegido; base nueva 45.
  - `test_intraday_lock`: protegido +10 (2 %) → multiplicador 0,5; luego −5 (devuelve la mitad) → 0,0.
  - `test_persistence_roundtrip`.
- [ ] **Step 2:** → FAIL.
- [ ] **Step 3:** Implementar. La semana empieza el lunes 00:00 UTC. El suelo se compara con `<=`. La pausa semanal solo se levanta con `human_resume`.
- [ ] **Step 4:** → PASS.
- [ ] **Step 5:** Commit `feat: libro de buckets con suelo y disyuntores`.

---

### Task 8: Máquina de modos (§9.5)

**Files:**
- Create: `src/tradesys/risk/modes.py`
- Test: `tests/risk/test_modes.py`

**Interfaces:**
- Consumes: `RiskConfig`, `Mode`, `Bucket`, `Stage`.
- Produces:
```python
@dataclass(frozen=True)
class ModeSignals:
    loss_streak: int; drawdown_from_peak: float; daily_breaker: bool
    macro_window: bool; health_ok: bool; shield_trigger_last_24h: bool
    regime: str; best_strategy_stage: Stage; week_pnl_pct: float
    bucket_equity: float; turbo_grant_until: datetime | None
@dataclass(frozen=True)
class ModeState: mode: Mode; since: datetime; shield_until: datetime | None
def next_mode(bucket: Bucket, cur: ModeState, s: ModeSignals, cfg: RiskConfig, now: datetime) -> ModeState
```

- [ ] **Step 1: Tests que fallan:**
  - `test_two_losses_protected_to_shield_4h`: streak=2 en PROTECTED → ESCUDO, `shield_until = now + 4h`.
  - `test_bolsa_needs_three_losses`: streak=2 en BOLSA → no cambia; streak=3 → ESCUDO.
  - `test_macro_window_forces_shield`.
  - `test_health_degraded_forces_shield`.
  - `test_drawdown_15_forces_shield`.
  - `test_shield_exits_after_4h_without_triggers` → NORMAL.
  - `test_shield_does_not_exit_while_trigger_persists`.
  - `test_protected_never_ataque`: con todas las condiciones de Ataque en PROTECTED → NORMAL como máximo.
  - `test_ataque_requires_all`: BOLSA con equity>0, G8, régimen `"TENDENCIA_ALCISTA"`, sin disparadores en 24 h, week_pnl −0,05 → ATAQUE. Quitar cada condición por separado (parametrizado: equity 0, stage G7, régimen `"RANGO"`, `shield_trigger_last_24h=True`, week_pnl −0,11) → NORMAL.
  - `test_turbo_needs_grant_and_expires`: grant hasta now+2h → TURBO; con `now` ≥ grant → ATAQUE o menos.
  - `test_downgrade_immediate`: en ATAQUE llega `macro_window` → ESCUDO en la misma llamada.
- [ ] **Step 2–4:** FAIL → implementar (primero los disparadores de Escudo, luego los candidatos de mayor a menor modo, filtrados por `allowed_modes` del bucket) → PASS.
- [ ] **Step 5:** Commit `feat: máquina de modos de riesgo`.

---

### Task 9: Puerta PASS/BLOCK (§9.6)

**Files:**
- Create: `src/tradesys/risk/gate.py`
- Test: `tests/risk/test_gate.py`

**Interfaces:**
- Consumes: Tareas 2–8.
- Produces:
```python
@dataclass(frozen=True)
class OpenPosition: symbol: str; bucket: Bucket; risk_usdt: float; corr_with_new: float
@dataclass(frozen=True)
class GateContext:
    setup: Setup; exp_R: float; current_price: float; now: datetime
    ledger: LedgerStatus; equities: dict[Bucket, float]; modes: dict[Bucket, ModeState]
    strategy_stage: Stage; strategy_regimes: set[str]; regime: str
    open_positions: list[OpenPosition]; rules: PairRules
    fee_in: float; fee_out: float; slippage_per_unit: float
    kelly_p_low: float; kelly_b_low: float; intraday_multiplier: float
def choose_bucket(ctx: GateContext) -> Bucket
def evaluate(ctx: GateContext, cfg: RiskConfig) -> RiskDecision
def ticket_hash(d: RiskDecision, setup: Setup) -> str   # sha256 de JSON canónico (sort_keys)
def is_ticket_valid(d: RiskDecision, now: datetime) -> bool   # now < valid_until
```
- Códigos de motivo exactos, en el orden del spec: `HALTED`, `STAGE`, `QUALITY`, `REGIME`, `BREAKER`, `EXPOSURE`, `MIN_SIZE`, `LIQUIDATION`, `NEG_EXPECTANCY`, `STALE`. Devuelve el **primer** motivo que falla.

- [ ] **Step 1: Tests que fallan:**
  - Un test por motivo, partiendo de un `GateContext` válido (fixture `ok_ctx`) y rompiendo una sola cosa:
    - `HALTED` (`ledger.halted`);
    - `STAGE` (stage G6);
    - `QUALITY` (B en NORMAL; A en ESCUDO);
    - `REGIME`;
    - `BREAKER` (bucket pausado);
    - `EXPOSURE` (3 abiertas; o 1 abierta con corr 0,8 cuyo riesgo + el nuevo supera el techo del modo);
    - `MIN_SIZE`;
    - `LIQUIDATION` (el apalancamiento que exige `margen_máx` no cumple la regla 0,5: `safe_leverage(...) < size.leverage`; p. ej. stop al 40 % de la entrada);
    - `NEG_EXPECTANCY` (exp_R = 0);
    - `STALE` (precio a 0,31 × |entrada−stop| de la entrada).
  - `test_pass_has_ticket`: PASS → `ticket_hash` de 64 hex, `valid_until == now + 60s`.
  - `test_ticket_expired_at_boundary`: `is_ticket_valid(d, d.valid_until) is False`.
  - `test_g7_in_progress_min_size_normal_only`: stage `G7_IN_PROGRESS` → qty = `rules.min_qty` y modo NORMAL aunque Kelly permita más; en ATAQUE → `STAGE`.
  - `test_choose_bucket_bolsa_only_when_attack`: A+, G8, bolsa en ATAQUE con equity>0 → BOLSA; cualquier otra combinación → PROTECTED.
  - `test_order_of_rules`: con HALTED y QUALITY rotos a la vez → motivo `HALTED`.
  - `test_risk_uses_kelly_and_intraday`: `risk_usdt == equity × min(kelly_cap, ceiling) × intraday_multiplier`.
- [ ] **Step 2–4:** FAIL → implementar → PASS.
- [ ] **Step 5:** Commit `feat: puerta de riesgo PASS/BLOCK`.

---

### Task 10: Secretos y `tradesys doctor`

**Files:**
- Create: `src/tradesys/infra/secrets.py`, `src/tradesys/infra/doctor.py`; modificar `src/tradesys/cli.py`
- Test: `tests/infra/test_secrets.py`, `tests/infra/test_doctor.py`

**Interfaces:**
- Produces:
  - `SERVICE = "tradesys"`; nombres permitidos `{"mexc_api_key","mexc_api_secret","mexc_readonly_key","mexc_readonly_secret","telegram_token","telegram_chat_id"}`; `get_secret(name) -> str | None`; `set_secret(name, value) -> None` (`ValueError` si el nombre no está permitido).
  - `CheckResult(name: str, ok: bool, detail: str)`; `run_checks(offline: bool, clock: Callable[[], float] | None = None) -> list[CheckResult]`.
  - CLI: `tradesys secrets set <name>` (entrada oculta con `typer.prompt(hide_input=True)`; nunca imprime el valor), `tradesys doctor [--offline]` (tabla en español; código de salida 1 si algo falla).
- **Comprobaciones:**
  - Python ≥ 3.12;
  - `config/risk.yaml` carga;
  - secretos de MEXC presentes (solo "sí/no");
  - con red: `GET https://api.mexc.com/api/v3/time` → desviación de reloj < 500 ms, `@pytest.mark.network` en su test real.

- [ ] **Step 1: Tests que fallan:** backend de keyring en memoria (fixture que hace `keyring.set_keyring(MemoryKeyring())`):
  - `test_set_get`;
  - `test_unknown_name_rejected`;
  - `test_cli_never_echoes_secret` (el valor no aparece en la salida);
  - `test_doctor_offline_reports_missing_keys` (falla con detalle `"falta mexc_api_key"`);
  - `test_clock_skew_check` con `clock` simulado a +600 ms → `ok False`.
- [ ] **Step 2–4:** FAIL → implementar → PASS.
- [ ] **Step 5:** Commit `feat: secretos en el Llavero y doctor`.

---

### Task 11: Sonda de capacidades de MEXC

**Files:**
- Create: `src/tradesys/exchange/probe.py`; modificar `src/tradesys/cli.py`
- Test: `tests/exchange/test_probe.py`, `tests/fixtures/mexc/` (respuestas grabadas)

**Interfaces:**
- Consumes: `get_secret` (Tarea 10).
- Produces:
  - `make_exchange(market: Literal["spot","swap"], auth: bool) -> ccxt.mexc` (`options.defaultType` = market).
  - `probe_public(ex) -> dict`: número de mercados; para `BTC/USDT` y `BTC/USDT:USDT`: precisión, `limits` y `mmr`, si existe.
  - `probe_private(ex) -> dict`: balances (solo totales), comisiones (`fetch_trading_fees`, o `"unknown"`), modo de posición y tipo de margen (o `"unknown"`).
  - `probe_order(ex, symbol: str, confirm: str) -> dict`: exige `confirm == "SI"` (si no, `PermissionError`). Coloca una orden límite **post-only** de compra al 50 % del precio actual con el tamaño mínimo, la cancela al momento y devuelve `{"created": bool, "cancelled": bool, "error": str | None}`.
  - Para futuros, comprobar además que acepta una orden stop reduce-only (crear y cancelar).
  - Para spot, registrar si acepta stop/OCO (`stop_supported: bool`).
  - CLI: `tradesys mexc probe [--private] [--order spot|swap]`. Escribe `reports/mexc_capabilities.json` y muestra un resumen en español. `--order` pide escribir `SI` por teclado.

- [ ] **Step 1: Tests que fallan** con un `FakeExchange` que devuelve las fixtures:
  - `test_probe_public_extracts_limits`;
  - `test_probe_order_requires_SI` (`confirm="si"` → `PermissionError`, distingue mayúsculas);
  - `test_probe_order_cancels_even_if_check_fails` (el fake lanza al consultar → igualmente llama a `cancel_order`);
  - `test_report_written_without_secrets` (el JSON no contiene las claves del fake).
- [ ] **Step 2–4:** FAIL → implementar → PASS.
- [ ] **Step 5:** Commit `feat: sonda de capacidades de MEXC`.
- [ ] **Step 6 (manual, en el Mac, con el dueño):**
  1. Crear la subcuenta y la clave API (sin retiros); `tradesys secrets set mexc_api_key` y `… mexc_api_secret`.
  2. `tradesys doctor` en verde.
  3. `tradesys mexc probe --private --order spot` y `--order swap`.
  4. Anotar los resultados en el spec (§3 y §10: comisiones, mínimos, stops en spot, modo de posición, caducidad de clave sin IP) y quitar las marcas [VERIFICAR F0] resueltas.
  5. Commit `docs: resultados de verificación F0`.

---

### Task 12: Barreras de Claude Code (§12)

**Files:**
- Create: `scripts/hooks/guard.py`, `.claude/settings.json`
- Test: `tests/hooks/test_guard.py`

**Interfaces:**
- Produces: `guard.decide(event: dict) -> dict | None`. Recibe el JSON de `PreToolUse` (`{"tool_name": ..., "tool_input": {...}}`) y devuelve `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny"|"ask", "permissionDecisionReason": "<español>"}}` o `None` para permitir. `main()` lee stdin y escribe stdout.
- **Reglas:**
  - `Bash` con un comando que coincida con `r"\btradesys\s+exec\s+live\b"` o `r"\btradesys\s+mexc\s+probe\b.*--order"` → `deny` ("la ejecución real solo por /operar con ticket vigente" / "la orden de prueba la lanza el dueño en su terminal").
  - `Edit`/`Write`/`MultiEdit` sobre una ruta que termine en `config/risk.yaml` o `config/gates.yaml` → `ask`.
  - `Bash` que lea secretos (`security find-generic-password`, `keyring get`) → `deny`.
- `.claude/settings.json` registra el hook `PreToolUse` con el matcher `Bash|Edit|Write|MultiEdit` y el comando `uv run python scripts/hooks/guard.py`.

- [ ] **Step 1: Tests que fallan:**
  - un caso por regla;
  - `test_allows_normal_commands` (`uv run pytest` → None);
  - `test_regex_not_fooled_by_spacing` (`tradesys  exec   live`);
  - `test_other_file_edit_allowed` (`config/risk.example.yaml` → None).
- [ ] **Step 2–4:** FAIL → implementar → PASS.
- [ ] **Step 5:** Verificación manual en Claude Code: pedir "ejecuta `tradesys exec live`" → bloqueado con el mensaje en español.
- [ ] **Step 6:** Commit `feat: barreras de Claude Code`.

---

## Cierre de la F0
- [ ] `uv run pytest` → todo PASS; `uv run ruff check .` → limpio.
- [ ] `tradesys doctor` → todo en verde en el Mac del dueño.
- [ ] `reports/mexc_capabilities.json` revisado con el dueño; spec actualizado.
- [ ] Demostración: con datos inventados, recorrer un setup por `evaluate` y ver PASS/BLOCK con sus motivos; simular el suelo y la pausa semanal.
- [ ] Aprobación del dueño → escribir `f1-datos-graficos.md`.
