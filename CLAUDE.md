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

climate_risk_score = 0.201 × stu_risk
                   + 0.142 × enso_risk
                   + 0.625 × brazil_drought_risk
                   + 0.031 × cot_contrarian_signal

Output range: 0.4× (strong caution) → 2.3× (high conviction buy)
```

**Weights updated from Phase 0's fixed 0.38/0.24/0.22/0.16 split** (notebook 06 §12,
real-data r-proportional, derived on the true-vintage L2a frame — see the L2a row below
and `climate_features.py::WEIGHTS`'s docstring for the full finding). `brazil_drought_risk`
(L3) is now the dominant weight by a wide margin, a reversal from Phase 0's stu_risk-heaviest
split — the true-vintage rebuild found L2a's real |r| against forward returns much weaker
than assumed. Walk-forward cost improvement with these weights: **+4.45% (2017-2024, PASS
vs the 3.0% gate)**.

Price position drives timing. Supply/climate signals amplify conviction when they agree.

**Multiple composite formulations are under active parallel exploration — not yet
converged.** This multiplicative formula (also implemented in
`domains/coffee/models/signal_generator.py` + `climate_features.py::climate_risk_score`) is
one collaborator's design and the one being validated/improved in notebook 06. A different,
structurally simpler **additive percentile-score system** also exists in
`docs/greensignal_procurement_intelligence_architecture.md` §11–12 (`price_percentile_2y`-
based point bonuses, thresholded at a score, not a multiplier). A third collaborator has been
exploring producer FX as a possible additional input (notebook 08 — tested and shelved as a
direct timing signal, "better framed as a conditioning/regime variable"; see
`docs/NEXT_STEPS.md`). Don't treat either formula above as final — reconciling them into one
production design is a deliberately deferred decision, not an oversight.

| Layer | Signal | Source | Phase 0 r | Real-data r |
|-------|--------|--------|-----------|-------------|
| L1 | 52-week price position | ICE KC=F / Yahoo Finance `KC=F` | +0.64 (contemp) | **+0.852 (contemp); +0.201 @ 24m fwd** ✅ |
| L2a | Stocks-to-use % (true vintage) | USDA Coffee: World Markets and Trade (`esmis.nal.usda.gov`, semiannual) | −0.35 | **True vintage source, dual gate, both PASS:** r(true vintage S/U, 12m-fwd price)=−0.488 (p=6.2e-3, n=30) — *stronger* than the earlier shift-approximation result (−0.312); r(true vintage delta, price level)=−0.261 (p=0.17, passes threshold but not significant at n=29, semiannual cadence). Approximation (12m shift of PSD bulk file, kept as monthly-cadence fallback) still available: r=−0.312/−0.259, both PASS |
| L2b | ENSO ONI, ~14m **lead** (El Niño) | NOAA CPC (`cpc.ncep.noaa.gov/data/indices/oni.ascii.txt`) | −0.30 | **+0.288 @ 15m lead vs fwd YoY (PASS); +0.327 @ 15m on WB 2000–24, p=1.4e-8** — original "La Niña drought" thesis had sign **and** lag backwards; corrected to El Niño supply-risk amplifier (see below) |
| L3 | Brazil CHIRPS rainfall (Minas Gerais) | Google Earth Engine or `data.chc.ucsb.edu` | +0.21 | **SPI rebuild: annual r(flowering SPI-3 Sep–Nov deficit, fwd-12m price) = +0.483 (p=0.069, n=15) → PASSES redefined gate ≥ +0.30.** Deficit `max(0,−SPI3)` beats signed SPI (−0.412, asymmetric tail risk); robust to look-ahead (expanding r=+0.494) & to stocks control (partial r=+0.48). Old monthly r≥+0.12 lens diluted an annual signal. Low-to-mid-weight confirming amplifier |
| L5 | COT speculative net (momentum) | CFTC disaggregated report (`cftc.gov`) | +0.15 | **Rebuilt around momentum thesis — PASSES: r(COT index, fwd 6m) = +0.144 (p=0.053, n=180)** vs gate ≥+0.08. Original contrarian thesis was inverted (managed money trend-follows, not fades); corrected sign/horizon in notebook 03. Weak/borderline signal: rolling 3yr stability only 45% positive (worse than a coin flip) — low-weight composite amplifier, not a standalone timer; `cot_contrarian_signal()` in `cot.py` still encodes the old disproven contrarian sign and needs updating when L5 is wired into the composite |

**L1 r clarification:** The Phase 0 r = +0.64 was the *contemporaneous* `r(price_pos_52w, trailing_12m_yoy)` — not a forward-predictive r. Real data confirms it at +0.852. Forward predictive r peaks at 24m (r = +0.20, p < 0.01) — arabica trends for ~12m then mean-reverts over 24m.

---

## Data Sources & Key Quirks

**ICE KC=F (price):** Use `CHRIS/ICE_KC1` continuous adjusted series — avoids manual front-month roll management. Month-end close for backtest. Response columns: `["Date", "Open", "High", "Low", "Last", "Change", "Settle", "Volume", "Previous Day Open Interest"]`. Use **`Settle`** (official exchange settlement), not `Last` (final trade, can differ). Look up column index dynamically from `column_names` — do not hardcode position.

**Source `fetch()` contract:** All sources return `tuple[list[MarketObservation | FeatureObservation], SourceRun]`. The `SourceRun` is always returned (even on failure). `records_stored` is always `0` — persisting to the database is the job's responsibility, not the source's. Use `datetime.now(UTC)` (not `utcnow()`) for timestamps.

**USDA PSD (stocks-to-use):** Source file `usda_psd.py`. Bulk per-commodity ZIP at `https://apps.fas.usda.gov/psdonline/downloads/psd_coffee_csv.zip` (contains `psd_coffee.csv`), no auth. **Quirks verified against the live file — the original stub assumptions were wrong:** `Commodity_Code` is the **integer `711100`** (not string `"0711100"`); **there is NO World aggregate row** — PSD lists 94 individual countries, so the world total must be **summed across countries per `Market_Year`**; `Attribute_ID` **176 = Ending Stocks, 125 = Domestic Consumption** (attribute `57` is *Imports*, not consumption — do not use it). One row per (country, market_year, attribute) = latest vintage only. World stocks-to-use % = Σ(176) / Σ(125) × 100. Each marketing year's S/U is anchored to **Dec 31 of `Market_Year`**; PSD is annual, so downstream forward-fills to monthly before correlating (notebook 04). `fetch(start, end)` returns `FeatureObservation` (`feature_name="stocks_to_use_pct"`, asset `coffee:supply:world_stu`, type `supply_signal`); `load_from_csv(path)` is the offline counterpart for archived vintage snapshots. `stu_risk_score(pct)` maps S/U → 0–1 risk (provisional bounds: ≤12% → 1.0, 23.5% → 0.5, ≥35% → 0.0) — **superseded in backtest by a z-score-based non-linear stress score validated in notebook 04, not yet promoted into this file** (see below). Values are retroactively revised — production logs each fetch as a SourceRun to track vintages, but **the bulk file itself is always the latest revised vintage, not a point-in-time snapshot** — this is a genuine look-ahead-bias risk for any backtest that uses it directly (see notebook 04's vintage-lag correction). **Real-data note:** world S/U has fallen from ~22% (MY2018) to **11.6% (MY2025)** — the tightest buffer in the series.

**USDA Coffee: World Markets and Trade (true vintage stocks-to-use):** Source file `usda_coffee_wmt.py`. **Not WASDE** — WASDE (World Agricultural Supply and Demand Estimates) does not cover coffee at all (grains/oilseeds/cotton/sugar/livestock only, confirmed via web search); the correct USDA report for coffee is this separate semiannual (Jun/Dec) PDF circular, archived back to June 2004 at `https://esmis.nal.usda.gov/publication/coffee-world-markets-and-trade`. Fixes the look-ahead bias in `usda_psd.py` (below) properly instead of approximating it: each circular is genuinely time-stamped, reporting the world "Total" Ending Stocks and Domestic Consumption as they were estimated **at that report's own publication date** — no shift/forward-fill approximation needed. **Discovery:** the archive listing is paginated (`?page=0,1,2,...`, 10/page, HTML `<table>`); past the real archive depth the pager does **not** return an empty page — it wraps back to repeating page-0 content — so pagination must stop when a page adds *no new report dates*, not merely when a page is empty (a real bug caught and fixed during implementation). **Parsing:** report layout drifted across 20+ years (pre-2011 one combined "Table 01A"; 2011+ split across paginated "Coffee Summary" pages) — both anchor on the literal phrase `"Thousand 60-Kilogram Bags"`, present on every summary-table page and nowhere else (critically, **not** on the page-1 narrative subsection that is *also* literally titled "Ending Stocks" in many issues — anchoring on this phrase avoids grabbing that false positive). Within the anchored segment, locate `"Domestic Consumption"` / `"Ending Stocks"` headers and the nearest following `"Total <n1> <n2> ...>"` line; take the **last** (newest) number. Reports before June 2010 fail to parse (different/older format) and are skipped — acceptable, since the notebook 04 backtest window starts in 2010. `fetch(start, end)` returns `FeatureObservation` (`feature_name="stocks_to_use_pct"`, asset `coffee:supply:world_stu_vintage`, type `supply_signal`), one observation per report **dated to the report's own publication date**; per-report download/parse failures degrade to PARTIAL (mirrors `cot.py`'s per-year degradation) rather than failing the whole run. **Cross-validated:** the Dec 2025 report parses to 11.59% S/U, matching `usda_psd.py`'s independently-computed 11.6% for the same period. Main deps added: `pdfplumber` (PDF text extraction) and `beautifulsoup4` (listing HTML parsing).

**NOAA ENSO ONI:** Fixed-width text (not CSV). Space-delimited, 4 columns: `SEAS YR TOTAL ANOM`. We use `ANOM` (the ONI anomaly in °C). Missing-value sentinel: `-99.9` — skip silently, do not treat as parse error.
- **Year-boundary rule:** NOAA's `YR` is the calendar year of the MIDDLE month of the season. `NDJ` is the only season whose final month (January) falls in `YR+1`. All other seasons end in `YR`. Implementation: `end_year = yr + 1 if season == "NDJ" else yr`.
- **Date assignment:** Use the last day of the season's final month (`calendar.monthrange`). Example: `DJF 1950 → 1950-02-28`; `NDJ 1950 → 1951-01-31`.
- **Asset:** `climate:enso:oni` (type `climate_signal`, domain `coffee`). Returns `FeatureObservation` with `feature_name="oni_anom"`, not `MarketObservation`.
- **`enso_risk_score(oni)`:** Linear, clamped `max(0, min(1, 0.5 + oni/3.0))`. ONI ≥ +1.5 → risk=1.0 (strong El Niño); ONI=0 → risk=0.5 (neutral); ONI ≤ −1.5 → risk=0.0 (strong La Niña). **El Niño (positive ONI) drives higher supply risk** — it droughts Vietnam + Indonesia robusta at flowering (the largest producers by volume) and stresses parts of Brazil, with the shortfall reaching market ~12–16 months later. This **corrects the original inverted thesis** ("La Niña causes Brazil/Vietnam drought") — the sign was flipped. ENSO effects are origin-specific (see `docs/enso_coffee_country_matrix.html`): El Niño hurts SE-Asia robusta but is *beneficial* for Colombia and roughly neutral/mildly-positive for Brazil arabica (frost avoidance), so net |r| stays modest (~0.3) and the signal is a low-weight amplifier, not a standalone timing signal.
- Apply a **~14m lead** (not 18–24m) before correlating with Arabica prices. The signal is against **forward** YoY price change: high ONI now → price up ~14m later. The strong *contemporaneous* negative r(ONI, price) ≈ −0.34 is a lead/lag artifact of ENSO's quasi-periodicity (La Niña follows the El Niño that caused the shortage) — do **not** read it as "La Niña → high prices". Validated in notebook 02: r=+0.288 @15m (KC 2010–24) / +0.327 @15m (WB 2000–24, p=1.4e-8); event study El Niño months → +36.5% fwd-12m vs La Niña −1.7% (t=5.83).

**World Bank Pink Sheet (physical coffee prices):** Free, no auth. Source file `world_bank_commodity.py`. Two-step fetch: (1) GET `https://www.worldbank.org/en/research/commodity-markets` to scrape the current Excel download URL (URL embeds a monthly hash — cannot be hardcoded); (2) download and parse `CMO-Historical-Data-Monthly.xlsx`, sheet `Monthly Prices`. Series: Arabica (Other Mild Arabicas — proxy for ICO Arabica indicator; Colombia, Kenya, Tanzania washed coffees) and Robusta (proxy for ICO Robusta indicator). Source units are USD/kg; always convert to USc/lb (× 100/2.20462 = × 45.3592) for consistency with KC=F. **Header-row count is not stable — confirmed drift, not hypothetical:** WB dropped the machine-code header row entirely in a 2026-07-02 update (previously row 4 = human name, 5 = unit, 6 = machine code, data from row 7; now row 4 = human name, 5 = unit, data from row 6 — one row earlier, no advance notice). Found live while auditing India price sources (see `docs/india_origin_signal_plan_v2_full_build.md`) — the hardcoded-row-index version silently returned zero observations. Fixed to locate the first data row dynamically (first row whose column 0 matches the `"YYYYMmm"` pattern) and search every row above it for a target series label, matching either the legacy machine code (`COFFEE_ARABIC`/`COFFEE_ROBUS`) or the current human-readable name (`"Coffee, Arabica"`/`"Coffee, Robusta"`) — never hardcode row indices for this file. Date format: `"YYYYMmm"` (e.g. `"2026M04"`) → last day of that month. NaN values = data not yet published for that month — skip silently (not a parse error). **pandas quirk:** when reading a header row with `df.iloc[row].astype(str)`, columns whose dtype is `float64` (because rows above them had NaN) keep `np.float64(nan)` as actual floats even after `astype(str)`; always do `df.iloc[row].fillna("").astype(str)` before string comparisons. `MarketObservation.raw` carries whichever label matched as `"wb_series"` (renamed from `"wb_code"` since it may now hold a name, not a code). Assets: `WB_ARABICA_BENCHMARK` (`coffee:benchmark:wb:arabica`) and `WB_ROBUSTA_BENCHMARK` (`coffee:benchmark:wb:robusta`) in `domains/coffee/registry/assets.py`.

**CHIRPS (Brazil):** Source file `chirps.py`. Uses `earthengine-api` (now a main dep). GEE auth: interactive `earthengine authenticate` (cached at `~/.config/earthengine/`) + Cloud project in env **`EARTHENGINE_PROJECT`** (ours: `western-plate-432020-t5`) — `ee.Initialize(project=...)` requires a project since 2023. Collection `UCSB-CHG/CHIRPS/PENTAD` (select `precipitation`), clipped to the **FAO GAUL level-1 polygon** `ADM1_NAME == "Minas Gerais"` (true state shape, better than the rectangular bbox in `regions.py`), `scale=5566` m. All ee interaction is isolated in `_query_monthly_precip` (one server-side `map` + a single `getInfo()`); aggregate pentads to monthly **sums**, then `reduceRegion` mean over the polygon. `fetch(start, end)` returns RAW monthly area-mean rainfall (mm) anchored to month-end (asset `climate:chirps:minas_gerais`, `feature_name="precip_mm"`) — anomaly/risk derived downstream, like ENSO. `drought_risk_score(anomaly_mm, is_flowering_season)` rises as rainfall falls below normal (full risk at −60 mm; off-season halved); `is_flowering_month` = Sep–Nov. Climatology check confirms correct extraction: wet Nov–Mar (~200 mm), dry Jun–Aug (~10 mm). Fallback `load_from_netcdf(path)` reads a direct NetCDF from `data.chc.ucsb.edu` (no GEE), lazy-imports `xarray` (not a hard dep) and raises a clear ImportError if absent.

**CHIRPS (India, Kodagu):** Source file `chirps_india.py` — a new module, not a parameterized `chirps.py` (that file backs the validated, live Brazil composite; refactoring tested/working code for marginal reuse wasn't worth the risk). Same GEE query logic, different constants: **FAO GAUL level-2** `ADM2_NAME == "Kodagu"` (district, not state — confirmed live-resolvable: `ADM0=India, ADM1=Karnataka, ADM2=Kodagu`), asset `climate:chirps:kodagu`. **Species-specific flowering windows** — `is_flowering_month(month, species)` requires `species` explicitly (no default): Robusta `{2, 3}` (pre-monsoon blossom showers late Feb-mid Mar), Arabica `{4, 5}` (needs rain by mid-April) — verified against real agronomy sources; do NOT use one shared window for both species (an earlier version of this file did) or reuse Brazil's Sep–Nov. **Live-only GEE bug found and fixed:** `reduceRegion().get("precipitation", default)` still raises `Dictionary.get: Dictionary does not contain key` even with a `default` argument if that default is `None` — GEE's own docs note "unless it is null" the default is ignored. Only surfaces for months with no CHIRPS coverage yet (e.g. fetching up to `date.today()`); `chirps.py`'s Brazil backtest never hit this since it only ever queried a fixed 2010–2024 window. Fixed with a real sentinel (`_NO_DATA_SENTINEL = -9999.0`) mapped back to `None` in `_precip_or_none()`.

**Coffee Board of India daily price (`coffeeboard.gov.in`):** Source file `coffee_board_india_price.py`. Live domain is `coffeeboard.gov.in` — **not** `indiacoffee.org` (dead; a first pass at this source wrongly concluded no India price source existed because it only tried that domain). Free, no auth, but the Daily Market Report archive is a **stateful ASP.NET WebForms flow**, not a simple URL: GET `Market_Info.aspx` → POST with `__EVENTTARGET=lbnarchives` (cross-page post) → `Market_Info_Archives.aspx` (a year × month `GridView1` grid, 2012–present) → POST selecting a month (control IDs are **not** a simple function of the year — e.g. 2020's column control is literally named `LinkButton64`, not `LinkButton2020`; parse the live grid's row/column structure every time, never construct control names algorithmically) → `Archives_Month.aspx` (a `DataList1` of archived days that month) → POST selecting a day → **the response body IS that day's PDF** (no separate download URL). Every step must carry forward the previous response's `__VIEWSTATE`/`__EVENTVALIDATION` hidden fields. `httpx.Client` needs `follow_redirects=True` explicitly (unlike `requests`, which follows redirects by default — this tripped up the first implementation). Extracts the **"Raw Coffee Price (Karnataka)"** table (`Ar.Pmt`/`Ar.Chy`/`Rob.Pmt`/`Rob.Chy`, ₹/50kg, as a `LOW - HIGH` range — `value` is the midpoint, `raw` carries the range) via a regex anchored on the table's own `"as on DD.MM.YYYY"` line, **not** the report's nominal date — the two can differ by several days. **Real cadence:** despite "daily" bulletins, this figure only updates ~weekly in practice (confirmed by observing identical values repeat across consecutive archived days) — dating to the table's own "as on" date makes duplicates collapse correctly rather than manufacturing fake daily noise. Real density starts **2014** (2012–2013 predate the table's consistent presence in the archive — near-zero rows). **Politeness:** paces day-level requests with a 2-second delay — a small government server, not a CDN; a full historical backfill is thousands of requests and takes hours by design. Assets: `INDIA_ARABICA` (`coffee:origin:india:arabica`), `INDIA_ROBUSTA` (`coffee:origin:india:robusta`).

**Coffee Board of India production estimates (`coffeeboard.gov.in`):** Source file `coffee_board_india_supply.py`. Parses the semiannual **"Database on Coffee" PDF circular** (`database-coffee.html` — a simple static listing, ~62 editions back to Jan 2009, unpaginated unlike `usda_coffee_wmt.py`'s ESMIS archive). Anchors on the stable phrase `"Production of Coffee in Major States/Districts"` (the leading section number drifts — 1.6 in 2013/2016, 1.7 in 2022, 1.8 in 2024 — same class of drift as `usda_coffee_wmt.py`). Unlike that PDF, this one has a genuine extractable table grid — `pdfplumber.extract_tables()` parses it cleanly, no text-position heuristics needed. Takes the **newest (leftmost) marketing-year column** per report as that report's point-in-time vintage observation (mirrors `usda_coffee_wmt.py`'s no-look-ahead discipline, not USDA PSD's always-latest-revised one). Report date comes from the cover page's own stated month/year (e.g. "January 2013") — some editions duplicate characters from a bold-font extraction quirk (e.g. "JJuunnee // JJuullyy 2016"); collapse repeated character runs before matching month names, and take the later month if two are mentioned. District name footnote markers vary (`"Kodagu #"` vs `"Kodagu *"`) — strip either. **`FeatureObservation` has no metadata field** (only `asset_id`/`observed_date`/`feature_name`/`value`/`source`) — region and species are encoded directly into `feature_name` (e.g. `"production_mt:kodagu:arabica"`, `"production_mt:india:total"` for the national Grand Total row) rather than adding many new per-district registry assets. One entry (Oct 2013 "Part II") is genuinely mislinked on the government site itself (`Pasupathi/` instead of `Database/` in the URL) — a real typo, not a bug here; degrades that one report to a download failure (PARTIAL run). Asset: `INDIA_PRODUCTION` (`coffee:supply:india:production`).

**CFTC COT:** Source file `cot.py`. Use the **disaggregated** report (not legacy) for the "Managed Money" breakdown. Annual futures-only ZIPs at `https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip`, each containing one CSV (`f_year.txt` — locate by `.txt` suffix, do not hardcode the member name). No auth. Columns: `Market_and_Exchange_Names` (filter rows containing `COFFEE C - ICE`), the weekly Tuesday report date (**column name varies by vintage** — pre-2013 it is `Report_Date_as_MM_DD_YYYY`, 2013+ it is `Report_Date_as_YYYY-MM-DD`; *both carry ISO `YYYY-MM-DD` values* despite the older header, so match the common `Report_Date_as_` prefix and let `pd.to_datetime` parse — matching only `Report_Date_as_YYYY` silently drops 2010–2012), `M_Money_Positions_Long_All`, `M_Money_Positions_Short_All`. Read with `low_memory=False` (100+ columns, mixed dtypes in unused trader-count fields). The disaggregated report does not exist before 2010 — `fut_disagg_txt_2008.zip` / `2009` return HTTP 404 (handled as PARTIAL). Net managed-money = long − short. `fetch(start, end)` downloads one ZIP per calendar year in range and returns raw weekly `FeatureObservation`s (`feature_name="managed_money_net"`, asset `coffee:cot:kc`, type `positioning_signal`); a single year's HTTP/archive failure yields a PARTIAL run (not FAILED) as long as another year returns data. **Month-end alignment is a downstream/backtest concern, not the source's** — the source stays faithful to the native weekly cadence (mirrors ENSO returning raw ONI before lagging). `_cot_index(series, window=156)` returns a **0–100** rolling index `100 × (val − min) / (max − min)`; a flat trailing window (max == min) maps to 50 (neutral), not NaN. `cot_contrarian_signal(idx)`: +1 if idx < 25 (specs crowded short → buy), −1 if idx > 75 (crowded long → caution), else 0.

---

## Tech Stack

| Layer | Choice |
|-------|--------|
| Package manager | uv (`pyproject.toml`) |
| Python | 3.12+ |
| Backend | FastAPI + Uvicorn |
| Excel parsing | openpyxl (main dep) — required by `world_bank_commodity.py` to parse the WB Pink Sheet at runtime |
| Geospatial / climate | earthengine-api (main dep) — required by `chirps.py` for GEE CHIRPS extraction; auth via `EARTHENGINE_PROJECT` env |
| PDF parsing | pdfplumber (main dep) — required by `usda_coffee_wmt.py` to extract text from historical USDA circular PDFs |
| HTML parsing | beautifulsoup4 (main dep) — required by `usda_coffee_wmt.py` to parse the ESMIS archive listing pages |
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
- **Note — format ≠ lint:** the PostToolUse hook runs `ruff format` only. It does **not** run `ruff check`, so lint errors (empty f-strings, import order, ambiguous names) slip past it. CI is the backstop that catches them — run `make verify` before committing.

### CI (`.github/workflows/verify.yml`)
- Runs `make verify` (check-imports + lint + test) on every push to `main` and every PR. This is the **enforced** gate — CLAUDE.md asks contributors to run `make verify` locally, but that is convention; only CI/branch-protection guarantees nothing red reaches `main`. Uses `uv sync --frozen`, so an out-of-date `uv.lock` also fails CI.
- **To make it blocking:** enable branch protection on `main` (Settings → Branches → require the `verify` status check). Until then CI is informational — a red run does not prevent a merge/push.
- **Doc freshness is *not* enforced by a hook** — it is the "Keeping This File Current" instructions in this file, which every Claude Code session in this repo loads automatically. It is prompt-level (model-dependent), not a deterministic gate; a manual commit or a non-complying agent can skip it.

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
| "ENSO ONI +0.8, El Niño" | "El Niño is developing — Vietnam's harvest could be short in ~14 months, supporting prices" |
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

**L2a (USDA stocks-to-use) — vintage rebuild; true-vintage source now implemented; dual gate PASSES on real data (notebook 04):**
- **Look-ahead bias identified and fixed twice:** first with a practical 12-month-forward shift of the PSD bulk file's monthly-ffilled series (simulating the publication lag PSD's always-latest-revised-vintage doesn't reflect), then properly with a new source, `usda_coffee_wmt.py`, that parses USDA's actual time-stamped semiannual circular ("Coffee: World Markets and Trade" — **not WASDE**, which doesn't cover coffee) for a genuinely point-in-time series. Both are in notebook 04; the true-vintage series is now the primary evidence, the shift approximation the documented fallback (pre-June-2010 coverage, or when a monthly-cadence input is needed between semiannual reports).
- Approximation: once lagged, raw r(S/U, price level) = −0.40 weakens to **r=−0.26**. True vintage: r(true vintage S/U, 12m-fwd price) = **−0.49** — *stronger* than the approximation. The two methods agree directionally but only moderately (r=+0.49 between them, mean abs diff 3.1pp) — the shift was a reasonable stand-in, not a validated substitute.
- Redefined gate is **two tests**, both **PASS** on both the approximation (Gate 1 r=−0.312 p=2.0e-5 n=180; Gate 2 r=−0.259 p=4.6e-4 n=180) and the true vintage series (Gate 1 r=−0.488 p=6.2e-3 n=30; Gate 2 r=−0.261 p=0.17 n=29 — passes the threshold but not significant at this small semiannual-cadence sample). Replaces the old single YoY-change gate (r=−0.04, wrong lens for an annual step-function var).
- Added a **10-year rolling z-score** (no additional look-ahead beyond the vintage lag), a **YoY delta** (the "shock" dimension), and **months of consumption** as roaster-legible features, computed on the PSD-derived annual series. World buffer 11.6% (MY2025) → Z=−1.96, a once-in-a-generation tight read, 1.4 months of consumption in storage.
- **Non-linear stress score replaces the linear clamp:** `stress = clamp((−z + 2) / 4, 0, 1)`, self-calibrating against the series' own 10yr history instead of fixed 12%/35% percent bounds. Not yet promoted into `usda_psd.py`/`supply_features.py` — stays notebook-local until composite wiring (06), per the L3/SPI precedent (same holds for the new true-vintage series).
- Rolling 3yr stability (on the approximation series) is honest but modest: 52% of windows negative (up from 23% on the old YoY-change basis, but not strong on its own) — the full-sample gates (n=180, p<0.001-scale) are the stronger evidence.

**L2b (ENSO) — re-backtested with corrected thesis; now PASSES (notebook 02):**
- The original gate (r ≤ −0.20 @ 24m lag, "La Niña drought") FAILED because both the **sign and the lag were wrong**. The country matrix (`docs/enso_coffee_country_matrix.html`, verified against peer-reviewed sources) shows El Niño — not La Niña — is the dominant coffee supply-risk phase: it droughts Vietnam + Indonesia robusta at flowering, while La Niña is *beneficial* for those origins and for Brazil arabica (frost avoidance) and only hurts Colombia.
- Redefined gate (r ≥ +0.20 vs **forward** YoY, 10–18m band) **PASSES**: r=+0.288 @15m lead (KC 2010–24, p=1.6e-4) and r=+0.327 @15m (WB 2000–24, p=1.4e-8 — confirms it is not a single-2024 artifact). Event study: El Niño months → **+36.5%** fwd-12m vs La Niña −1.7% (Welch t=5.83, p<0.001).
- `enso_risk_score` sign flipped (now rises with El Niño). Stays a low-weight amplifier (|r|~0.3 because the Brazil-arabica frost channel offsets the SE-Asia drought channel), but it now clears its gate — upgrade L2b from "weak amplifier" to a validated lead signal.

**L5 (COT) — rebuilt around the momentum thesis; now PASSES its gate (notebook 03):**
- Original contrarian thesis (gate ≥+0.08 @ fwd 12m) was inverted on real data — managed money trend-follows in coffee, not fades. Rebuilt gate: `r(COT index, fwd 6m change) ≥ +0.08` → **PASSES at r=+0.144** (p=0.053, n=180, 2010–2024); horizon sweep confirms 6m as the peak (3m close behind at r=+0.140, decays to ~0 by 18–24m).
- Signal is real but weak and borderline: p=0.053 is at the edge of conventional significance, and 3yr rolling stability holds in only **45% of windows** (worse than a coin flip). Walk-forward cost-saving does not materialize in the same framework as L1 — momentum signals don't reduce weighted-average purchase price the way contrarian signals do (buying more when COT is high means buying when price is already elevated); the notebook concludes the correct role is a **low-weight composite amplifier, not a standalone timer**.
- `cot_contrarian_signal()` in `cot.py` still encodes the old, disproven contrarian sign/threshold (+1 crowded short, −1 crowded long) — needs updating to the momentum framing when L5 is wired into the composite (notebook 06).

**L3 (CHIRPS) — SPI rebuild; now PASSES a redefined confirming-signal gate (notebook 05):**
- Rebuilt around **SPI** (gamma-fit Standardized Precipitation Index) instead of the raw mm anomaly. Primary feature = **flowering SPI-3 deficit** (Sep–Nov accumulation ending Nov, `max(0,−SPI3)`), evaluated on the **annual crop-year frame** vs forward-12m Arabica price: **r=+0.483 (p=0.069, n=15)**, up from the old raw-mm annual +0.398.
- The old gate (monthly r ≥ +0.12) was the wrong frame — a plain monthly Pearson dilutes a signal concentrated in one 3-month window per year (same class of frame error fixed for L2b/L2a). **Redefined gate: annual r ≥ +0.30 (confirming signal) → PASS.**
- Signal is **asymmetric** (deficit form beats signed SPI −0.412 → drought is a one-sided tail risk), **robust to look-ahead** (expanding-window SPI r=+0.494, n=9), and **independent of the supply balance** (partial r controlling for stocks-to-use = +0.48). Tercile study: driest vs wettest flowering third → +33.6% vs +9.5% fwd-12m.
- Remains a **low-to-mid-weight confirming amplifier** (explains *why* a buy window opens: "Minas Gerais flowering was dry"), not a standalone timing signal — L1/L2 drive timing. **When wiring the composite, promote the SPI flowering-deficit feature into `climate_features.py`** (replacing the provisional mm-anomaly `drought_risk_score` in `chirps.py`) and feed it as a continuous z-score, not a 0/1 flag.

**All 5 sources implemented, backtested, and now composited (notebook 06) — rebuilt once to fix a real product-fit problem in the first version.**

The first version of notebook 06 passed its gate (discrete "forward prescience after BUY" ≥3.50%) but on a thin sample: only 11–21 buy-months across the 10 walk-forward test years (2015–2024), 3–4 with *zero* buy months. Flagged by the product owner as a real problem — a tool that goes silent for years can't serve the weekly purchasing decision GreenSignal exists to support (see "Product Framing" above — this is the same "actionable in under 2 minutes" requirement, applied to the composite backtest's own methodology, not just the UI copy).

**Re-reading the product docs confirmed the mismatch was in the backtest, not the product design:** GreenSignal is built as a continuous, always-on 3-state signal (`docs/GreenSignal_ICP.md`, `coffee_intelligence_mvp.md` — "A roaster checks the signal in 2 minutes... Not a research dashboard"). Phase 0's own synthetic target has L1 alone firing BUY 22% of months (`docs/GreenSignal_Phase0_Report.md` §2.1); real data confirms 35–41% — not sparse at all. The sparsity was introduced by the backtest's own methodology.

- **Root cause, found and fixed:** the walk-forward re-derived its normalization baseline once per *calendar year* from an expanding window (annual-refit), producing lumpy 12-month buckets. A **rolling 24-month** trailing-window normalization (recomputed every month, closer to how `price_position_52w` itself already works) raised the BUY rate from 4.9% to 20.0% and cut the longest silent gap from 18 to 16 months — confirmed directly, not assumed, by running both side by side with identical weights.
- **Primary gate switched from the discrete prescience test to the continuous `cost_improvement_backtest` methodology** (`docs/GreenSignal_Math_Reference.md` §11.1 — the same one notebook 01 used to validate L1 alone), since that's what Phase 0's own doc treats as the primary ROI story and what actually mirrors the product's continuous purchase-volume-scaling design. **PASSES: walk-forward +5.86%**, *exceeding* L1-alone's own walk-forward benchmark (+3.71%) — full-history is +4.45% (vs. L1-alone's +10.73%).
- **Spike avoidance confirmed directly:** the composite held a sustained BUY signal through most of Jan–Sep 2023 (price $146–190/lb), *before* the 2024 rally accelerated past $220/lb and kept climbing — a real instance of the "buy before the spike" behavior `docs/GreenSignal_Phase0_Report.md` §3.2 frames as the actual product story for smaller roasters.
- **Two honest open anomalies, reported rather than smoothed over:** (1) the secondary (discrete, 3-state) prescience check shows BUY months *underperforming* CAUTION/NEUTRAL forward returns in this sample — tempered by using in-sample fixed weights rather than the walk-forward weights that pass the primary gate, and plausibly reflecting the 2023–2025 structural supply-shock rally where mean-reversion timing underperforms momentum; (2) the leave-one-out ablation **reverses sign for L5** vs. the original notebook (dropping `cot_momentum` now *helps* by +0.56pp, was −0.81pp) — which sub-signals earn their weight is sensitive to the validation metric and weighting scheme used, a reason to treat any single ablation result as provisional. L2b (`enso_risk`) remains the strongest contributor in both versions.
- **Multiple collaborators are independently exploring different composite formulas right now** (see above) — this rebuild specifically validates and improves the multiplicative formula already implemented in `signal_generator.py`, not a claim that it's the converged team design.
- **Resolved — `stu_stress` rebuilt off the true-vintage series (notebook 04 §16, notebook 06 §11), and the result is a real negative finding, not the expected confirmation.** True-vintage `stu_stress` (window=6 small-n z-score, n=25 valid semiannual observations) is **wrong-signed** against `fwd_6m` (r=−0.135, vs the approximation's +0.262), and dropping it from the composite *improves* walk-forward cost improvement by +0.79pp — worse than the approximation's near-neutral −0.03pp. L2a still passes its own standalone gate against 12m-forward **price level** (r=−0.488) — genuinely different from the composite's 6m-forward-**return** ablation target, not a contradiction: stocks-to-use may validly track where price sits without predicting near-term moves. **Weights re-derived on the true-vintage frame and promoted into `climate_features.py::WEIGHTS`**: stu_risk 0.201 (down from Phase 0's 0.38), enso_risk 0.142, brazil_drought_risk 0.625 (now dominant), cot_contrarian 0.031. Walk-forward with final weights: +4.45% (2017-2024, PASS vs 3.0% gate).

**Nasdaq Data Link CHRIS access:** CHRIS futures database requires a paid subscription. Production `ice_coffee_c.py` targets `CHRIS/ICE_KC1`; backtests use Yahoo Finance `KC=F` (same instrument). Activate paid plan before deploying the production ingestion job.

---

## India Origin Signal (Arabica + Robusta, Karnataka) — Parallel Track, Own Gate

Built end-to-end (branch `feat/india-origin-signal`) as a second origin, separate
from and not blocking the notebook 06 anomaly reconciliation above. Full writeup:
`docs/india_origin_signal_plan_v2_full_build.md` (§12 is the current authoritative
state — §1-11 is an earlier pass whose price-source conclusion turned out to be
wrong, corrected below). Motivation: an easier potential sales inroad for demoing
GreenSignal to Indian roasters.

**Status: real India-origin data throughout (price, supply, climate); gate still
FAILS, honestly diagnosed rather than reframed.** First pass settled for a World
Bank global-benchmark price proxy after `indiacoffee.org` proved unreachable and
got an expected FAIL. Told explicitly not to settle for a proxy or self-impose
artificial timelines, a second pass found the real thing: **Coffee Board of
India's actual live domain is `coffeeboard.gov.in`**, not `indiacoffee.org`. It
publishes a genuine daily "Raw Coffee Price (Karnataka)" series and a semiannual
production-estimate circular — both now real, tested production sources, no
proxy needed.

- **`domains/coffee/sources/coffee_board_india_price.py`** — scrapes
  `coffeeboard.gov.in`'s Daily Market Report archive, a stateful ASP.NET WebForms
  flow (page → postback → year/month grid → postback → day list → postback →
  that day's PDF as the POST response body). Extracts the "Raw Coffee Price
  (Karnataka)" table (Arabica/Robusta, Parchment/Cherry, ₹/50kg, as a low-high
  range). Paced deliberately (2s between requests — small government server) and
  resumable. **Real cadence discovery:** despite "daily" bulletins, the figure
  only updates ~weekly in practice (confirmed by observing identical values
  repeat across consecutive archived days) — each observation is dated to the
  table's own "as on" date, so this collapses correctly rather than manufacturing
  fake daily noise. Real density starts 2014 (2012-2013 predate the table's
  consistent presence). Full backfill: 9,217 raw observations, 2012-2026.
- **`domains/coffee/sources/coffee_board_india_supply.py`** — parses
  `coffeeboard.gov.in`'s semiannual "Database on Coffee" PDF circular (~62
  editions back to 2009, static listing, no pagination) for district + national
  production estimates. `pdfplumber.extract_tables()` parses this cleanly (a
  real structured grid, unlike `usda_coffee_wmt.py`'s PDF which needs
  text-position heuristics). Vintage-aware like `usda_coffee_wmt.py` — each
  report's own newest marketing-year column is used, not a later revision.
  `FeatureObservation` has no metadata field, so region+species are encoded into
  `feature_name` (e.g. `"production_mt:kodagu:arabica"`). Full backfill: 1,289
  observations, 2010-2024 (PARTIAL — one report mislinked on the government site
  itself, "Pasupathi/" instead of "Database/" in the URL; a real, harmless typo).
- **Climate leg corrected to species-specific windows:** `chirps_india.py`
  originally used one Feb-Mar window for both species (copied from the generic
  agronomy template) — verified against real sources to be wrong for Arabica.
  `is_flowering_month(month, species)` now requires species explicitly: Robusta
  `{2, 3}` (pre-monsoon blossom showers late Feb-mid Mar), Arabica `{4, 5}`
  (needs rain by mid-April, roughly a month later).
- **Notebook 09 gate FAILS on real data too — but a different, more diagnosed
  result than the proxy-based FAIL.** Annual r(flowering SPI-3 deficit, fwd
  price) ≥ +0.30 bar: **Robusta r=−0.357 at 12m (n=12)** — wrong-signed at every
  horizon tested from 3-24 months (a lag sweep, not just one fixed horizon).
  **Arabica r=−0.038 at 12m (n=12)** — much closer to zero than the proxy test's
  −0.214, and turns positive at longer horizons (24m: +0.179, echoing L1's own
  24m mean-reversion finding), but still short of the bar. Supply (production
  YoY) vs fwd-6m price: r=−0.110, p=0.564, n=30 — no standalone relationship.
  **`price_position_52w`'s own sanity check passes cleanly for both species**
  (BUY-zone avg < ALL avg < CAUTION-zone avg, monotone) — the price data and
  feature engineering are sound; it's specifically the climate/supply-to-price
  mechanism under test that doesn't clear its gate. See notebook 09 §6 for the
  full diagnostic writeup (lag sweep, standalone supply test, sanity check) and
  plausible unconfirmed explanations (n=12 is thin; Kodagu-only vs. a
  production-weighted multi-district signal is untried; India price may be
  dominated by factors — global pass-through, currency, domestic policy — this
  composite doesn't model).
- **Composite runs live for demo purposes** (`generate_india_signal()`,
  confidence set to 0.3 — lower than a merely-untested proxy would warrant, since
  this is now a climate mechanism tested on real data that didn't clear its
  gate) — suitable for showing product mechanics and UI/copy shape to
  stakeholders, **explicitly not** as a validated India timing signal.
- **Three live-only bugs found and fixed along the way** (all real production
  bugs, not India-specific in cause): World Bank's Pink Sheet Excel format drift
  (see `world_bank_commodity.py` above), a GEE `Dictionary.get` default-value gap
  (see `chirps_india.py` above), and an `httpx.Client` redirect-following default
  that differs from `requests`' (the new India price source needed
  `follow_redirects=True` explicitly).
- **Both flagged follow-up experiments now closed out, same session, real
  negative results (notebook 09 §4c-4d; full writeup in plan doc §13):**
  - **Production-weighted multi-district climate signal** — `chirps_india.py`
    extended with a `district` parameter (Kodagu/Chikmagalur/Hassan), weighted
    by each district's production share (52%/33%/14%). **Does not rescue the
    signal**: Robusta improves marginally but stays wrong-signed (r=−0.357 →
    −0.285, still FAIL); Arabica moves toward zero (r=−0.038 → −0.016, still
    FAIL). Weak evidence against "wrong district" as the primary cause — the
    climate mechanism itself, not the district chosen, looks like the bigger
    issue.
  - **Arabica 24m hint robustness check** — leave-one-out on the r=+0.179 @
    24m figure ranges **[−0.065, +0.395]** (sign flips depending on which year
    is excluded); 5,000-resample bootstrap 90% CI is **[−0.356, +0.622]**
    (spans both zero and the gate). **Conclusion: the 24m hint was noise, not
    a real weak effect** — n=12 carries almost no statistical information here;
    only new years of price history, not cleverer analysis, can move it.
- **A real data-quality bug found and fixed:** `coffee_board_india_supply.py`
  district rows were splitting into duplicate series for the same real
  district due to spelling drift across PDF editions ("Chikkamagaluru" vs
  "Chikmagalur", "Wyanad" vs "Wayanad", "Orissa" vs "Odisha" — the last a
  genuine 2011 state rename). Fixed with a `_REGION_ALIASES` map in
  `_region_slug()`; deliberately did **not** merge "Andhra Pradesh" with
  "Andhra Pradesh & Orissa" (older editions genuinely combine two states into
  one row — a structural difference, not a spelling variant).
- **A real external incident, handled without cutting a security corner:**
  mid-session, re-fetching the full supply backfill failed with
  `CERTIFICATE_VERIFY_FAILED` — `coffeeboard.gov.in`'s TLS cert expires
  2026-07-22 (confirmed via direct `openssl` inspection), the same day, and
  the site was unreachable over both HTTPS and HTTP. A caching-script mistake
  compounded this: the re-fetch's empty result was written over the
  previously-good 1,289-observation supply CSV without checking success
  first, destroying it (git-untracked, unrecoverable). **Bypassing SSL
  certificate verification to force the fetch through was explicitly rejected**
  as a workaround — that trades a data-loss problem for a MITM/data-integrity
  risk. Recovered instead by re-parsing 4 locally-cached PDF editions into a
  reduced 168-observation snapshot (sufficient for the district-weight
  experiment above, not for the full national YoY test's original power).
  **A full 62-report re-backfill is still needed once the site's certificate
  is renewed** — a genuine, external, currently-blocked follow-up.
- **Global pass-through + FX decomposition (2026-07-28) — resolves *why* the
  climate gate fails, not just *that* it fails.** External review diagnosed the
  structural reason before this ran: India produces ~3.5% of world coffee and
  exports most of it — a price taker, not a price setter — so the causal arrow
  should run from the global benchmark + FX into India's price, not from local
  weather into price. Tested directly in notebook 09 §6-7:
  `log(india_price) ~ log(global_price) + log(usd_inr)` (World Bank Pink Sheet
  benchmark reused from notebook 07's cache; USD/INR via `yfinance`, notebook
  08's already-validated fetch pattern) — **R²=0.887 (Robusta) / 0.962
  (Arabica)**, both FX coefficients positive as expected and highly significant
  (p<0.001). Global pass-through + FX explains 89-96% of India's domestic
  price — not a partial explanation, close to the whole story.
  **Residual re-test** (same ≥+0.30 gate against the pass-through residual,
  not raw price) still FAILS for both species: Arabica r=+0.033 (indistinguishable
  from zero); **Robusta r=−0.587 (p=0.045, n=12) — more significant AND more
  wrong-signed than the raw-price test**, stable across the 6-24m lag sweep. Read
  plainly, a wetter (not drier) Robusta flowering season associates with a
  *higher* pass-through-adjusted price a year-plus later — a genuinely
  surprising result, reported as such rather than explained away; it argues for
  "this climate construction doesn't capture the right mechanism," not just
  "needs more data." **Product-narrative implication:** a validated India
  signal is far more accurately framed as global-price-plus-FX than a
  local-climate timing signal — materially different from `generate_india_signal()`'s
  current 2-input composite, feeding into the still-pending card-copy review.
  Two items remain deliberately out of scope (larger, separate passes):
  discrete regulatory/policy event dummies (EUDR, India-EFTA) and
  harvest-window (Nov-Feb) rainfall as a different climate pathway from the
  flowering-window SPI-3 already built.

---

## Build Sequence

1. ✅ Real data pipelines for L1 (ICE KC), L2b (ENSO), L5 (COT) — no GEE needed
2. ✅ Add USDA PSD (L2a) from bulk CSV
3. ✅ Add CHIRPS (L3) via GEE (project `western-plate-432020-t5`)
4. ✅ Composite backtest (notebook 06) on real data, **rebuilt once** — first version passed on a discrete, thin-sample metric; rebuilt around a continuous cost-improvement gate + rolling-24m normalization to match the product's always-on design. PASSES: walk-forward +5.86% (beats L1-alone's +3.71%). Two anomalies flagged, not resolved (§7/§8 disagreements, see above)
4a. ✅ **`stu_stress` rebuilt off the true-vintage series and L2a ablation re-run (notebook 04 §16, notebook 06 §11-§12)** — a real, reportable negative finding, not the hoped-for confirmation: true-vintage `stu_stress` is **wrong-signed** against `fwd_6m` (r=−0.135, vs the approximation's +0.262) and dropping it from the composite *improves* walk-forward cost improvement by +0.79pp — more than the approximation's near-neutral −0.03pp. L2a still passes its own standalone gate (12m-fwd **price level**, r=−0.488) — a genuinely different target than the composite's 6m-**forward-return** ablation, not a contradiction. **Weights re-derived and promoted into `climate_features.py::WEIGHTS`**: `stu_risk=0.201, enso_risk=0.142, brazil_drought_risk=0.625, cot_contrarian=0.031` (L3 now dominant, a reversal from Phase 0's stu_risk-heaviest split). Walk-forward with final weights: **+4.45% (2017-2024, PASS vs 3.0% gate)**
4b. ✅ **`domains/coffee/models/risk_scorer.py` implemented** — `score_supply_risk(asset_id, signal_date, stu_pct)` (reuses `usda_psd.stu_risk_score`) and `score_climate_risk(asset_id, signal_date, enso_risk, drought_risk)` (simple average of the two, origin-agnostic — no region name baked into `source`, since CHIRPS extraction is per-origin). Both classify into `RiskLevel` via a plain quartile split of the 0-1 score and write plain-language `rationale` text. 9 new tests
4c. ✅ **Rolling-24m normalization wired via `core/services/recommendation_engine.py::classify_normalized()`** — a separate, explicit function (`classify_normalized(current_multiplier, trailing_multipliers) -> tuple[float, Action]`), not a change to `build_recommendation()`'s signature: that function is pure/single-point-in-time and has no way to hold a trailing history, so normalization stays an opt-in step for callers that have one (a notebook backtest today; a future job with persisted history once Build Sequence step 6 lands). Reuses the same `_BUY_THRESHOLD`/`_CAUTION_THRESHOLD` constants, applied to `current_multiplier / mean(trailing 24 months)` instead of the raw multiplier — matches notebook 06 §4/§12's validated `mult.rolling(24, min_periods=12).mean().shift(1)` exactly. Raises below 12 trailing observations (the notebook's own `min_periods`). 7 new tests
4d. ✅ **India §15 forecast-transferability test run — a decisive FAIL, real and reportable.** With production wiring complete (true-vintage L2a, finalized weights, `classify_normalized()`), notebook 09 §10 tested whether the Brazil composite's real historical BUY/CAUTION/NEUTRAL regime predicts forward India Arabica price — not just the contemporaneous level relationship §14 already proved. **r(Brazil normalized_mult, fwd-12m India price) = −0.250 (p=0.005, n=127), wrong-signed and significant** — BUY months averaged −0.38% forward India price vs +17.71% for NEUTRAL and +14.51% for CAUTION, the opposite of what a working timing signal would show. FX-adjusted version (isolating the coffee-only story from FX) gives nearly the same result (r=−0.235, p=0.008) — this isn't primarily an FX-noise artifact. **Conclusion: India price levels move with global price + FX at the same time (§14, still true), but the global composite's forward-looking regime does not carry forecasting power for India price specifically** — likely adjustment lags or sticky domestic pricing, a real and distinct phenomenon from the pass-through relationship itself. Rules out the "one global composite, translated per-origin" architecture for India specifically; doesn't invalidate §14's product-narrative finding (India price is a global-plus-FX story) or the broader architectural hope for other origins. See `docs/india_origin_signal_plan_v2_full_build.md` §15 and `docs/NEXT_STEPS.md` for the full writeup
5. ← **NEXT:** Reconcile the notebook 06 §7/§8 anomalies. Confirm which composite formula is being wired first — multiple collaborators are exploring different designs (see composite section above). India's card-copy calibrated-honesty review (still pending) should now incorporate §15's finding alongside §14's — a validated India signal isn't yet demonstrated as a *timing* signal via any tested route, global-composite-translation or local-climate
6. Independent engineering work (can parallelize): `core/storage/repositories.py` (stub — nothing is currently persisted despite 6 working sources) + job wiring, `margin_features.py`
7. FastAPI layer with core route structure
8. React frontend: signal cards, price chart, margin calculator

**Parallel track — India origin signal (Arabica + Robusta, Kodagu):** built in a
separate sprint (`feat/india-origin-signal`), reusing this build sequence's Brazil
infrastructure rather than replicating it. See "India Origin Signal" section above
for the full status — summary: real India-origin price, supply, and climate data
throughout (no proxy); registry, `chirps_india.py` (now multi-district),
`build_recommendation`, and `generate_india_signal` are all real and running on
live data; the notebook 09 backtest gate **FAILS for both species** on genuine
India-origin data, and all three flagged follow-up experiments (multi-district
weighting, Arabica 24m robustness, and global pass-through + FX decomposition)
have since been run and closed out — the last of these explains *why* the
first two failed: India's domestic price is 89-96% explained by global
benchmark + FX pass-through, not local climate. This is a fully diagnosed
methodology finding, not a data-availability gap. **A fourth test (§15,
run once Brazil's production wiring was complete) closes the loop: the
Brazil composite's regime does NOT predict forward India price** (r=−0.250,
wrong-signed, p=0.005) — the pass-through relationship holds at the price
*level* but doesn't transfer as a *timing* signal. Not validated for
roaster-facing promotion yet; full supply re-backfill blocked pending
`coffeeboard.gov.in`'s TLS certificate renewal.
