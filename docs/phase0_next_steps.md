# GreenSignal — Phase 0 Data & Signal Review
*Session notes for co-founder handoff · May 2026*

---

## Context

This document summarises a working session reviewing the GreenSignal Phase 0 report.
The goal was to document each signal's data sources comprehensively before rebuilding
the Phase 0 backtest results in Claude Code.

---

## Signal Data Documentation

### Signal 1 — Price Position (Layer 1)
**Source:** ICE Arabica Futures (KC=F)
**Provider:** Nasdaq Data Link — `data.nasdaq.com`
**What it is:** Daily settlement prices for the front-month ICE Arabica futures contract,
USD/lb. Global benchmark price for washed Arabica coffee.

**Schema:**
| Field | Type | Description |
|-------|------|-------------|
| date | DATE | Trading day |
| close | FLOAT | Settlement price (USD/lb) |
| volume | INT | Contracts traded (optional) |
| open_interest | INT | Outstanding contracts (optional) |

**Derived fields:**
- `52w_high`, `52w_low` — rolling 252-day max/min
- `price_position` — (close − 52w_low) / (52w_high − 52w_low), range 0–1
- `yoy_price_change` — (close − close_1y_ago) / close_1y_ago

**Frequency:** Daily; backtest uses month-end close.
**History needed:** 2008–present (2-year buffer for 2010–2025 backtest)
**Key quirk:** Use Nasdaq Data Link continuous adjusted series `CHRIS/ICE_KC1` to avoid
managing front-month rolls manually.

---

### Signal 2 — Stocks-to-Use % (Layer 2a)
**Source:** USDA Production, Supply and Distribution (PSD)
**Provider:** `apps.fas.usda.gov/psdonline` — free bulk CSV, no auth

**What it is:** Global coffee supply/demand balance sheet. Published monthly with major
revisions on WASDE release dates. Covers production, consumption, and ending stocks
by country and commodity.

**Schema (relevant fields):**
| Field | Type | Description |
|-------|------|-------------|
| commodity_code | STR | `0711100` = Coffee, Green |
| country_code | STR | `0000` = World total |
| market_year | INT | Crop year |
| month | INT | Month estimate was published |
| attribute_id | STR | `176` = Ending Stocks; `57` = Domestic Consumption |
| value | FLOAT | In 1000 60-kg bags |

**Derived field:** `stocks_to_use` = ending_stocks / domestic_consumption (%)

**Frequency:** Monthly revisions, crop-year level data.
**History needed:** 2008–present crop years.
**Key quirk:** Bulk download gives current estimates only — values are retroactively
revised. For a rigorous backtest, vintage snapshots (what was known at each point in
time) are needed. Acceptable for Phase 1; log each monthly release in production.

---

### Signal 3 — ENSO ONI (Layer 2b)
**Source:** NOAA Climate Prediction Center
**Provider:** `cpc.ncep.noaa.gov/data/indices/oni.ascii.txt` — direct download, no auth

**What it is:** Oceanic Niño Index — 3-month rolling average sea surface temperature
anomaly in the Niño 3.4 region (°C). Positive = El Niño, negative = La Niña.

**Schema:**
| Field | Type | Description |
|-------|------|-------------|
| year | INT | Calendar year |
| season | STR | 3-month season code e.g. "DJF" |
| oni | FLOAT | Temperature anomaly (°C) |

**Derived fields:**
- `oni_lagged_18m`, `oni_lagged_24m` — shifted series aligned to price impact
- `enso_risk_score` — ONI < −0.5 → La Niña flag; ONI > +0.5 → El Niño flag

**Frequency:** Monthly (overlapping 3-month seasons).
**History needed:** 2006–present (24-month lag buffer).
**Key quirk:** Fixed-width text format, not CSV. Seasons span year boundaries —
year attribution needs care when parsing.

---

### Signal 4 — Brazil CHIRPS Rainfall (Layer 3)
**Source:** CHIRPS (Climate Hazards Group InfraRed Precipitation with Station data)
**Provider:** Google Earth Engine — `earthengine.google.com` (free, 1–2 day approval)
**Fallback:** Direct NetCDF download from `data.chc.ucsb.edu` — no approval needed

**What it is:** Gridded monthly precipitation at ~5km resolution, blending satellite IR
with ground stations. Extracted as spatial average over Minas Gerais, Brazil —
dominant Arabica-producing region.

**Schema (after GEE extraction):**
| Field | Type | Description |
|-------|------|-------------|
| date | DATE | Month start |
| mean_precip_mm | FLOAT | Area-averaged precipitation (mm) |
| anomaly_mm | FLOAT | Deviation from 1981–2010 climatological mean |

**Derived fields:**
- `flowering_season_flag` — Sep/Oct/Nov indicator
- `brazil_drought_risk` — normalised anomaly score for composite

**Frequency:** Monthly.
**History needed:** 2008–present.
**Key quirk:** GEE requires Python API (`earthengine-api`). Minas Gerais boundary
loadable from FAO GAUL dataset within GEE.

---

### Signal 5 — COT Speculative Positioning (Layer 5)
**Source:** CFTC Commitments of Traders — Disaggregated Report
**Provider:** `cftc.gov/MarketReports/CommitmentsofTraders` — free, weekly, no auth

**What it is:** Weekly snapshot (Tuesday) of aggregate futures positions by trader
category on ICE Coffee KC. Non-commercial (speculative) net = longs minus shorts
held by hedge funds and managed money.

**Schema:**
| Field | Type | Description |
|-------|------|-------------|
| report_date | DATE | Tuesday of report week |
| market_name | STR | `"COFFEE C - ICE FUTURES U.S."` |
| noncomm_long | INT | Speculative long contracts |
| noncomm_short | INT | Speculative short contracts |
| noncomm_net | INT | Long − Short (derived) |

**Derived fields:**
- `cot_index` — (noncomm_net − 3y_min) / (3y_max − 3y_min), range 0–100
- `cot_contrarian_signal` — 1 if cot_index < 25, −1 if > 75, else 0

**Frequency:** Weekly (published Friday for Tuesday positions). Align to month-end
for backtest.
**History needed:** 2005–present (3-year rolling window buffer).
**Key quirk:** Use disaggregated report (not legacy) for the "Managed Money"
breakdown. Annual CSVs available on the CFTC site.

---

## Agreed Next Steps

1. **Claude Code — data pipelines first:** Get signals 1, 3, and 5 running on real
   data (all downloadable without GEE). Layer in USDA PSD next. Wait for GEE
   approval for CHIRPS.
2. **Rebuild Phase 0 backtest:** Reproduce executive summary results on real data
   and verify signal rank order holds.
3. **Price signal research (tabled):** Explore statistical signals in price data
   beyond 52-week range — mean reversion tests, regime detection, seasonality,
   futures curve term structure.

---

## Note from Anshumaan — Tasks for Each Dataset

*The following is verbatim from Anshumaan and sets the agenda for the next working
session:*

> I want to do the following tasks for each dataset:
>
> 1. Are there any unacceptable effects of data - overwritten values / predate
>    corrections etc, how can we get as-is data that show correct state of the
>    world by date.
> 2. Are there more data sources to this kind of information - give multiple
>    prompts, e.g.: one based on geography, source, granularity, etc.
> 3. State what statistical test or hypothesis you want to investigate, what's
>    the response variable, what is the metric being designed if any.
