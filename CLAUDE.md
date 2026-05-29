# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Keeping This File Current

This is a living document. Update it proactively — without waiting to be asked — whenever:

- A data source, signal formula, or backtest result changes
- A tech stack decision is made or reversed
- A new architectural rule or pattern is established in code
- A Phase moves from planning to implementation (e.g., Phase 0 → Phase 1)
- A signal is validated, invalidated, or reweighted on real data
- A new domain (cacao, seafood) moves from planned to active

Edit only the affected section. Do not rewrite sections that are still accurate.

**Also update `docs/FILE_MAP.md`** whenever a file is added, removed, renamed, or its status changes (stub → implemented). The status column (`🔲 Stub` / `✅ Done` / `✅ Working`) should always reflect reality.

**Also update `docs/NEXT_STEPS.md`** at the end of every session — check off completed items, add newly discovered tasks, and record any decisions made. This is the primary handoff document between sessions and collaborators.

**Also update `CHANGELOG.md`** when anything meaningful lands on `main` — new source implemented, notebook validated, route wired up, architecture decision made. Use the existing version/date format.

---

## What GreenSignal Is

GreenSignal is a **coffee purchasing intelligence tool** for small-to-mid specialty roasters (100–500 kg/month). It aggregates public commodity data, climate signals, and supply indicators into a plain-language Buy / Hold / Caution signal per origin — giving independent roasters the same decision support large roasters have in-house, with no broker conflict of interest.

**Expansion path:** Cacao (craft chocolate) first, then specialty seafood. The infrastructure must be built to support these without a rewrite.

---

## Key Architectural Decisions

**Canonical models use Pydantic `BaseModel`** (not dataclasses). All schemas in `core/models/` inherit from `pydantic.BaseModel`. This gives FastAPI automatic JSON serialization, validation, and OpenAPI generation with no extra layer. Do not use `@dataclass` for canonical schemas.

**`core/` import boundary is enforced by `make check-imports`** — runs `grep -r "from domains" core/` and fails if anything is found. Run before committing or in CI.

**Jobs have no scheduler wired yet.** `jobs/coffee/*.py` are plain Python functions. Scheduling approach (GitHub Actions cron or lightweight VPS cron) is deferred to Phase 1. Do not add a scheduler dependency until the first job is implemented end-to-end.

---

## Architecture Principle: Vertical Product, Horizontal Core

```
Domain-specific ingestion
    → Canonical data model (core/)
    → Domain-specific feature engineering (domains/)
    → Shared scenario / risk / recommendation objects (core/)
    → Domain-specific UI and product language (apps/)
```

**Critical import rule:** `core/` must never import from `domains/`. All dependencies flow upward:

```
domains/* → core
apps/* → core, domains
jobs/* → core, domains
```

---

## Repo Structure

```
greensignal/
  pyproject.toml
  .env.example

  apps/
    web/          # React + Vite frontend (Recharts for charts)
    api/          # FastAPI backend

  core/
    models/       # Canonical schemas: Asset, MarketObservation, Forecast,
                  # RiskSignal, Recommendation, Scenario, SourceRun
    services/     # Shared engines: forecasting, scenario, recommendation,
                  # explanation, data_quality, freshness
    storage/      # db.py, repositories, migrations

  domains/
    coffee/
      sources/    # One file per data source (ice_coffee_c, usda_psd, etc.)
      features/   # price_features, climate_features, supply_features, margin_features
      models/     # forecaster, risk_scorer, signal_generator
    cacao/        # Mirror structure of coffee/

  jobs/
    coffee/       # Scheduled ingestion + forecast jobs
    cacao/

  notebooks/      # Backtests, data validation, exploration

  tests/
    core/
    domains/
```

---

## The Five-Signal Composite

The purchasing signal combines five independent signals. Simple averaging underperforms — use the **conditional formula**:

```
multiplier = (1.5 - price_position) × (1.0 + 0.65 × climate_risk_score)

climate_risk_score = 0.38 × stu_risk
                   + 0.24 × enso_risk
                   + 0.22 × brazil_drought_risk
                   + 0.16 × cot_contrarian_signal

Output range: 0.4× (strong caution) → 2.3× (high conviction buy)
```

Price position drives timing. Supply/climate signals amplify conviction when they agree.

| Layer | Signal | Source | Phase 0 r | Real-data r |
|-------|--------|--------|-----------|-------------|
| L1 | 52-week price position | ICE KC=F / Yahoo Finance `KC=F` | +0.64 (contemp) | **+0.852 (contemp); +0.201 @ 24m fwd** ✅ |
| L2a | Stocks-to-use % | USDA PSD (`apps.fas.usda.gov/psdonline`) | −0.35 | **YoY-change metric −0.04 (FAIL); but price level −0.40, annual −0.56, −0.59 @ 23m** — strong fundamental; YoY is wrong lens for an annual stock var, redefine gate to price level (cf. L1) |
| L2b | ENSO ONI, 24m lag | NOAA CPC (`cpc.ncep.noaa.gov/data/indices/oni.ascii.txt`) | −0.30 | **−0.127 @ 24m lag (FAIL); −0.338 contemporaneous** — signal peaks at 0–7m; revised to current-state amplifier |
| L3 | Brazil CHIRPS rainfall (Minas Gerais) | Google Earth Engine or `data.chc.ucsb.edu` | +0.21 | pending |
| L5 | COT speculative net (contrarian) | CFTC disaggregated report (`cftc.gov`) | +0.15 | **−0.05 @ fwd 12m (FAIL)** — contrarian thesis inverted; managed money trend-follows, r(index)=+0.14 @ fwd 3–6m; revise to momentum-confirmation role or drop |

**L1 r clarification:** The Phase 0 r = +0.64 was the *contemporaneous* `r(price_pos_52w, trailing_12m_yoy)` — not a forward-predictive r. Real data confirms it at +0.852. Forward predictive r peaks at 24m (r = +0.20, p < 0.01) — arabica trends for ~12m then mean-reverts over 24m.

---

## Data Sources & Key Quirks

**ICE KC=F (price):** Use `CHRIS/ICE_KC1` continuous adjusted series — avoids manual front-month roll management. Month-end close for backtest. Response columns: `["Date", "Open", "High", "Low", "Last", "Change", "Settle", "Volume", "Previous Day Open Interest"]`. Use **`Settle`** (official exchange settlement), not `Last` (final trade, can differ). Look up column index dynamically from `column_names` — do not hardcode position.

**Source `fetch()` contract:** All sources return `tuple[list[MarketObservation | FeatureObservation], SourceRun]`. The `SourceRun` is always returned (even on failure). `records_stored` is always `0` — persisting to the database is the job's responsibility, not the source's. Use `datetime.now(UTC)` (not `utcnow()`) for timestamps.

**USDA PSD (stocks-to-use):** Source file `usda_psd.py`. Bulk per-commodity ZIP at `https://apps.fas.usda.gov/psdonline/downloads/psd_coffee_csv.zip` (contains `psd_coffee.csv`), no auth. **Quirks verified against the live file — the original stub assumptions were wrong:** `Commodity_Code` is the **integer `711100`** (not string `"0711100"`); **there is NO World aggregate row** — PSD lists 94 individual countries, so the world total must be **summed across countries per `Market_Year`**; `Attribute_ID` **176 = Ending Stocks, 125 = Domestic Consumption** (attribute `57` is *Imports*, not consumption — do not use it). One row per (country, market_year, attribute) = latest vintage only. World stocks-to-use % = Σ(176) / Σ(125) × 100. Each marketing year's S/U is anchored to **Dec 31 of `Market_Year`**; PSD is annual, so downstream forward-fills to monthly before correlating (notebook 04). `fetch(start, end)` returns `FeatureObservation` (`feature_name="stocks_to_use_pct"`, asset `coffee:supply:world_stu`, type `supply_signal`); `load_from_csv(path)` is the offline counterpart for archived vintage snapshots. `stu_risk_score(pct)` maps S/U → 0–1 risk (provisional bounds: ≤12% → 1.0, 23.5% → 0.5, ≥35% → 0.0; calibrate in notebook 04). Values are retroactively revised — production logs each fetch as a SourceRun to track vintages. **Real-data note:** world S/U has fallen from ~22% (MY2018) to **11.6% (MY2025)** — the tightest buffer in the series.

**NOAA ENSO ONI:** Fixed-width text (not CSV). Space-delimited, 4 columns: `SEAS YR TOTAL ANOM`. We use `ANOM` (the ONI anomaly in °C). Missing-value sentinel: `-99.9` — skip silently, do not treat as parse error.
- **Year-boundary rule:** NOAA's `YR` is the calendar year of the MIDDLE month of the season. `NDJ` is the only season whose final month (January) falls in `YR+1`. All other seasons end in `YR`. Implementation: `end_year = yr + 1 if season == "NDJ" else yr`.
- **Date assignment:** Use the last day of the season's final month (`calendar.monthrange`). Example: `DJF 1950 → 1950-02-28`; `NDJ 1950 → 1951-01-31`.
- **Asset:** `climate:enso:oni` (type `climate_signal`, domain `coffee`). Returns `FeatureObservation` with `feature_name="oni_anom"`, not `MarketObservation`.
- **`enso_risk_score(oni)`:** Linear, clamped `max(0, min(1, 0.5 - oni/3.0))`. ONI ≤ −1.5 → risk=1.0 (strong La Niña); ONI=0 → risk=0.5 (neutral); ONI ≥ +1.5 → risk=0.0. La Niña (negative ONI) drives higher supply risk because it causes drought in Brazil and Vietnam 18–24 months later.
- Apply **18m and 24m lags** before correlating with Arabica prices in the composite.

**World Bank Pink Sheet (physical coffee prices):** Free, no auth. Source file `world_bank_commodity.py`. Two-step fetch: (1) GET `https://www.worldbank.org/en/research/commodity-markets` to scrape the current Excel download URL (URL embeds a monthly hash — cannot be hardcoded); (2) download and parse `CMO-Historical-Data-Monthly.xlsx`, sheet `Monthly Prices`. Series `COFFEE_ARABIC` (Other Mild Arabicas — proxy for ICO Arabica indicator; Colombia, Kenya, Tanzania washed coffees) and `COFFEE_ROBUS` (Robusta — proxy for ICO Robusta indicator). Source units are USD/kg; always convert to USc/lb (× 100/2.20462 = × 45.3592) for consistency with KC=F. Column header row is index 6 (machine codes) — locate columns dynamically, never hardcode positions. Date format: `"YYYYMmm"` (e.g. `"2026M04"`) → last day of that month. NaN values = data not yet published for that month — skip silently (not a parse error). **pandas quirk:** when reading the code-row with `df.iloc[6].astype(str)`, columns whose dtype is `float64` (because rows above them had NaN) keep `np.float64(nan)` as actual floats even after `astype(str)`; always do `df.iloc[row].fillna("").astype(str)` before string comparisons. Assets: `WB_ARABICA_BENCHMARK` (`coffee:benchmark:wb:arabica`) and `WB_ROBUSTA_BENCHMARK` (`coffee:benchmark:wb:robusta`) in `domains/coffee/registry/assets.py`.

**CHIRPS (Brazil):** Requires `earthengine-api` Python package for GEE extraction over Minas Gerais boundary (use FAO GAUL dataset). Fallback: direct NetCDF from `data.chc.ucsb.edu` (no approval needed). Strongest signal during flowering season: Sep–Nov.

**CFTC COT:** Source file `cot.py`. Use the **disaggregated** report (not legacy) for the "Managed Money" breakdown. Annual futures-only ZIPs at `https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip`, each containing one CSV (`f_year.txt` — locate by `.txt` suffix, do not hardcode the member name). No auth. Columns: `Market_and_Exchange_Names` (filter rows containing `COFFEE C - ICE`), the weekly Tuesday report date (**column name varies by vintage** — pre-2013 it is `Report_Date_as_MM_DD_YYYY`, 2013+ it is `Report_Date_as_YYYY-MM-DD`; *both carry ISO `YYYY-MM-DD` values* despite the older header, so match the common `Report_Date_as_` prefix and let `pd.to_datetime` parse — matching only `Report_Date_as_YYYY` silently drops 2010–2012), `M_Money_Positions_Long_All`, `M_Money_Positions_Short_All`. Read with `low_memory=False` (100+ columns, mixed dtypes in unused trader-count fields). The disaggregated report does not exist before 2010 — `fut_disagg_txt_2008.zip` / `2009` return HTTP 404 (handled as PARTIAL). Net managed-money = long − short. `fetch(start, end)` downloads one ZIP per calendar year in range and returns raw weekly `FeatureObservation`s (`feature_name="managed_money_net"`, asset `coffee:cot:kc`, type `positioning_signal`); a single year's HTTP/archive failure yields a PARTIAL run (not FAILED) as long as another year returns data. **Month-end alignment is a downstream/backtest concern, not the source's** — the source stays faithful to the native weekly cadence (mirrors ENSO returning raw ONI before lagging). `_cot_index(series, window=156)` returns a **0–100** rolling index `100 × (val − min) / (max − min)`; a flat trailing window (max == min) maps to 50 (neutral), not NaN. `cot_contrarian_signal(idx)`: +1 if idx < 25 (specs crowded short → buy), −1 if idx > 75 (crowded long → caution), else 0.

---

## Tech Stack

| Layer | Choice |
|-------|--------|
| Package manager | uv (`pyproject.toml`) |
| Python | 3.12+ |
| Backend | FastAPI + Uvicorn |
| Excel parsing | openpyxl (main dep) — required by `world_bank_commodity.py` to parse the WB Pink Sheet at runtime |
| Frontend | React + Vite + Recharts (scaffold deferred) |
| Database | Supabase (PostgreSQL) |
| Hosting | Vercel (frontend + serverless) |
| ML | NeuralProphet or ARIMA-X with climate covariates |
| Linter | Ruff |
| Tests | pytest + pytest-asyncio |
| Notebooks | Jupyter |

---

## Claude Code Automation Layer

### Hooks (`.claude/settings.json`)
- **PostToolUse (Edit|Write):** Ruff auto-formats every file after each edit — no manual `make format` needed
- **PreToolUse (Write|Edit):** Blocks any write to `.env` — secrets must be managed manually, never by Claude

### MCP Servers (`.mcp.json`)
- **`github`** — `@modelcontextprotocol/server-github`, auth via `GITHUB_TOKEN` env var. Use for PR management, issue triage, branch operations
- **`supabase`** — `@supabase/mcp-server-supabase`, auth via `SUPABASE_ACCESS_TOKEN`. Use when wiring storage in Phase 1

### Skills (`.claude/skills/`)
- **`implement-source`** — Step-by-step contract checklist for implementing any `domains/coffee/sources/` stub. Enforces return types, SourceRun logging, error handling, and test requirements
- **`backtest-notebook`** — Template and steps for creating the 6 validation notebooks. Enforces standard structure (fetch → quality check → feature → correlation → gate → summary)

### Agents (`.claude/agents/`)
- **`data-source-reviewer`** — Specialized subagent for reviewing a completed source implementation. Run before merging: checks contract compliance, error handling, tests, and documentation. Returns APPROVED or NEEDS WORK verdict

## Commands

```bash
uv sync                                          # install deps, create .venv
uv run uvicorn apps.api.main:app --reload        # start API dev server
uv run pytest tests/                             # run all tests
uv run pytest tests/domains/coffee/ -k price    # run a single test module
uv run ruff check .                              # lint
uv run ruff format .                             # format
make check-imports                               # enforce core/ → domains/ boundary
make verify                                      # check-imports + lint + test
```

---

## Product Framing (Affects Every Output)

Never use technical jargon in user-facing copy. Translate everything:

| Technical | User-facing |
|-----------|-------------|
| "stocks-to-use 13%" | "The world's coffee buffer is the lowest in 20 years" |
| "ENSO ONI −0.8, La Niña" | "La Niña is developing — Vietnam harvest could be short in 18 months" |
| "COT index < 25" | "Hedge funds are unusually pessimistic — often a buy signal" |
| "composite score 0.28" | "Ethiopia: near a 2-year price low. Good window to buy." |

Signal output should be actionable in under 2 minutes. The product serves the Thursday/Friday purchasing decision moment, not a research session.

---

## Phase 0 Validation Results — Updated with Real Data

**L1 (price position) — VALIDATED on real data (notebook 01 §1–8, 2010–2024):**
- Contemporaneous r = **+0.852** (Phase 0 claimed +0.64 — same metric, confirmed)
- Cost saving vs naive (full-history, in-sample): **+10.73%**
- Cost saving — **walk-forward (no look-ahead): +3.71% avg, 12/12 years positive** ← cite this in product/investor comms
- BUY zone (pos < 0.30) avg price: **135 USc/lb** vs AVOID zone (pos > 0.70): **205 USc/lb** — 52% cheaper
- Forward predictive r peaks at **24m lag** (r = +0.20), not 12m — arabica momentum lasts ~12m before mean-reverting
- All three validation gates PASS ✅
- **Momentum baseline (above 3m MA) = −10.37%** — trend-following hurts vs naive; contrarian approach validated
- **104w (2-year) window saves +15.01%** — outperforms 52w (+12.95%); consistent with 24m mean-reversion horizon (noted for composite formula tuning)

**L2a (USDA stocks-to-use) — backtested on real data; strong on price level, gate metric needs redefining (notebook 04):**
- YoY-change metric (README gate) = −0.04 → FAILS as literally specified; but r(S/U, price **level**) = **−0.40** (monthly, p≈1.7e-8), −0.56 annual (n=15), −0.59 @ 23m lag — a strong supply fundamental
- S/U is a slow annual step function: it tracks the price *level* tightly but not high-frequency YoY *momentum*; YoY-change is the wrong lens. **Redefine the L2a gate to price-level correlation (cf. L1).** On that basis L2a is the strongest fundamental after L1, preserving rank order.
- World buffer 11.6% (MY2025), tightest in series → `stu_risk_score` ≈ 1.0; calibrate the 12%/35% bounds against the realized 11.6–23% range.

**L2b (ENSO) and L5 (COT) — backtested on real data, both FAIL their original gates:**
- L2b: −0.127 @ 24m lag (gate ≤ −0.20); strongest contemporaneously (−0.338); revised to current-state amplifier
- L5: −0.05 @ fwd 12m (gate ≥ +0.08); contrarian thesis inverted — managed money trend-follows in coffee, r(COT index, fwd 3–6m) = +0.14; revise to a low-weight momentum-confirmation role or drop. Revisit `cot_contrarian_signal` sign/threshold before composite wiring.

**L3 (CHIRPS) — still on synthetic baseline (real backtest pending, blocked on GEE):**
- Full 5-signal composite: **4.54% forward prescience** (vs 3.2% for L1 alone — 42% better) — synthetic; must be re-run now that L2b/L5 failed and L2a needs a redefined gate
- Spike avoidance (2024 Arabica +110%): 200 kg/month roaster saved ~$3,000 in one quarter
- Signal rank order (L1 > L2a > L2b > L3 > L5) must be confirmed on real data before product work

**Nasdaq Data Link CHRIS access:** CHRIS futures database requires a paid subscription. Production `ice_coffee_c.py` targets `CHRIS/ICE_KC1`; backtests use Yahoo Finance `KC=F` (same instrument). Activate paid plan before deploying the production ingestion job.

---

## Build Sequence

1. Real data pipelines for L1 (ICE KC), L2b (ENSO), L5 (COT) — no GEE needed
2. Add USDA PSD (L2a) from bulk CSV
3. Add CHIRPS (L3) after GEE approval
4. Rebuild Phase 0 backtest on real data — confirm signal rank order
5. FastAPI layer with core route structure
6. React frontend: signal cards, price chart, margin calculator
