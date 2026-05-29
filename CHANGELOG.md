# Changelog

All notable changes to GreenSignal are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Versions are dated. Each entry covers what changed, why it matters, and who did it.

---

## [Unreleased]

Planned but not yet merged to `main`:
- Redefine the L2a gate to price-level correlation (cf. L1) after the YoY-metric mismatch
- Decide L5 composite role (momentum-confirmation vs drop) after the notebook 03 FAIL
- Apply for GEE access → implement `chirps.py` (L3); then composite notebook 06

---

## [0.13.0] — 2026-05-28

### Added
- `notebooks/coffee_backtests/04_usda_supply_signal.ipynb` — L2a USDA stocks-to-use backtest (real data, 26 marketing years; 180 monthly points 2010–2024): forward-fill annual S/U to monthly, correlation vs price level + YoY change, lag sweep, annual-level robustness check, rolling stability, interpretation cell

### Key findings (notebook 04 — L2a, real data 2010–2024)
- **Literal YoY-change gate FAILS** — r(S/U, trailing YoY price change) = **−0.04** (gate ≤ −0.25)
- **But the supply signal is strong on price level** — r(S/U, price level) = **−0.40** (p≈1.7e-8); annual-level r = **−0.56** (n=15, p=0.03); best lagged r = **−0.59 @ 23m**. The 23m peak ≈ two crop cycles of supply tightness feeding into price
- **Metric mismatch, not a weak signal** — S/U is a slow annual step function; it tracks the low-frequency price *level* tightly but not high-frequency YoY *momentum*. The Phase 0 −0.35 (YoY) baseline was a synthetic artifact
- **Recommendation:** redefine the L2a gate to price-level correlation, mirroring the L1 gate redefinition. On that basis L2a passes (|r|=0.40–0.59) and is the strongest fundamental after price — rank order L1 > L2a > L2b > L3 > L5 holds
- World buffer at **11.6% (MY2025)**, tightest in series → `stu_risk_score` ≈ 1.0, a strong current BUY-side amplifier

---

## [0.12.0] — 2026-05-28

### Added
- `domains/coffee/sources/usda_psd.py` — USDA PSD world stocks-to-use source (L2a); `fetch(start, end)` downloads the coffee bulk ZIP, aggregates ending stocks / domestic consumption across all 94 reporting countries per marketing year, returns world stocks-to-use % as `FeatureObservation`; adds `stu_risk_score` (0–1 supply risk) and keeps `load_from_csv` (offline vintage snapshots) + `stocks_to_use`; 20 tests, all passing
- `tests/domains/coffee/test_usda_psd.py` — 20 tests: `stocks_to_use`, `stu_risk_score` (clamping/midpoint), world aggregation across countries, attribute/commodity filtering, incomplete-year skip, date filter, dynamic CSV member, `load_from_csv`, HTTP/request/bad-zip/missing-attribute failures
- `domains/coffee/registry/assets.py` — added `USDA_STU` asset (`coffee:supply:world_stu`, type `supply_signal`)

### Fixed (stub assumptions corrected against the live file)
- `Commodity_Code` is the **integer `711100`**, not the string `"0711100"`
- **No World aggregate row exists** — PSD lists 94 individual countries; the world total is summed across countries per marketing year (the stub's `country 0000 = World` does not exist in the file)
- **Attribute `125` = Domestic Consumption**; the stub's `57` is *Imports* — using it would have computed stocks-to-imports

### Key data point
- World coffee stocks-to-use has fallen from **~22% (MY2018) to 11.6% (MY2025)** — the tightest buffer in the series, on-thesis for L2a (low buffer → price pressure)

---

## [0.11.0] — 2026-05-28

### Added
- `notebooks/coffee_backtests/03_cot_signal.ipynb` — L5 COT backtest on real data (CFTC disaggregated, 835 weekly obs 2010–2025); forward-horizon correlation sweep, gate validation, 3yr rolling stability, interpretation cell

### Fixed
- `domains/coffee/sources/cot.py` — date-column detection now matches the `Report_Date_as_` prefix (was `Report_Date_as_YYYY`). Pre-2013 vintages name the column `Report_Date_as_MM_DD_YYYY` (carrying ISO values), so 2010–2012 were being silently dropped; data now starts 2010 as intended. Added `low_memory=False` to the CSV read to suppress mixed-dtype warnings on unused trader-count columns. New regression test `test_pre_2013_date_column_name` (21 tests total)

### Key findings (notebook 03 — COT L5, real data 2010–2024, n=180 months)
- **Gate L5 FAILS** — r(contrarian signal, fwd 12m change) = **−0.05** (required ≥ +0.08); negative at every horizon ≤ 18m
- **Contrarian thesis is inverted** — managed money *trend-follows* in coffee: r(COT index, fwd 3–6m return) = **+0.14** (specs crowded long → prices keep rising short-term), peaking at 6m (p ≈ 0.05). Consistent with notebook 01's ~12m Arabica momentum
- **Unstable** — 3yr rolling r spans −0.64 to +0.86; positive in only 68% of windows
- **Composite implication** (parallels ENSO/L2b): do not use COT as a standalone contrarian timing signal — either flip to a low-weight 3–6m momentum-confirmation role or drop L5. Revisit the sign/threshold of `cot_contrarian_signal` before wiring into `signal_generator`
- Signal rank order L1 > L2a > L2b > L3 > L5 holds: L5 is the weakest, now failing its gate

---

## [0.10.0] — 2026-05-28

### Added
- `domains/coffee/sources/cot.py` — CFTC disaggregated Commitments of Traders source (L5); downloads annual `fut_disagg_txt_{year}.zip` files, filters to `COFFEE C - ICE`, returns weekly net managed-money positions (long − short) as `FeatureObservation`; 20 tests, all passing
- `tests/domains/coffee/test_cot.py` — 20 tests: `_cot_index` (min/max/midpoint/flat-window/range), `cot_contrarian_signal` boundaries, success path (market filter, net calc, sorting, date filter, dynamic ZIP member), multi-year PARTIAL on a failing year, PARTIAL on malformed rows, FAILED on HTTP/request/bad-zip errors
- `domains/coffee/registry/assets.py` — added `COT_KC` asset (`coffee:cot:kc`, type `positioning_signal`)

### Key decisions
- **Disaggregated (not legacy) report** — needed for the "Managed Money" speculative breakdown; net = `M_Money_Positions_Long_All − M_Money_Positions_Short_All`
- **Source returns raw weekly Tuesday positions** — month-end alignment for the monthly backtest is a downstream concern (mirrors ENSO returning raw ONI before lagging), keeping the source faithful to the native weekly cadence
- **`_cot_index` returns 0–100** — to match the 25/75 thresholds in `cot_contrarian_signal`; flat trailing window (max == min) maps to 50 (neutral) rather than NaN
- **Per-year download is fault-tolerant** — one year's HTTP/archive failure yields a PARTIAL run as long as another year returns data; only a fully empty result is FAILED
- **ZIP member located dynamically** — annual file is `f_year.txt`, but matched by `.txt` suffix rather than hardcoded name

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
