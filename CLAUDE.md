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

| Layer | Signal | Source | Validated r |
|-------|--------|--------|-------------|
| L1 | 52-week price position | ICE KC=F via Nasdaq Data Link `CHRIS/ICE_KC1` | +0.64 |
| L2a | Stocks-to-use % | USDA PSD (`apps.fas.usda.gov/psdonline`) | −0.35 |
| L2b | ENSO ONI, 24m lag | NOAA CPC (`cpc.ncep.noaa.gov/data/indices/oni.ascii.txt`) | −0.30 |
| L3 | Brazil CHIRPS rainfall (Minas Gerais) | Google Earth Engine or `data.chc.ucsb.edu` | +0.21 |
| L5 | COT speculative net (contrarian) | CFTC disaggregated report (`cftc.gov`) | +0.15 |

---

## Data Sources & Key Quirks

**ICE KC=F (price):** Use `CHRIS/ICE_KC1` continuous adjusted series — avoids manual front-month roll management. Month-end close for backtest.

**USDA PSD (stocks-to-use):** Bulk CSV download, no auth. Commodity `0711100` = Coffee Green, country `0000` = World. `attribute_id` 176 = Ending Stocks, 57 = Domestic Consumption. Values are retroactively revised — log each monthly release in production to track vintage snapshots.

**NOAA ENSO ONI:** Fixed-width text (not CSV). Seasons span year boundaries — handle year attribution carefully when parsing. Apply 18m and 24m lags for signal generation.

**CHIRPS (Brazil):** Requires `earthengine-api` Python package for GEE extraction over Minas Gerais boundary (use FAO GAUL dataset). Fallback: direct NetCDF from `data.chc.ucsb.edu` (no approval needed). Strongest signal during flowering season: Sep–Nov.

**CFTC COT:** Use disaggregated report (not legacy) for "Managed Money" breakdown. Annual CSVs at cftc.gov. Align weekly Tuesday positions to month-end for backtest. COT index = (noncomm_net − 3y_min) / (3y_max − 3y_min).

---

## Tech Stack

| Layer | Choice |
|-------|--------|
| Package manager | uv (`pyproject.toml`) |
| Python | 3.12+ |
| Backend | FastAPI + Uvicorn |
| Frontend | React + Vite + Recharts (scaffold deferred) |
| Database | Supabase (PostgreSQL) |
| Hosting | Vercel (frontend + serverless) |
| ML | NeuralProphet or ARIMA-X with climate covariates |
| Linter | Ruff |
| Tests | pytest + pytest-asyncio |
| Notebooks | Jupyter |

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

## Phase 0 Validation Results (Baseline to Preserve)

- Price position alone: 2.2% cost improvement vs naive buying (2010–2025 backtest)
- Full 5-signal composite: **4.54% forward prescience** (vs 3.2% for L1 alone — 42% better)
- Spike avoidance (2024 Arabica +110%): 200 kg/month roaster saved ~$3,000 in one quarter

The Phase 0 backtest was built on synthetic/calibrated data. **First code priority:** rebuild it on real data and verify signal rank order holds before building the product.

---

## Build Sequence

1. Real data pipelines for L1 (ICE KC), L2b (ENSO), L5 (COT) — no GEE needed
2. Add USDA PSD (L2a) from bulk CSV
3. Add CHIRPS (L3) after GEE approval
4. Rebuild Phase 0 backtest on real data — confirm signal rank order
5. FastAPI layer with core route structure
6. React frontend: signal cards, price chart, margin calculator
