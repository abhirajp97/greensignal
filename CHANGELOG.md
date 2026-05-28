# Changelog

All notable changes to GreenSignal are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Versions are dated. Each entry covers what changed, why it matters, and who did it.

---

## [Unreleased]

Planned but not yet merged to `main`:
- Implement `noaa_enso.py` — NOAA ONI signal with 24m lag
- Implement `cot.py` — CFTC COT disaggregated report
- Backtest notebooks 02–06 on real data

---

## [0.9.0] — 2026-05-26

### Added
- `domains/coffee/sources/noaa_enso.py` — NOAA ONI source; parses fixed-width text; handles NDJ year-boundary; skips -99.9 sentinel; 26 tests, all passing
- `tests/domains/coffee/test_noaa_enso.py` — 26 tests: date conversion (DJF/NDJ/leap), risk score clamping, success path, sentinel skip, date filter, HTTP/request errors, partial run on malformed rows
- `domains/coffee/registry/assets.py` — added `ENSO_ONI` asset (`climate:enso:oni`, type `climate_signal`)
- `notebooks/coffee_backtests/02_enso_signal.ipynb` — L2b backtest with extended analysis

### Key findings (notebook 02 — ENSO L2b, real data 1980–2024)
- **Gate L2b FAILS at 24m lag** — r = −0.127 (KC=F 2010–2024) and r = +0.033 (WB Arabica 2000–2024); Phase 0 synthetic estimate of −0.30 does not hold on real data
- **Contemporaneous r IS strong** — r(ONI_lag0, price) = −0.338 (p < 0.001); La Niña NOW correlates with high prices NOW — the market prices in climate risk within months, not years
- **Signal peaks at 0–7m lag** — r crosses the −0.20 gate threshold at lags 0–7m; the textbook "18–24m supply chain lag" is not visible in 2010–2024 Arabica data
- **Composite role revised**: ENSO should be treated as a **current-state risk amplifier** (0–6m lag), not a 24m forward predictor; weight 0.24 is appropriate but mechanism differs from Phase 0 assumption
- **2024 spike adds noise**: the 2023–2024 price surge happened during an El Niño transition, not La Niña, obscuring the lagged La Niña signal

---

## [0.8.0] — 2026-05-22

### Added
- `notebooks/coffee_backtests/07_wb_physical_prices.ipynb` — L1 backtest on World Bank physical prices; all gates PASS for both Arabica and Robusta; first-ever Robusta L1 validation; Arabica basis analysis confirms r=+0.9693 vs ICE KC=F

### Key findings (notebook 07 — WB physical prices, 2010–2024, n=180)
- **WB Arabica — ALL GATES PASS**: Gate 1 r=+0.8347, Gate 2 saving=+12.08%, Gate 3 monotone (BUY=164.3 < naive=186.9 < AVOID=213.8); walk-forward avg +3.14%
- **WB Robusta — ALL GATES PASS** (first real Robusta backtest): Gate 1 r=+0.7477, Gate 2 saving=+15.12%, Gate 3 monotone (BUY=85.0 < naive=100.2 < AVOID=115.4); walk-forward avg +4.52%
- **Arabica basis**: WB physical tracks KC=F futures at r=+0.9693; mean basis +25.2 USc/lb (physical premium over futures) — confirms WB as valid alternative L1 source
- **Robusta walk-forward positive 6/12 years** — the 0.00% years are structurally correct (no BUY signals, strategy degenerates to naive; not a failure)
- **WB Arabica walk-forward +3.14%** slightly below ICE KC=F +3.71% — expected since WB is monthly physical, slightly different timing from daily futures

---

## [0.7.0] — 2026-05-22

### Added
- `domains/coffee/sources/world_bank_commodity.py` — World Bank Pink Sheet source; fetches monthly Arabica and Robusta physical spot prices (free, no auth); two-step fetch (page scrape → Excel download); converts $/kg → USc/lb; 15 tests, all passing
- `tests/domains/coffee/test_world_bank_commodity.py` — 15 tests covering success, NaN skipping, date-range filtering, unit conversion, asset routing, URL-not-found, HTTP error, and request error
- `domains/coffee/registry/assets.py` — added `WB_ARABICA_BENCHMARK` (`coffee:benchmark:wb:arabica`) and `WB_ROBUSTA_BENCHMARK` (`coffee:benchmark:wb:robusta`)
- `openpyxl>=3.1` promoted from dev dep to main dep (required at runtime by the WB source)

### Key decisions
- **World Bank Pink Sheet over ICO** — ICO monthly data costs £250; WB Pink Sheet carries the same underlying series (Other Mild Arabicas for Arabica, Robusta) free with no auth
- **Two-step fetch** — WB Excel URL embeds a monthly document hash; must scrape the commodity markets page to find the current URL rather than hardcoding
- **`fillna("").astype(str)` for code row** — `astype(str)` alone leaves `np.float64(nan)` as float in mixed-dtype pandas columns; `fillna("")` must precede it

---

## [0.6.0] — 2026-05-21

### Added
- `notebooks/coffee_backtests/01_ice_price_signal.ipynb §7` — Walk-forward test (year-by-year, no look-ahead): avg +3.71% saving, 12/12 positive years
- `notebooks/coffee_backtests/01_ice_price_signal.ipynb §8` — Signal variant comparison: momentum (above 3m MA) = −10.37% (HURTS); 104w contrarian = +15.01% (best variant, aligns with 24m mean-reversion)

### Key findings (walk-forward + variants)
- Walk-forward conservative headline: **+3.71% avg cost saving**, every year positive (2013–2024)
- Momentum-following actively destroys value (−10.37% vs naive) — validates contrarian thesis
- 104w (2-year) window outperforms 52w (15.01% vs 12.95%) — consistent with arabica's 24m reversion
- When reporting to non-technical users, cite **+3.71% walk-forward** (no look-ahead), not +10.73% (full-history, in-sample)

---

## [0.5.0] — 2026-05-21

### Added
- `notebooks/coffee_backtests/01_ice_price_signal.ipynb` — L1 backtest executed on real data; all 3 gates PASS
- `notebooks/coffee_backtests/data/ice_kc_monthly.csv` — saved reference price series for notebooks 02–06
- `domains/coffee/features/price_features.py` — implemented `price_position_52w`, `yoy_price_change`, `price_momentum_12m` (were stubs)
- `yfinance>=0.2` added to dev deps — used for backtest data fetch (Nasdaq CHRIS requires paid plan)

### Changed
- `notebooks/coffee_backtests/README.md` — L1 gate redefined: 3 tests (contemp r, cost-saving, zone monotone); Phase 0 r clarified as contemporaneous, not forward-predictive
- `CLAUDE.md` — Phase 0 results updated with real L1 data; signal table adds real-data r column; arabica 24m mean-reversion documented

### Key findings (L1 — real data 2010–2024, n=180 months)
- Contemporaneous r = **+0.852** (Phase 0 baseline +0.64 confirmed as same metric)
- Cost saving vs naive = **+10.73%** (Phase 0 estimated 2.2%)
- BUY zone avg 135 USc/lb vs AVOID zone 205 USc/lb (52% spread)
- Forward predictive r peaks at 24m (+0.20, p=0.008) — arabica trends ~12m before mean-reverting

---

## [0.4.0] — 2026-05-21

### Added
- `domains/coffee/sources/ice_coffee_c.py` — first real data source implemented; fetches `CHRIS/ICE_KC1` daily settle prices via Nasdaq Data Link, returns `tuple[list[MarketObservation], SourceRun]`
- `tests/domains/coffee/test_ice_coffee_c.py` — 8 tests covering success, partial (malformed rows), HTTP error, request error, and column-order independence
- `core/services/data_quality.py` — implemented `check_no_gaps` and `check_value_range` (were stubs)

### Fixed
- `core/models/__init__.py` — was importing non-existent `Scenario`; corrected to `ScenarioInput`, `ScenarioOutput`

---

## [0.3.0] — 2026-05-21

### Added
- `.claude/settings.json` — project-level hooks: Ruff auto-format on every Edit/Write; hard block on `.env` writes
- `.mcp.json` — GitHub MCP (`@modelcontextprotocol/server-github`) and Supabase MCP (`@supabase/mcp-server-supabase`) wired via env vars
- `.claude/skills/implement-source/SKILL.md` — custom skill enforcing the source implementation contract (return type, SourceRun, error handling, test requirements, doc updates)
- `.claude/skills/backtest-notebook/SKILL.md` — custom skill with full notebook template for all 6 validation notebooks
- `.claude/agents/data-source-reviewer.md` — subagent for pre-merge review of source implementations; returns APPROVED or NEEDS WORK verdict

### Changed
- `CLAUDE.md` — added "Claude Code Automation Layer" section documenting hooks, MCP servers, skills, and agents
- `docs/FILE_MAP.md` — added `.claude/` and root `.mcp.json` entries

---

## [0.2.0] — 2026-05-18

### Added
- `CONTRIBUTING.md` — branching workflow, naming conventions, secrets rules, `make verify` as pre-commit gate
- `docs/NEXT_STEPS.md` — session handoff document; updated by Claude at end of each working session
- `CHANGELOG.md` — this file
- Branch protection on `main`: PRs required, 1 approving review, stale approvals dismissed, force-push blocked
- `@anshquant` (Anshumaan Gandhi) added as Admin collaborator

### Changed
- Repo made public (required for branch protection on free GitHub plan; no secrets in code)

---

## [0.1.0] — 2026-05-17

### Added
- Full repo skeleton: `core/`, `domains/coffee/`, `apps/api/`, `jobs/`, `notebooks/`, `tests/`
- Canonical Pydantic models: `Asset`, `MarketObservation`, `FeatureObservation`, `Recommendation`, `RiskSignal`, `Forecast`, `ScenarioInput/Output`, `SourceRun`
- Coffee domain stubs: all 5 signal sources (`ice_coffee_c`, `noaa_enso`, `cot`, `usda_psd`, `chirps`), feature engineering, `signal_generator`, `risk_scorer`
- FastAPI app with working `GET /health` and stubbed `/coffee` routes
- `Makefile` with `lint`, `test`, `check-imports`, `verify` targets
- `docs/FILE_MAP.md` — full file map with status column, kept current alongside code
- `docs/NEXT_STEPS.md` — prioritised task list and session handoff
- `notebooks/coffee_backtests/README.md` — per-signal pass/fail gates (r thresholds) that must be met on real data before product work begins
- `CLAUDE.md` — architecture rules, key decisions, commands, build sequence, and proactive update instructions for Claude Code
- `pyproject.toml` with uv, Python 3.12+, FastAPI, Pydantic v2, Ruff, pytest

### Architecture decisions
- Canonical models use `pydantic.BaseModel` (not dataclasses) — FastAPI serialization with no extra layer
- `core/` import boundary enforced by `make check-imports` — `grep -r "from domains" core/` must return nothing
- Jobs (`daily_prices`, `monthly_supply`, `monthly_climate`) are plain `run()` functions — scheduler deferred to Phase 1
- `domains/coffee/models/forecaster.py` not created — pointless wrapper until `core/services/forecasting.py` is real
