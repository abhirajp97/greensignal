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
| `notebook_01_guide.md` | Reader's guide for notebook 01 (ICE KC price position signal) — section-by-section explanation, math, and key numbers. |
| `notebook_03_guide.md` | Reader's guide for notebook 03 (CFTC COT signal) — section-by-section explanation, momentum vs contrarian thesis, and why COT works as a composite modifier not a standalone signal. |
| `india_origin_signal_plan_v2_full_build.md` | India origin signal (Arabica + Robusta, Karnataka) build plan (v2.4). §12 (real price/supply source found on `coffeeboard.gov.in`) + §13 (multi-district weighting, Arabica 24m robustness, district-alias bug fix, TLS-cert/data-loss incident) + §14 (global pass-through + FX decomposition — R²=0.887-0.962, confirms India price is dominated by global benchmark + FX, not local climate) are authoritative. |

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
| `recommendation_engine.py` | `build_recommendation()` — applies the composite formula (`multiplier = (1.5 - price_position) × (1.0 + 0.65 × climate_risk_score)`), returns a `Recommendation` with action/headline/rationale. Origin-agnostic — used by both `generate_signal()` (Brazil) and `generate_india_signal()`. Also exports `classify_normalized(current_multiplier, trailing_multipliers)` — the notebook-06-validated rolling-24m normalization (ratio to trailing 24-month mean, same thresholds), kept as a separate explicit function since `build_recommendation()` is pure/stateless and has no way to hold trailing history | ✅ Done |
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
| `assets.py` | Declares tracked assets as constants: origins (`BRAZIL_ARABICA`, `COLOMBIA_ARABICA`, `ETHIOPIA_ARABICA`, `VIETNAM_ROBUSTA`, `INDIA_ARABICA`, `INDIA_ROBUSTA`), benchmarks (`ICE_ARABICA_BENCHMARK`, `WB_ARABICA_BENCHMARK`, `WB_ROBUSTA_BENCHMARK`), and signals (`ENSO_ONI`, `COT_KC`, `USDA_STU`, `USDA_STU_VINTAGE`, `CHIRPS_MINAS`, `CHIRPS_KODAGU`, `FX_USD_INR`, `INDIA_PRODUCTION`); collected in `ALL_ASSETS` | ✅ Done |
| `regions.py` | Geographic bounding boxes for CHIRPS extraction: `MINAS_GERAIS`, `VIETNAM_CENTRAL_HIGHLANDS`, `KODAGU` | ✅ Done |

### `domains/coffee/sources/` — One file per data source. Each returns `list[MarketObservation]` or `list[FeatureObservation]`.

| File | Source | Implement order | Status |
|------|--------|----------------|--------|
| `ice_coffee_c.py` | Nasdaq Data Link `CHRIS/ICE_KC1` daily close | **1st** — needs API key only | ✅ Done |
| `world_bank_commodity.py` | World Bank Pink Sheet — Arabica + Robusta physical prices (free, no auth) | **new** | ✅ Done |
| `noaa_enso.py` | NOAA CPC ONI fixed-width text (`oni.ascii.txt`) | **2nd** — free, no auth | ✅ Done |
| `cot.py` | CFTC disaggregated COT report, annual ZIP/CSVs | **3rd** — free, no auth | ✅ Done — `cot_contrarian_signal()` still encodes the disproven contrarian sign, pending update to the validated momentum framing (notebook 03) |
| `usda_psd.py` | USDA PSD bulk CSV — world stocks-to-use % (free, no auth); always latest-revised vintage, look-ahead risk for backtests — see `usda_coffee_wmt.py` | **4th** — free, no auth | ✅ Done |
| `chirps.py` | CHIRPS via Google Earth Engine (Minas Gerais GAUL polygon); NetCDF fallback | **5th** | ✅ Done |
| `usda_coffee_wmt.py` | USDA "Coffee: World Markets and Trade" semiannual PDF circular (`esmis.nal.usda.gov`, free, no auth) — true vintage-dated world stocks-to-use %, fixes `usda_psd.py`'s look-ahead bias. Not WASDE (WASDE doesn't cover coffee). Deps: `pdfplumber`, `beautifulsoup4` | **6th** — free, no auth | ✅ Done |
| `chirps_india.py` | CHIRPS via GEE, now multi-district (`district` param: Kodagu/Chikmagalur/Hassan, Karnataka's 3 largest coffee districts — GAUL level-2 `ADM2_NAME`, not level-1 like Brazil); species-specific blossom windows (`is_flowering_month(month, species)` — Robusta Feb-Mar, Arabica Apr-May, corrected against real agronomy sources); `drought_risk_score`; NetCDF fallback. New module (not a `chirps.py` parameterization) — built for the India origin signal | ✅ Done |
| `coffee_board_india_price.py` | Coffee Board of India's Daily Market Report archive (`coffeeboard.gov.in`, free, no auth, stateful ASP.NET postback flow) — genuine India-origin "Raw Coffee Price (Karnataka)" (Arabica/Robusta, Parchment/Cherry, ₹/50kg), archive back to 2012. Supersedes the WB-benchmark proxy fallback the first India sprint pass settled for | ✅ Done |
| `coffee_board_india_supply.py` | Coffee Board's semiannual "Database on Coffee" PDF circular (free, no auth) — district + national production estimates (MT), vintage-dated per report like `usda_coffee_wmt.py`. India-specific supply signal, back to 2009. `_region_slug()` now applies a `_REGION_ALIASES` map to collapse district-name spelling drift across editions (e.g. "Chikkamagaluru"/"Chikmagalur"). **Data note:** the cached `data/coffee_board_india_supply.csv` is currently a reduced 168-row/4-edition snapshot, not the full 1,289-row/62-report backfill — lost to a caching-script mistake during a `coffeeboard.gov.in` TLS-cert outage; full re-backfill pending the site's cert renewal (see plan doc §13.4) | ✅ Done (cached data reduced, pending re-backfill) |

### `domains/coffee/features/` — Signal computation from raw DataFrames

| File | What it computes | Status |
|------|-----------------|--------|
| `price_features.py` | `price_position_52w` (0–1), `yoy_price_change`, `price_momentum_12m` (context only — not a buy signal) | ✅ Done |
| `supply_features.py` | `stu_risk_score` (STU % → 0–1 risk), `supply_regime` label. Notebook 04 validated a z-score-based stress score (`stu_z_score`, `stu_stress`) as the successor to the linear clamp — not yet promoted here, pending composite wiring (06) | 🔲 Stub |
| `climate_features.py` | `climate_risk_score` (weighted sub-signal combination) is ✅ implemented, weights now the real-data r-proportional split from notebook 06 §12 (`WEIGHTS` constant, L3 dominant at 0.625) — supersedes the Phase 0 fixed split. `enso_lagged` (~14m shift) is still 🔲 stub — the real, currently-used lag+score logic lives in `noaa_enso.enso_risk_score()` instead | 🔲 Mixed |
| `margin_features.py` | `roaster_margin`, `forward_buy_saving` — dollar-impact numbers for roasters | 🔲 Stub |

### `domains/coffee/models/` — Signal assembly

| File | What it does | Status |
|------|-------------|--------|
| `signal_generator.py` | `generate_signal()` — Brazil, takes all five signal inputs → calls `recommendation_engine.build_recommendation`. `generate_india_signal()` — additive, India's 2-input (price_position + Kodagu climate risk) composite, same formula shape | ✅ Done |
| `risk_scorer.py` | `score_supply_risk()` (stu_pct → RiskSignal via `usda_psd.stu_risk_score`) and `score_climate_risk()` (ENSO + drought → averaged RiskSignal, origin-agnostic) — both build `RiskLevel`-classified, plain-language `RiskSignal` objects | ✅ Done |

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
| `coffee_backtests/01_ice_price_signal.ipynb` | L1: fetch real ICE KC data, validate price_position_52w correlation | ✅ Done (r=+0.852, saving=+10.73%, all gates PASS) |
| `coffee_backtests/07_wb_physical_prices.ipynb` | WB Arabica & Robusta L1 gates + basis analysis vs KC=F | ✅ Done (Arabica r=+0.835, Robusta r=+0.748, all gates PASS) |
| `coffee_backtests/02_enso_signal.ipynb` | L2b: NOAA ONI backtest, corrected El Niño thesis; gate PASSES — r=+0.288 @15m lead (KC), +0.327 @15m (WB 2000–24, p=1.4e-8); event study El Niño→+36.5% fwd-12m vs La Niña −1.7%. Original sign+lag were backwards | ✅ Done |
| `coffee_backtests/03_cot_signal.ipynb` | L5: CFTC COT backtest, **rebuilt around momentum thesis** — original contrarian gate FAILED (r=−0.05 @ fwd 12m); redefined gate PASSES: r(COT index, fwd 6m)=+0.144 (p=0.053, n=180). Weak/borderline: 3yr rolling stability only 45% positive; walk-forward $ savings don't materialize (momentum ≠ contrarian economics). Recommended role: low-weight composite amplifier, not standalone timer | ✅ Done |
| `coffee_backtests/04_usda_supply_signal.ipynb` | L2a: USDA world stocks-to-use backtest, **vintage rebuild** — fixes look-ahead bias two ways: (1) a practical 12m-forward shift of the PSD bulk file (monthly cadence, fallback), (2) the true fix via the new `usda_coffee_wmt.py` source (semiannual, no approximation). Redefined dual gate PASSES on both: approximation Gate1 r=−0.312/Gate2 r=−0.259 (n=180); true vintage Gate1 r=−0.488 (n=30, *stronger*)/Gate2 r=−0.261 (n=29, not significant). Adds 10yr rolling z-score, YoY delta, months-of-consumption features and a z-score-based non-linear stress score | ✅ Done |
| `coffee_backtests/05_chirps_signal.ipynb` | L3: CHIRPS Minas Gerais drought backtest, **SPI rebuild**. Flowering SPI-3 (Sep–Nov) deficit vs fwd-12m price r=+0.483 (p=0.069, n=15) — PASSES redefined confirming-signal gate (≥+0.30); deficit form beats signed SPI (asymmetric); robust to look-ahead (expanding r=+0.494) and to stocks control (partial r=+0.48). Low-to-mid-weight confirming amplifier | ✅ Working |
| `coffee_backtests/06_composite_backtest.ipynb` | Full composite: aligns all 5 signals onto one monthly frame (reusing nb04's step-function forward-fill for L2a/L3). **Rebuilt** from a discrete rare-event "prescience" gate (thin sample — 11-21 buy-months/10yrs, 3-4 silent years) to match the product's actual continuous always-on design: rolling-24m normalization (vs the old annual-refit, which was the sparsity's root cause — 20.0% vs 4.9% BUY rate) + `cost_improvement_backtest` (continuous volume-scaling) as the primary gate. **PASSES**: walk-forward +5.86%, beating L1-alone's own +3.71% benchmark. Confirms spike-avoidance story (sustained BUY signal before the 2024 rally). Two honest open anomalies flagged, not resolved: secondary prescience check shows BUY underperforming CAUTION/NEUTRAL in this sample; ablation reverses L5's sign vs the original notebook. §11-§12 (new): re-ran the L2a ablation on the true-vintage `stu_stress` (nb04 §16) — wrong-signed, dropping it improves the ablation more than the approximation did; final weights re-derived and promoted into `climate_features.py::WEIGHTS`. §13 (new): cross-validates `core.services.recommendation_engine.classify_normalized()` against this notebook's own rolling computation (matches to 4e-16) and saves `data/06_composite_history_true.csv` — Brazil's real historical composite history, consumed by notebook 09 §10's transferability test | ✅ Done |
| `coffee_backtests/08_producer_fx_signal.ipynb` | Producer FX PoC (USD/BRL → KC, extended to 10 origin currencies via `yfinance`): G1 PASS (monthly r=−0.316), G2/G3 FAIL — co-moves with KC/DXY, not an exploitable timing lead after controls | ✅ Done |
| `coffee_backtests/09_india_origin_signal.ipynb` | India origin backtest v2 (Arabica + Robusta, Karnataka) — rebuilt entirely on REAL India-origin data: price from `coffee_board_india_price.py` (9,217 obs, 2014-2026), supply from `coffee_board_india_supply.py`, climate from `chirps_india.py` (species-specific SPI-3 windows, now multi-district). Gate (annual r ≥ +0.30): Robusta r=−0.357 **FAIL**, Arabica r=−0.038 **FAIL** — both closed out via 2 negative experiments (multi-district weighting, Arabica 24m robustness). §6-7: global pass-through + FX decomposition — `log(india_price) ~ log(global_price) + log(usd_inr)` gives **R²=0.887 (Robusta) / 0.962 (Arabica)**, explaining 89-96% of India's price; residual re-test against the same climate gate still FAILS both species. §10 (new): the §15 forecast-transferability test — does the Brazil composite's real regime predict *forward* India price, not just the contemporaneous level relationship? **FAIL, decisively**: r(Brazil `normalized_mult`, fwd-12m India Arabica price)=−0.250 (p=0.005, n=127), wrong-signed; FX-adjusted version nearly identical (r=−0.235) — not an FX-noise artifact. `price_position_52w` sanity check passes cleanly. Composite (§8) wired for demo purposes, confidence=0.3 | ✅ Done (both gates FAIL, real data, fully diagnosed — see notebook §9-§10) |
| `coffee_data_validation/india_price_history_audit.ipynb` | Task 0 for the India origin signal — original timeboxed (~30-45min) pass found nothing (wrong domain tried: `indiacoffee.org`, dead). §6 documents the correction: a second pass found the real live domain `coffeeboard.gov.in`, with real daily price + semiannual production archives. See `docs/india_origin_signal_plan_v2_full_build.md` §12 for the full writeup | ✅ Done (superseded verdict documented, not deleted) |

---

## `tests/`

Empty test directories — tests are written alongside each implementation.

| Path | What it will test |
|------|------------------|
| `tests/core/` | Canonical models, services, storage helpers |
| `tests/domains/coffee/` | Source parsers, feature engineering, signal generator |

---

*Last updated: 2026-07-22 — India origin signal, real-data pass: found the real `coffeeboard.gov.in` domain and built `coffee_board_india_price.py` + `coffee_board_india_supply.py`, superseding the earlier WB-proxy fallback; notebook 09 rebuilt on real data (gate still FAILS, now honestly diagnosed via lag sweep + sanity check); `chirps_india.py` corrected to species-specific flowering windows*
