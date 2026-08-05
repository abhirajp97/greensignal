# GreenSignal — File Map

Every file in the repo, what it does, and its current status. Update this whenever a file is added, removed, renamed, or its purpose meaningfully changes.

---

## Root

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project definition — Python version, all dependencies, Ruff + pytest config. `uv sync` reads this. |
| `.env.example` | Template for secrets — copy to `.env` and fill in Nasdaq API key, Supabase URL/key, GEE project ID. |
| `.gitignore` | Keeps `.env`, `.venv`, `__pycache__`, notebook checkpoints out of git. |
| `Makefile` | `lint`, `test`, `check-imports` (enforces `core/` never imports `domains/`), `verify` (all three). |
| `CLAUDE.md` | Instructions for Claude Code — architecture rules, commands, signal formulas, build sequence. |
| `.mcp.json` | MCP server config — GitHub (`@modelcontextprotocol/server-github`) and Supabase (`@supabase/mcp-server-supabase`). Auth via env vars `GITHUB_TOKEN` and `SUPABASE_ACCESS_TOKEN`. |

---

## `.claude/` — Claude Code automation (not shipped to production)

| File | Purpose |
|------|---------|
| `.claude/settings.json` | Project-level hooks: PostToolUse Ruff auto-format on Edit/Write; PreToolUse `.env` write block. |
| `.claude/skills/implement-source/SKILL.md` | Skill: step-by-step contract for implementing any `domains/coffee/sources/` stub — return type, SourceRun, error handling, test requirements. |
| `.claude/skills/backtest-notebook/SKILL.md` | Skill: template and steps for the 6 validation notebooks — fetch → QC → feature → correlation → gate → summary. |
| `.claude/agents/data-source-reviewer.md` | Subagent: reviews a completed source implementation before merge — contract, error handling, tests, docs. Returns APPROVED or NEEDS WORK. |

---

## `docs/`

| File | Purpose |
|------|---------|
| `FILE_MAP.md` | This file. Full map of every file and its role. |
| `GreenSignal_Phase0_Report.md` | Phase 0 validation results — signal correlations, ROI analysis, composite formula derivation. |
| `GreenSignal_Math_Reference.md` | Every formula and statistical concept used in the product, with Python implementations. |
| `GreenSignal_ICP.md` | Ideal customer profile — who the roaster is, how they make purchasing decisions, how to reach them. |
| `coffee_intelligence_mvp.md` | MVP feature set, ROI case, technical architecture overview, build sequence. |
| `greensignal_procurement_intelligence_architecture.md` | Full system architecture — repo structure, canonical objects, data flows, domain expansion design. |
| `phase0_next_steps.md` | Per-signal data source documentation and agreed next steps coming out of Phase 0 review. |
| `notebook_01_guide.md` | Reader's guide for notebook 01 (ICE KC price position signal) — section-by-section explanation, math, and key numbers, including the re-executed walk-forward result (78w window, +7.34% avg, 10/12 positive years). |
| `notebook_02_guide.md` | Reader's guide for notebook 02 (NOAA ENSO ONI signal) — section-by-section explanation, the corrected El Niño thesis, and the walk-forward purchase simulation (isolated ENSO does not beat naive buying despite passing its correlation gate). |
| `notebook_03_guide.md` | Reader's guide for notebook 03 (CFTC COT signal) — section-by-section explanation, momentum vs contrarian thesis, the existing multi-variant walk-forward plus the new canonical single-weight walk-forward, and why COT works as a composite modifier not a standalone signal. |
| `notebook_04_guide.md` | Reader's guide for notebook 04 (USDA stocks-to-use signal) — section-by-section explanation of the price-level vs YoY-change gate mismatch; no walk-forward section yet (correlation/gate-validation notebook only). |
| `notebook_05_guide.md` | Reader's guide for notebook 05 (CHIRPS Minas Gerais drought signal) — section-by-section explanation and the walk-forward purchase simulation that replaced the old (incorrectly lag-0) rolling-stability section. |

---

## `core/` — Shared layer. Never imports from `domains/`.

### `core/models/` — Canonical Pydantic schemas

All models use `pydantic.BaseModel`. These are the objects that flow between every layer — sources produce observations, features compute from them, services produce recommendations and forecasts.

| File | What it defines | Status |
|------|----------------|--------|
| `asset.py` | `Asset` — anything that can be bought (`asset_id`, `domain`, `asset_type`, `name`, `unit`, `metadata`) | ✅ Done |
| `observation.py` | `MarketObservation` (raw price point) and `FeatureObservation` (derived signal value) | ✅ Done |
| `recommendation.py` | `Recommendation` — the output a roaster sees: `action` (Buy/Neutral/Caution), `multiplier`, `headline`, `rationale` | ✅ Done |
| `risk_signal.py` | `RiskSignal` — a named risk flag with `level`, `score` (0–1), and plain-language `rationale` | ✅ Done |
| `forecast.py` | `Forecast` — price prediction with confidence band, model name, features used | ✅ Done |
| `scenario.py` | `ScenarioInput` / `ScenarioOutput` — margin calculator I/O (v2 feature, stub only) | 🔲 Stub |
| `source_run.py` | `SourceRun` — ingestion job log: when it ran, records fetched/stored, errors | ✅ Done |

### `core/services/` — Shared logic no domain owns

| File | What it does | Status |
|------|-------------|--------|
| `recommendation_engine.py` | The composite formula: `multiplier = (1.5 - price_position) × (1.0 + 0.65 × climate_risk_score)` | 🔲 Stub |
| `scenario_engine.py` | Computes `ScenarioOutput` from `ScenarioInput` for margin modelling | 🔲 Stub |
| `forecasting.py` | Wraps NeuralProphet or ARIMA-X — takes price + feature DataFrames, returns `Forecast` | 🔲 Stub |
| `data_quality.py` | Gap detection and range checks — called by ingestion jobs before storing | 🔲 Stub |
| `freshness.py` | Checks whether a source's last update is stale — used to flag signals in the API | 🔲 Stub |

### `core/storage/`

| File | What it does | Status |
|------|-------------|--------|
| `db.py` | Creates the Supabase client from env vars via `get_client()` | 🔲 Stub |
| `repositories.py` | `upsert(table, rows)`, `fetch_range(table, start, end)`, `latest(table, asset_id)` | 🔲 Stub |

### `core/utils/`

| File | What it does | Status |
|------|-------------|--------|
| `dates.py` | `month_end()`, `shift_months()`, `flowering_season()` (True for Sep/Oct/Nov) | 🔲 Stub |
| `logging.py` | `get_logger(name)` — returns a stdout logger with timestamps | ✅ Done |

---

## `domains/coffee/` — Coffee-specific layer. Imports from `core/`, never the reverse.

### `domains/coffee/registry/`

| File | What it does | Status |
|------|-------------|--------|
| `assets.py` | Declares tracked assets as constants: origins (`BRAZIL_ARABICA`, `COLOMBIA_ARABICA`, `ETHIOPIA_ARABICA`, `VIETNAM_ROBUSTA`), benchmarks (`ICE_ARABICA_BENCHMARK`, `WB_ARABICA_BENCHMARK`, `WB_ROBUSTA_BENCHMARK`), and signals (`ENSO_ONI`, `COT_KC`, `USDA_STU`, `CHIRPS_MINAS`); collected in `ALL_ASSETS` | ✅ Done |
| `regions.py` | Geographic bounding boxes for CHIRPS extraction: `MINAS_GERAIS`, `VIETNAM_CENTRAL_HIGHLANDS` | ✅ Done |

### `domains/coffee/sources/` — One file per data source. Each returns `list[MarketObservation]` or `list[FeatureObservation]`.

| File | Source | Implement order | Status |
|------|--------|----------------|--------|
| `ice_coffee_c.py` | Nasdaq Data Link `CHRIS/ICE_KC1` daily close | **1st** — needs API key only | ✅ Done |
| `world_bank_commodity.py` | World Bank Pink Sheet — Arabica + Robusta physical prices (free, no auth) | **new** | ✅ Done |
| `noaa_enso.py` | NOAA CPC ONI fixed-width text (`oni.ascii.txt`) | **2nd** — free, no auth | ✅ Done |
| `cot.py` | CFTC disaggregated COT report, annual ZIP/CSVs | **3rd** — free, no auth | ✅ Done |
| `usda_psd.py` | USDA PSD bulk CSV — world stocks-to-use % (free, no auth) | **4th** — free, no auth | ✅ Done |
| `chirps.py` | CHIRPS via Google Earth Engine (Minas Gerais GAUL polygon); NetCDF fallback | **5th** | ✅ Done |

### `domains/coffee/features/` — Signal computation from raw DataFrames

| File | What it computes | Status |
|------|-----------------|--------|
| `price_features.py` | `price_position_52w` (0–1), `yoy_price_change`, `price_momentum_12m` (context only — not a buy signal) | ✅ Done |
| `supply_features.py` | `stu_risk_score` (STU % → 0–1 risk), `supply_regime` label | 🔲 Stub |
| `climate_features.py` | `enso_lagged` (~14m shift, El Niño lead), `climate_risk_score` (weighted sub-signal combination) | 🔲 Stub |
| `margin_features.py` | `roaster_margin`, `forward_buy_saving` — dollar-impact numbers for roasters | 🔲 Stub |

### `domains/coffee/models/` — Signal assembly

| File | What it does | Status |
|------|-------------|--------|
| `signal_generator.py` | Takes all five signal inputs → calls `recommendation_engine.build_recommendation` → returns `Recommendation` | 🔲 Stub |
| `risk_scorer.py` | Builds `RiskSignal` objects from supply and climate inputs | 🔲 Stub |

---

## `apps/`

### `apps/api/`

| File | What it does | Status |
|------|-------------|--------|
| `main.py` | Creates FastAPI app, mounts `/health` and `/coffee` routers | ✅ Done |
| `routes/health.py` | `GET /health → {"status": "ok"}` | ✅ Working |
| `routes/coffee.py` | `GET /coffee/origins`, `/origins/{id}/signal`, `/price`, `/risk`, `/forecast` | 🔲 Stub |

### `apps/web/`

Empty — React + Vite scaffold deferred until data pipeline and signal are validated.

---

## `jobs/coffee/` — Scheduled ingestion functions. No scheduler wired yet.

| File | When it runs (eventually) | Status |
|------|--------------------------|--------|
| `daily_prices.py` | Every trading day — fetches ICE KC close, stores as `MarketObservation` | 🔲 Stub |
| `monthly_supply.py` | After each WASDE release — reads USDA PSD CSV, stores STU as `FeatureObservation` | 🔲 Stub |
| `monthly_climate.py` | Monthly — fetches ENSO ONI and COT positions, stores as `FeatureObservation` | 🔲 Stub |

---

## `notebooks/`

| Path | Purpose | Status |
|------|---------|--------|
| `coffee_backtests/README.md` | Pass/fail gates for each signal on real data. All notebooks must pass these before product work begins. | ✅ Done |
| `coffee_backtests/01_ice_price_signal.ipynb` | L1: fetch real ICE KC data, validate price_position_52w correlation; walk-forward re-executed (§4c) — 78w window wins, +7.34% avg saving, 10/12 positive years (2013–2024) | ✅ Done (r=+0.852, saving=+10.73%, all gates PASS) |
| `coffee_backtests/07_wb_physical_prices.ipynb` | WB Arabica & Robusta L1 gates + basis analysis vs KC=F | ✅ Done (Arabica r=+0.835, Robusta r=+0.748, all gates PASS) |
| `coffee_backtests/02_enso_signal.ipynb` | L2b: NOAA ONI backtest, corrected El Niño thesis; gate PASSES — r=+0.288 @15m lead (KC), +0.327 @15m (WB 2000–24, p=1.4e-8); event study El Niño→+36.5% fwd-12m vs La Niña −1.7%. Original sign+lag were backwards. Old gate-validation/event-study/risk-distribution sections replaced with a walk-forward purchase simulation (isolated ENSO): −0.07% avg saving, 8/15 positive years — correlation gate passing does not imply a standalone economic edge | ✅ Done |
| `coffee_backtests/03_cot_signal.ipynb` | L5: CFTC COT backtest; gate PASSES on the corrected momentum framing (r=+0.144 @ fwd 6m); original contrarian thesis inverted — managed money trend-follows. Existing multi-variant walk-forward (§5) plus new canonical single-weight walk-forward (§7, replacing the old rolling-stability section): −2.26% avg saving, 1/12 positive years — momentum signal loses money against naive buying in this framework | ✅ Done |
| `coffee_backtests/04_usda_supply_signal.ipynb` | L2a: USDA world stocks-to-use backtest; YoY-change gate FAILS (r=−0.04) but signal strong on price level (r=−0.40 monthly, −0.56 annual, −0.59 @ 23m lag); recommend redefining L2a gate to price level (cf. L1). No walk-forward section yet | ✅ Done |
| `coffee_backtests/05_chirps_signal.ipynb` | L3: CHIRPS Minas Gerais drought backtest; gate narrowly FAILS (r=+0.10 @ 14m) but right sign/lag/mechanism, annual flowering r=+0.40; keep as low-weight flowering amplifier. Old (incorrectly lag-0) rolling-stability section replaced with a walk-forward purchase simulation (isolated drought risk): +1.01% avg saving, 8/15 positive years | ✅ Done |
| `coffee_backtests/06_composite_backtest.ipynb` | Full composite: all signals combined, measure forward prescience | 🔲 Not created |
| `coffee_data_validation/` | Exploratory data quality checks as each new source is pulled | 🔲 Empty |

---

## `tests/`

Empty test directories — tests are written alongside each implementation.

| Path | What it will test |
|------|------------------|
| `tests/core/` | Canonical models, services, storage helpers |
| `tests/domains/coffee/` | Source parsers, feature engineering, signal generator |

---

*Last updated: 2026-08-04 — walk-forward purchase simulations added to notebooks 01 (re-executed), 02, 03, and 05; reader's guides added/updated for all five backtest notebooks (`docs/notebook_0{1..5}_guide.md`)*
