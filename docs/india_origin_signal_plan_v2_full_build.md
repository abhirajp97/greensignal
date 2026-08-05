# GreenSignal India — Full Build Plan (v2.2 — real India-origin price source found)

**Status (2026-07-22 update):** The v2.1 pass below concluded no India-origin price
source existed and fell back to a WB global-benchmark proxy — notebook 09's gate
FAILED on that basis. **That conclusion has been superseded.** Told explicitly not
to settle for a proxy or self-impose artificial timelines, a second, unhurried pass
found the real thing: Coffee Board of India's actual live domain is
**`coffeeboard.gov.in`**, not the unreachable `indiacoffee.org` v2.1 tried. It
publishes a genuine daily "Raw Coffee Price (Karnataka)" series (Arabica/Robusta,
Parchment/Cherry) back to 2012, plus semiannual district-level production estimates
back to 2009 — both now implemented as real sources
(`coffee_board_india_price.py`, `coffee_board_india_supply.py`) and being backfilled.
See §12 for the full discovery writeup and what changes as a result. **The rest of
this document (§1-§11) is the v2.1 record of the first pass — kept for its still-valid
reasoning (Kodagu scope, flowering-window agronomy, composite formula shape) but its
price-source and gate-result claims are now stale; see §12 for what supersedes them.**
**Owner:** Abhiraj
**Goal:** Ship a real India Buy / Neutral / Caution recommendation for Arabica and
Robusta origins — same output schema, same trust tier, same "decision support, not
price prediction" framing as the ICE-benchmark composite. Not a downgraded card
product. The difference from the benchmark is the underlying data and calibration,
not the ambition.

**Non-negotiable:** this only gets promoted to roasters as a Buy/Caution label once
it clears a backtest gate — even a deliberately looser, honestly-documented one given
thinner history than the ICE series. That's not scope-cutting, it's the same
calibration discipline already written into `GreenSignal_Math_Reference.md` §10.1:
*"An overconfident signal destroys trust... permanently."* Get there fast, but get
there validated. Until it clears a gate, the card carries an explicit
**"accumulating validation" label** — softer framing for early sales conversations is
not the trade-off being made here.

---

## 0. What changed from v2 → v2.1

v2 was written before parts of the current codebase existed and drifted from what's
actually here. Corrections, found via direct repo inspection (not assumption):

- **No FRED source exists anywhere in this repo** (grepped, zero hits). v2's claim
  that "you already use FRED elsewhere per `phase0_next_steps.md`" was false —
  that doc never mentions FRED. **FX now goes through `yfinance` (`INR=X`)**,
  extending the pattern `08_producer_fx_signal.ipynb` already validated for other
  origin currencies (BRL, COP, PEN, MXN, GTQ, HNL, NIO, VND, IDR, ETB). No new
  FRED-style production source is being built for v1.
- **`domains/coffee/registry/regions.py` is a plain `@dataclass Region` with a
  hardcoded WGS84 bounding box** — not the `RegionSpec(gaul_level=...)` class v2
  invented. That bbox is consumed only by `chirps.py`'s netcdf fallback. The live
  Google Earth Engine path's GAUL admin-name lookup is hardcoded as **module
  constants inside `chirps.py` itself** (`_GAUL_COLLECTION`, `_REGION_ADM1`), not
  read from `regions.py` at all. India follows the same split: a `KODAGU` bbox entry
  in `regions.py` for fallback/documentation parity, plus its own GAUL constants in
  a new source module.
- **`FeatureObservation`'s date field is `observed_date`, not `timestamp`** — v2's
  code snippets used the wrong field name throughout.
- **No new API routes needed.** `apps/api/routes/coffee.py` already exposes generic
  `asset_id`-parameterized stub routes (`GET /coffee/origins/{asset_id}/signal`,
  etc.). Once India assets exist in the registry, these routes cover India for free.
  v2's §9 proposal to add `india-arabica`/`india-robusta`-specific routes is dropped.
- **`climate_risk_score()` and `generate_signal()` are Brazil-coupled, not
  origin-generic.** `climate_risk_score()` weight-combines four Brazil-specific
  inputs (STU, ENSO, Brazil drought, COT); India realistically has **one** climate
  input (rainfall), so there's nothing to weight-combine — India's climate source's
  own risk score *is* its climate risk input directly. `generate_signal()` calls
  `climate_risk_score()` internally, so it isn't reusable for India as-is. What *is*
  reusable is the formula **shape**
  (`multiplier = (1.5 - price_position) × (1.0 + k × climate_risk)`), via a new,
  additive `generate_india_signal()` — see §7.
- **A genuine, newly-discovered wrinkle v2 missed entirely:** Brazil's CHIRPS query
  uses **FAO GAUL level-1** (`ADM1_NAME`, state granularity — "Minas Gerais"). India's
  coffee belt (Kodagu, Chikmagalur, Hassan, Wayanad) is **district**-level, i.e.
  **GAUL level-2** (`ADM2_NAME`) — not a same-level string swap. See §5.1.
- **`core/services/recommendation_engine.py::build_recommendation()` is still an
  unimplemented stub** (`...` body, returns `None`) — it documents the composite
  formula in its docstring but doesn't apply it. This blocks a clean India composite
  call unless implemented first (§7) — a small, self-contained fix, also unblocks
  the existing Brazil production-wiring path noted as CLAUDE.md's own "NEXT" step.
- **Notebook numbering**: `coffee_backtests/` is already at 01–08 (07 = World Bank
  physical prices, 08 = producer FX exploration). The India backtest notebook is
  **`09_india_origin_signal.ipynb`**, not `07` as v2 assumed.
- **Scope confirmed with product owner (2026-07-21):** both **Arabica and Robusta**
  ship in v1 (both grown in Kodagu, so climate infra is shared); v1 targets
  **Kodagu only** (India's largest coffee district, ~30% of national output, both
  species grown there) rather than all four districts v2 listed — multi-district
  averaging is a Phase 2 refinement, not a demo blocker; **FX is in scope** for this
  build (not deferred, since the pitch benefits from USD-comparable framing against
  the global benchmark).

---

## 1. File Map Delta (corrected)

| File | Purpose | Status |
|---|---|---|
| `domains/coffee/registry/assets.py` | `INDIA_ARABICA`, `INDIA_ROBUSTA`, `CHIRPS_KODAGU`, `FX_USD_INR` | 🔲 Edit |
| `domains/coffee/registry/regions.py` | `KODAGU` bbox entry (netcdf-fallback/documentation parity, mirrors `MINAS_GERAIS`) | 🔲 Edit |
| `domains/coffee/sources/chirps_india.py` | GEE CHIRPS rainfall over Kodagu (GAUL level-2), India blossom-shower risk score | 🔲 New |
| `domains/coffee/sources/india_coffee_price.py` | Real India price source **if** Task 0 finds one; otherwise this file is skipped and `WB_ARABICA_BENCHMARK`/`WB_ROBUSTA_BENCHMARK` (already implemented) are wired directly | 🔲 New (conditional) |
| `domains/coffee/features/price_features.py` | No changes — `price_position_52w` etc. already auto-detect daily/monthly frequency | ✅ Reused as-is |
| `domains/coffee/features/climate_features.py` | No changes — India's single climate input needs no weight-combining | ✅ Reused as-is (not extended) |
| `core/services/recommendation_engine.py` | `build_recommendation()` — implement the currently-stubbed formula for real | 🔲 Edit (was stub) |
| `domains/coffee/models/signal_generator.py` | `generate_india_signal()` — new, additive; `generate_signal()` (Brazil) untouched | 🔲 Edit |
| `notebooks/coffee_data_validation/india_price_history_audit.ipynb` | Task 0 — timeboxed price/climate data availability audit | 🔲 New |
| `notebooks/coffee_backtests/09_india_origin_signal.ipynb` | Full backtest/demo, following the `backtest-notebook` skill template, both species + FX leg | 🔲 New |
| `notebooks/coffee_backtests/README.md` | India gate row(s) or accumulating-validation note | 🔲 Edit |
| `tests/domains/coffee/test_chirps_india.py`, `test_india_coffee_price.py` | Source tests, mocked per existing `test_chirps.py` pattern | 🔲 New |
| `docs/FILE_MAP.md`, `docs/NEXT_STEPS.md`, `CHANGELOG.md`, `CLAUDE.md` | Handoff updates once something real lands | 🔲 Edit |

---

## 2. Task 0 — Price + Climate Data Audit (timeboxed, do this first)

**Why this comes first:** everything downstream — window sizes, gate thresholds, how
soon this can be honestly promoted — depends on how much clean history actually
exists. Don't guess.

**Confirmed time-box: ~30–45 minutes.** Build
`notebooks/coffee_data_validation/india_price_history_audit.ipynb`:

1. Check whatever the Coffee Board of India's own site exposes as historical price
   bulletins (domain may have moved from `indiacoffee.org` — verify current URL).
   Look for a downloadable archive, not just a "today's price" page. Do this for
   **both** Arabica and Robusta grades.
2. Check ICO (International Coffee Organization) indicator prices as a free
   historical cross-check/fallback framing (not India-specific, but legitimate).
3. Document a clear per-species verdict: "usable clean history starts ~[date]" or
   "falling back to WB benchmark proxy."

**If the timebox runs out without a clean multi-year India-specific series:** fall
back to the already-implemented `WB_ARABICA_BENCHMARK` / `WB_ROBUSTA_BENCHMARK`
(World Bank Pink Sheet, `world_bank_commodity.py`) as the price series, with an
explicit "tracked via global benchmark, India-specific series pending" note carried
through to the card copy. This is a legitimate, pre-agreed v1 path — not a
compromise to hide. It costs zero new source code, since both benchmark assets
already exist.

**If a real India series is found:** proceed with a real backtest, scaling window
sizes down from the benchmark's as the audit dictates, and expect gates closer to,
but still looser than, the ICE L1 bar (see §8).

Either branch is fine. Guessing which one you're in without running the audit is not.

---

## 3. Registry Additions

### 3.1 `domains/coffee/registry/assets.py`

Follows the existing `Asset` pydantic model exactly (`asset_id`, `domain`,
`asset_type`, `name`, `unit`, `metadata`) — same shape as `BRAZIL_ARABICA` etc.:

```python
INDIA_ARABICA = Asset(
    asset_id="coffee:origin:india:arabica",
    domain="coffee",
    asset_type="origin",
    name="India Arabica (Kodagu)",
    unit="lb",  # consistent with every other origin asset; native price stored in metadata/source currency
    metadata={
        "country": "India",
        "species": "arabica",
        "regions": ["kodagu"],
        "growing_system": "shade_grown",
    },
)

INDIA_ROBUSTA = Asset(
    asset_id="coffee:origin:india:robusta",
    domain="coffee",
    asset_type="origin",
    name="India Robusta (Kodagu)",
    unit="lb",
    metadata={
        "country": "India",
        "species": "robusta",
        "regions": ["kodagu"],
        "growing_system": "shade_grown",
    },
)

CHIRPS_KODAGU = Asset(
    asset_id="climate:chirps:kodagu",
    domain="coffee",
    asset_type="climate_signal",
    name="CHIRPS Rainfall — Kodagu (India Arabica/Robusta)",
    unit="mm",
    metadata={
        "source": "UCSB CHIRPS via Google Earth Engine",
        "gee_collection": "UCSB-CHG/CHIRPS/PENTAD",
        "region": "FAO GAUL level-2 ADM2_NAME='Kodagu'",  # district, not state — see §5.1
        "description": (
            "Monthly area-mean precipitation (mm) over Kodagu, India's largest "
            "coffee district. Below-normal rainfall during the Feb-Mar blossom "
            "shower window threatens flowering and is bullish for price."
        ),
    },
)

FX_USD_INR = Asset(
    asset_id="fx:usd_inr",
    domain="coffee",
    asset_type="fx_signal",
    name="USD/INR Exchange Rate",
    unit="inr_per_usd",
    metadata={
        "source": "Yahoo Finance",
        "ticker": "INR=X",
        "description": "Used to express India origin prices comparably to the USD-denominated global benchmark.",
    },
)
```

Add all four to `ALL_ASSETS`.

### 3.2 `domains/coffee/registry/regions.py`

Same shape as the existing `Region` dataclass (bbox, netcdf-fallback/documentation
parity only — the live GEE path reads its own constants from the source module, not
from here):

```python
KODAGU = Region(
    region_id="india:kodagu",
    name="Kodagu",
    asset_id="coffee:origin:india:arabica",
    lat_min=11.85,
    lat_max=12.75,
    lon_min=75.35,
    lon_max=76.15,
)
```

Add to `ALL_REGIONS`.

---

## 4. Source Adapters

### 4.1 India price source (contingent on Task 0)

**If Task 0 finds a real source:** `domains/coffee/sources/india_coffee_price.py`,
following the `implement-source` skill contract exactly — same `fetch()` shape as
`ice_coffee_c.py`/`world_bank_commodity.py`:

```python
def fetch(start: date, end: date) -> tuple[list[MarketObservation], SourceRun]:
    ...

# MarketObservation(
#     asset_id="coffee:origin:india:arabica",  # or :robusta
#     observed_date=<date>,          # NOT `timestamp` — corrected field name
#     value=<price>,
#     unit=<whatever the source's native unit is>,
#     source="india_coffee_price",
#     metadata={"grade": ..., "raw": {...}},
# )
```

Store every grade available, not just the benchmark grade — grade spread may be
informative and is cheap to store now versus re-fetch later.

**If Task 0 doesn't find a real source in the timebox:** no new file — wire
`WB_ARABICA_BENCHMARK` / `WB_ROBUSTA_BENCHMARK` (`world_bank_commodity.py`, already
implemented) directly as the India price series in the notebook/composite, with the
"tracked via global benchmark" note carried into card metadata.

### 4.2 `domains/coffee/sources/chirps_india.py`

**New module** (not a parameterization of `chirps.py` — that file backs the
validated, live Brazil composite, and refactoring tested/working code for marginal
reuse benefit isn't worth the risk here). Copy `chirps.py`'s GEE query logic
verbatim; change only the module constants:

```python
_GAUL_COLLECTION = "FAO/GAUL/2015/level2"  # district, not state (level-1) — see §0
_REGION_ADM2 = "Kodagu"                     # filter on ADM2_NAME, not ADM1_NAME

_SOURCE_ID = "coffee:chirps_india"
_SOURCE_TAG = "gee:chirps_pentad_india"
_FEATURE_NAME = "precip_mm"

# Karnataka Arabica blossom-shower window (Feb-Mar) — NOT Brazil's Sep-Nov.
# Provisional; calibrate against notebook 09, same as _DROUGHT_REF_MM in chirps.py.
_FLOWERING_MONTHS = {2, 3}
```

Same `drought_risk_score()` / `is_flowering_month()` shape as `chirps.py`, scoped to
Kodagu/India's calendar. `fetch()` returns raw monthly area-mean precipitation
(`FeatureObservation`, asset `climate:chirps:kodagu`) — anomaly/risk derived
downstream, same pattern as Brazil.

### 4.3 FX — `INR=X` via `yfinance` (no new production source for v1)

Reuse `08_producer_fx_signal.ipynb`'s already-validated `yfinance` ticker pattern
directly in notebook 09 — add `"INR": "INR=X"` alongside its existing origin-currency
tickers (BRL, COP, PEN, MXN, GTQ, HNL, NIO, VND, IDR, ETB). Since `price_position`
and climate risk are both currency-invariant, FX isn't needed for the composite math
— only for USD-comparable card framing. Promoting this into a real production
`fx_rates.py` source is a fast-follow, not a v1 blocker.

---

## 5. Feature Engineering

### 5.1 Price features — no new file

`domains/coffee/features/price_features.py`'s `price_position_52w`,
`yoy_price_change`, `price_momentum_12m` already auto-detect daily vs. monthly
frequency and size their window/`min_periods` accordingly — they work directly on an
India price series with **zero code changes**. If Task 0 finds thin history, resample
to monthly before calling them (monthly path needs only ~8 months minimum vs. 176
days on the daily path) — a call-site data-prep choice, not a library change.

### 5.2 Climate risk — no new file, no changes to `climate_features.py`

India has exactly one climate input (Kodagu rainfall), so there's nothing to
weight-combine the way Brazil's four-input `climate_risk_score()` does.
`chirps_india.py`'s own `drought_risk_score()` **is** India's climate risk input
directly — feed it straight into the composite (§7). Adding a pass-through wrapper to
`climate_features.py` would be pure ceremony.

### 5.3 Tests

- `test_chirps_india.py`: mock `_query_monthly_precip` exactly as the existing
  `test_chirps.py` does; cover the Feb-Mar flowering-window logic.
- `test_india_coffee_price.py` (if a real source is implemented): mocked HTTP/parse
  tests per the `implement-source` skill's standard bar (no bare `except:`, 30s
  timeouts, skip-and-log bad rows).

---

## 6. Composite Signal

### 6.1 Prerequisite: implement `build_recommendation()` for real

`core/services/recommendation_engine.py::build_recommendation()` is currently an
unimplemented stub (`...` body). Fill it in per its own docstring — apply
`multiplier = (1.5 - price_position) × (1.0 + 0.65 × climate_risk_score)`, derive
`Action`/`headline`/`rationale`, return a `Recommendation`. Small, self-contained; also
unblocks Brazil's own (equally stubbed) production wiring path.

### 6.2 `domains/coffee/models/signal_generator.py::generate_india_signal()`

Reuses the formula **shape**, not the Brazil-coupled `generate_signal()`/
`climate_risk_score()` functions. India's own weight (`k`) starts from the same
0.65 placeholder as Brazil's, **explicitly not treated as final** until notebook 09
calibrates it — same discipline the Brazil composite already documents in CLAUDE.md.

```python
def generate_india_signal(
    asset_id: str,
    signal_date: date,
    price_position: float,
    climate_risk: float,
    k: float = 0.65,  # placeholder, not yet calibrated for India
) -> Recommendation:
    """India 2-input composite: price_position + single Kodagu climate risk score.
    Same formula shape as generate_signal() (Brazil), fewer/different inputs.
    Additive — generate_signal() itself is untouched.
    """
    return build_recommendation(asset_id, signal_date, price_position, climate_risk)
```

One call per species (India Arabica, India Robusta) — same function, different
`asset_id` and inputs. `confidence` on the resulting `Recommendation` should reflect
Task 0's outcome: lower under the accumulating-validation branch, standard if the
backtest gate passes on adequate history — don't hardcode it.

---

## 7. Backtest — `notebooks/coffee_backtests/09_india_origin_signal.ipynb`

Follow the `backtest-notebook` skill template exactly (Setup → Fetch → QC → Feature
engineering → Correlation vs. price → Pass/fail gate → optional rolling stability →
Summary), same 8-section structure as notebooks 01–08. Cover **both** Arabica and
Robusta, plus the FX leg (§4.3) for USD-comparable framing.

**Gates — set these after Task 0, not before.** If 3+ years of clean data turn up,
aim for something in the neighborhood of the L2a/L3 tier (|r| ≥ 0.20–0.25) — don't
hold India to the L1 bar (r ≥ 0.50) on a much shorter, noisier series with no liquid
futures market backing it. If Task 0 comes back thin (including the WB-benchmark
fallback path), this notebook becomes an exploratory QC pass instead of a gated
backtest, with an explicit **"accumulating validation, N months tracked"** label — the
confirmed framing for this build, not a fallback to avoid.

Update `notebooks/coffee_backtests/README.md` with whatever gate is reached and why —
same transparency standard as the existing signals. (Also fix the existing drift
there: `08_producer_fx_signal.ipynb` is currently missing from `docs/FILE_MAP.md`'s
notebook table — correct that in the same pass.)

---

## 8. API and Card

### 8.1 Route

**No new routes.** `apps/api/routes/coffee.py` already exposes
`GET /coffee/origins/{asset_id}/signal` generically — `coffee:origin:india:arabica`
and `coffee:origin:india:robusta` are covered once the registry entries and a
recommendation source exist behind that route. This is a correction from v2, which
proposed dedicated India routes unnecessarily.

### 8.2 Card copy

Same plain-language narrative style as `generate_signal_text()` in the Math Reference
doc, adapted for India's inputs (Kodagu rainfall deviation, price position, FX where
relevant). Route this copy through the same calibrated-honesty review as the
benchmark — no confident language beyond what the notebook's actual result earned.
Under the accumulating-validation branch, the card must say so explicitly, not imply
a backtest-gated signal it hasn't earned.

---

## 9. Sequence

Single sprint, not a multi-week timeline (corrected from v2's 5-6 week estimate,
which assumed a much larger scope — full production route wiring, DB persistence,
frontend — none of which is this sprint's goal):

1. Task 0 audit (§2), timeboxed ~30-45 min. In parallel: registry additions (§3).
2. `chirps_india.py` (§4.2) with tests.
3. India price source — real (§4.1) or WB-benchmark wiring, per Task 0's verdict.
4. `build_recommendation()` implemented for real + `generate_india_signal()` (§6).
5. Notebook 09 (§7): backtest/demo for both species + FX leg, README updated.
6. Handoff docs: `FILE_MAP.md`, `NEXT_STEPS.md`, `CHANGELOG.md`, and a new CLAUDE.md
   "India Origin Signal" section once the composite/backtest is real.

Frontend/route wiring, DB persistence, and a live discovery call with an India-sourcing
roaster remain explicitly out of scope for this sprint — they follow once the signal
itself is real and reviewed, same gating v2 already argued for.

---

## 10. Go/No-Go Before Promotion

Do not use this in outreach materials or discovery calls as a finished, backtest-gated
signal until:

- [x] Task 0 audit complete and documented — WB-benchmark fallback triggered (Coffee
      Board of India unreachable, mirror has no archive, ICO request-gated); see
      `notebooks/coffee_data_validation/india_price_history_audit.ipynb`
- [x] Notebook 09 run — **gate FAILED for both species** (Arabica r=−0.214, Robusta
      r=+0.132, both vs +0.30 bar, n=16). The accumulating-validation branch is the
      operative one, not by choice but because the gate didn't pass — see notebook
      09 §8 for why this is an expected result of the proxy price limitation, not a
      methodology bug
- [ ] Card copy reviewed against the calibrated-honesty standard in the Math
      Reference doc — draft exists in notebook 09 §7/§8 (headline/rationale via
      `generate_india_signal`, confidence=0.4), full roaster-facing copy review
      still pending
- [ ] At least one real discovery call using the live card, not a mockup, before
      wider promotion

**Demo usage in the meantime:** the composite is real and runs live (see notebook 09
§7 for the current signal) — it's suitable for showing *product mechanics and UI
shape* to stakeholders, explicitly **not** as a validated India timing signal. Any
demo must state plainly that India pricing is tracked via the global benchmark
pending a genuine India-origin price source, and that this composite has not cleared
its own backtest gate.

**What would change this:** a genuine India-origin price series (re-run Task 0 if
Coffee Board of India becomes reachable, a partner roaster shares purchase history,
or a paid vendor is evaluated), then re-run notebook 09 against it. The FAIL is not
fixable by more history or a different window — Kodagu already has 18+ years of
clean climate data; the issue is specifically that the current price leg has no
structural reason to respond to Kodagu-specific rainfall.

---

## 12. v2.2 update — a real India-origin price source was found (2026-07-22)

Everything above (§1–§11) is the v2.1 record: real work, but built on a
conclusion that turned out to be an avoidable mistake, not a genuine dead end.
Told explicitly to fix Task 0 properly — not to settle for a proxy, and not to
self-impose artificial timelines — a second, unhurried pass found the real thing.
This section is the authoritative current state; §1–§11's price-source and
gate-result claims are superseded by what follows.

### 12.1 What was actually wrong with the v2.1 audit

**`indiacoffee.org` was simply the wrong domain.** Coffee Board of India's real,
live site is **`coffeeboard.gov.in`** — reachable, current, and rich. This was
found via a broader web search (checking the Coffee Board's official Ministry of
Commerce listing) rather than assuming the first plausible URL was the only one
to try. The v2.1 audit's *methodology* (check a plausible URL, a mirror, ICO,
within a timebox) was reasonable; the miss was not trying one more domain.

### 12.2 What `coffeeboard.gov.in` actually has

- **Daily Market Report Archive** (`Market_Info_Archives.aspx`) — a stateful
  ASP.NET WebForms flow (not a simple URL: page → postback → year/month grid →
  postback → day list → postback → that day's PDF, served inline as the POST
  response). Reverse-engineered by replaying the flow with `requests.Session()`
  and cross-checking against a live browser click-through. Archive listing goes
  back to 2012; each daily PDF contains, among other things, a genuine
  India-origin **"Raw Coffee Price (Karnataka)"** table (Arabica/Robusta,
  Parchment/Cherry, ₹/50kg, as a low-high range) plus ICTA grade-level auction
  prices, the day's USD/INR rate, and cumulative export volumes (the latter two
  not parsed in this pass — documented scope, not an oversight; see
  `coffee_board_india_price.py`'s docstring).
- **Semiannual "Database on Coffee" PDF circular** (`database-coffee.html`) — a
  simple static listing, ~62 PDFs back to Jan 2009, each a ~60-120 page
  statistical report. Contains district + national **production estimates**
  (Section "Production of Coffee in Major States/Districts") — the India-specific
  supply signal v2.1 (and the original v1) had proposed and then dropped.

### 12.3 An honest discovery about the price data's real cadence

Despite being published in *daily* bulletins, the "Raw Coffee Price" figure only
actually **updates about weekly** in practice — confirmed directly by observing
the identical value repeated across several consecutive archived days, not
assumed. `coffee_board_india_price.py` anchors each observation to the table's
own "as on" date (not the report's nominal date), so this collapses correctly
into one observation per real update rather than manufacturing fake daily noise.
Real density starts in **2014** — 2012/2013 predate the table's consistent
presence in the archive and yield almost nothing (0 and 4 raw rows respectively).

### 12.4 What was built

- **`domains/coffee/sources/coffee_board_india_price.py`** — the ASP.NET
  scraper described above. Paced deliberately (2s between requests — a small
  government server, not a CDN) and resumable (the backfill driver writes one
  year at a time). Mocked test suite, 16 tests, passing.
- **`domains/coffee/sources/coffee_board_india_supply.py`** — parses the
  semiannual Database PDF's production table with `pdfplumber.extract_tables()`
  (a clean structured grid, verified directly — no text-position heuristics
  needed, unlike `usda_coffee_wmt.py`'s PDF). Vintage-aware like
  `usda_coffee_wmt.py`: each report's own newest marketing-year column is used,
  not a some-other-report's-later-revision. Mocked test suite, 19 tests, passing.
- **`INDIA_PRODUCTION`** asset added to `assets.py`; `INDIA_ARABICA`/
  `INDIA_ROBUSTA` metadata updated to point at the real source instead of the WB
  proxy claim; unit changed from a placeholder `"lb"` to `"inr_per_50kg"` (the
  real source's native unit — `price_position_52w` is a relative measure, so this
  doesn't affect correctness, just accuracy of the label).
- **Full historical backfill run**: 9,217 raw price observations (2012-2026,
  dense from 2014), 1,289 supply observations (2010-2024, one PARTIAL run from
  two failed reports — a genuine site typo in one PDF's link and one transient
  network error, both immaterial). Cached to
  `notebooks/coffee_backtests/data/coffee_board_india_daily_raw.csv` and
  `coffee_board_india_supply.csv` (mirrors this repo's "Save Reference CSV"
  convention).
- **`notebooks/coffee_backtests/09_india_origin_signal.ipynb` rebuilt entirely**
  on this real data, plus the species-specific climate windows (§13 below).

### 12.5 The honest final result: gate still FAILS, but now a real, diagnosed result

With genuine India-origin price data (not a proxy), the annual r ≥ +0.30 gate
**still fails for both species** — and this time it was diagnosed, not just
reported:

- **Robusta: r=−0.357 at 12m (n=12)** — wrong-signed, and stays wrong-signed at
  every tested horizon from 3 to 24 months (range −0.36 to −0.09, checked via a
  lag sweep). This is not a borderline miss on noisy real data — the specific
  hypothesis (Kodagu blossom-window rainfall deficit predicts forward Robusta
  price) is not supported.
- **Arabica: r=−0.038 at 12m (n=12)** — much closer to zero than the wrong-signed
  −0.214 v2.1 got on the WB proxy, and **turns positive at longer horizons**
  (18m: +0.076, 24m: +0.179 — the right sign, echoing L1's own 24m
  mean-reversion finding elsewhere in this repo) but still short of +0.30.
- **Supply (production YoY) vs forward-6m price: r=−0.110, p=0.564, n=30** — no
  standalone relationship.
- **Sanity check passes cleanly**: `price_position_52w`'s BUY-zone-average <
  ALL-average < CAUTION-zone-average monotonicity holds for both species on the
  real price series — the price data and feature engineering are sound; it's
  specifically the climate/supply-to-price mechanism under test that doesn't
  clear its gate.

This is reported as a real result, not re-run or reframed until it passed. See
notebook 09 §6 for the full diagnostic writeup and plausible (unconfirmed)
explanations — thin annual sample (n=12), Kodagu-only vs. a production-weighted
multi-district climate signal, and India price possibly being dominated by
factors (global pass-through, currency, domestic policy) this composite doesn't
model.

### 12.6 Species-specific flowering windows (also fixed this pass)

v2.1's `chirps_india.py` used one Feb-Mar blossom window for both species —
verified against real agronomy sources to be wrong for Arabica. Corrected:
**Robusta** blossoms via pre-monsoon showers late Feb-mid Mar (`_FLOWERING_MONTHS_BY_SPECIES["robusta"] = {2, 3}`);
**Arabica** needs rain by mid-April, roughly a month or two later
(`_FLOWERING_MONTHS_BY_SPECIES["arabica"] = {4, 5}`). Both need a "backing
shower" ~2 weeks after the initial blossom for cherries to set.
`is_flowering_month(month, species)` now requires the species explicitly rather
than defaulting silently to one or the other.

### 12.7 Two live bugs found and fixed along the way (not India-specific in cause)

- **`world_bank_commodity.py`**: World Bank dropped the machine-code header row
  from the Pink Sheet Excel in a 2026-07-02 update, silently breaking the live
  fetch (mocked tests didn't catch it — they encode the assumed structure
  directly). Fixed to locate header/data rows dynamically. Found while checking
  whether the WB proxy fallback was still viable — became moot once the real
  source was found, but the fix stands as a real production bug fix.
- **`chirps_india.py`**: GEE's `Dictionary.get(key, default)` still raises if
  `default=None` ("unless it is null," per GEE's own docs) — only surfaces when
  fetching up to `date.today()` (months with no CHIRPS coverage yet). Fixed with
  a real sentinel value.

### 12.8 Status and next steps

- [x] Real India-origin price source found and implemented
- [x] Real India-specific supply source found and implemented
- [x] Species-specific climate flowering windows corrected
- [x] Full historical backfill run (paced, respectful of the government server)
- [x] Notebook 09 rebuilt on real data, with lag-sweep and sanity-check
      diagnostics before concluding — **gate FAILS honestly, both species**
- [x] Production-weighted multi-district climate signal — **tried, see §13.1;
      does not rescue the gate**
- [x] Arabica 24m-horizon hint robustness check — **tried, see §13.2;
      the hint does not survive scrutiny**
- [ ] Card copy / calibrated-honesty review still pending — and now has an even
      clearer message to convey: real India-origin data, mechanically sound
      infrastructure, composite formula validated in shape but not in its
      specific climate input — demo-appropriate, not yet roaster-promotion-ready

## 13. v2.3 update — both flagged follow-up experiments closed out (2026-07-22, same day)

The two "not yet tried" items from §12.8 were both implemented and run to
completion in the same session. Neither rescues the composite; both are
reported as real negative results, not reframed or re-run until they passed.

### 13.1 Experiment 1 — production-weighted multi-district climate signal

`chirps_india.py` was extended from Kodagu-only to a `district` parameter
(Kodagu, Chikmagalur, Hassan — Karnataka's three largest coffee districts by
production; GAUL's own spelling is "Chikmagalur," differing from Coffee
Board's "Chikkamagaluru" — see §13.3's alias fix). Each district's flowering
SPI-3 deficit was weighted by its share of combined production (52% / 33% /
14%, from `coffee_board_india_supply.py`'s own district data) into a single
weighted signal, and the same annual-r gate test was re-run.

**Result: does not rescue the signal.** Robusta improves marginally
(r=−0.357 → −0.285) but stays wrong-signed and FAILS; Arabica moves closer to
zero (r=−0.038 → −0.016) and FAILS. Directionally, broadening beyond Kodagu
alone made Robusta marginally *less* wrong — weak evidence against "wrong
district" as the primary cause of the FAIL. The climate mechanism itself, not
the specific district chosen, looks like the bigger issue.

### 13.2 Experiment 2 — robustness check on the Arabica 24m hint

The lag sweep in §12.5 found Arabica turns positive at 24m (r=+0.179) — right
sign, but n=12 is thin. Two standard robustness checks (same discipline
notebook 05 applied to L3's SPI-3 result before trusting it):

- **Leave-one-out**: r ranges **[−0.065, +0.395]** across the 12
  single-year-excluded refits — the sign itself flips depending on which one
  year is held out.
- **Bootstrap** (5,000 resamples, 90% CI): **[−0.356, +0.622]** — comfortably
  spans both zero and the +0.30 gate.

**Conclusion: the 24m hint was noise, not a real weak effect.** This resolves
the ambiguity §12.5 left open ("worth revisiting") — at n=12 this specific
point estimate carries almost no statistical information, and only genuinely
new years of price history (not cleverer analysis of the same 12 points) can
move it. See notebook 09 §4d for the full computation.

### 13.3 A real data-quality bug found and fixed: district name spelling drift

`coffee_board_india_supply.py`'s district rows split into duplicate series for
the same real-world district because PDF editions spell district names
differently across the years (e.g. "Chikkamagaluru" in 2024 editions vs.
"Chikmagalur" in 2013 editions; also "Nilliampathy"/"Nelliampathies",
"Wyanad"/"Wayanad", and "Orissa"/"Odisha" — the last a genuine 2011 state
rename, same entity). Fixed with a `_REGION_ALIASES` map applied inside
`_region_slug()`. Deliberately did **not** merge "Andhra Pradesh" with
"Andhra Pradesh & Orissa" — older editions genuinely combine two states into
one row, a structural difference, not a spelling variant; merging would
silently conflate a two-state figure with a one-state one. 4 new tests lock
this in (`tests/domains/coffee/test_coffee_board_india_supply.py::TestRegionSlug`).

### 13.4 A real external incident: `coffeeboard.gov.in` TLS certificate expiry and a caching-script data-loss mistake

Mid-session, a re-fetch of the full 62-report supply backfill (to pick up the
§13.3 alias fix across the whole history) failed with
`[SSL: CERTIFICATE_VERIFY_FAILED] certificate has expired`. Direct inspection
(`openssl s_client` against the live cert) confirmed `notAfter=Jul 22 23:59:59
2026 GMT` — the certificate expires the same day as this session, a real,
external, dated event, not a bug in this repo. Both HTTPS and plain HTTP
access failed, indicating a broader outage on Coffee Board's side.

**A real mistake compounded this**: the caching script that ran the re-fetch
wrote its (empty, failed) result to the same path as the previously-good CSV
without checking `run.status` first, destroying the original
1,289-observation, 62-report dataset (git-untracked, unrecoverable via git).

**What was explicitly *not* done to route around it**: bypassing SSL
certificate verification to force the fetch through. That would trade a
data-loss problem for a MITM/data-integrity risk on a source this signal
partly depends on for supply data — not an appropriate substitute for "wait
for their IT team to renew the cert."

**Recovery taken instead**: 4 PDF editions (2013-01, 2016-07, 2022-01,
2024-07) still cached locally from earlier exploration were re-parsed with
the corrected `_region_slug()`, rebuilding a reduced 168-observation supply
CSV — enough for §13.1's district *production weights* (a fixed snapshot
suffices for that) but not enough to redo the original national YoY
supply-vs-price test with its original statistical power. **A full
re-backfill of all 62 reports is still needed once `coffeeboard.gov.in` is
reachable again** — this is a genuine open, external, currently-blocked item,
not resolved in this session.

### 13.5 Status and next steps (supersedes §12.8's open items)

- [x] Production-weighted multi-district experiment — closed, negative result
- [x] Arabica 24m robustness check — closed, negative result (noise)
- [x] District name spelling-drift bug — found and fixed, tested
- [ ] **Blocked on an external dependency**: full 62-report supply backfill
      re-run, once `coffeeboard.gov.in`'s TLS certificate is renewed and the
      site is reachable again — restores the 1,289-observation dataset and
      full statistical power for the national YoY supply test
- [x] Whether India price is dominated by factors this composite doesn't model
      (global pass-through, currency) — **tested directly, see §14: yes,
      overwhelmingly**
- [ ] What remains genuinely untested even after §14: (a) discrete
      regulatory/policy shocks (EUDR compliance deadline, India-EFTA duty
      changes) as event-study step dummies, and (b) a fundamentally different
      climate construction (harvest-window Nov-Feb rainfall — berry drop /
      fungal disease during an already-picked-or-picking crop — rather than a
      blossom-window SPI-3 anchor)
- [ ] Card copy / calibrated-honesty review still pending (carried over from
      §12.8) — now has a materially different message to convey per §14: a
      validated India signal looks like global-price-plus-FX, not a
      local-climate timing signal

## 14. v2.4 update — global pass-through + FX decomposition (2026-07-28)

External review of notebook 09's climate-gate FAIL (both species, plus both
§13 experiments) offered a structural diagnosis rather than another
climate-construction tweak: **India produces roughly 3.5% of world coffee and
exports most of what it grows — it is a price taker, not a price setter.** A
Kodagu rainfall deficit is not big enough to move the world price on its own,
so the causal arrow should mostly run from the global benchmark and USD/INR
into India's domestic price, not from local weather into price. This was
exactly the "genuinely untested" item flagged in §13.5 — tested directly here.

### 14.1 Method

Notebook 09 §6-7 (new sections, inserted before the composite demo, which
renumbered from §5→§8; the old §6 Summary renumbered to §9). Reused existing
infrastructure rather than building new production sources: the global
benchmark is notebook 07's already-cached World Bank Pink Sheet series
(`data/wb_arabica_monthly.csv` / `wb_robusta_monthly.csv`, monthly, 2000-2025);
USD/INR is `yfinance`'s `INR=X`, using notebook 08's exact already-validated
fetch call (that notebook's own `ORIGIN_FX` ticker list doesn't include INR,
but the pattern needed no modification). Model: `log(india_price) ~
log(global_price) + log(usd_inr)`, OLS with a constant, per species — log-log
rather than plain levels, since FX pass-through is multiplicative (a weaker
rupee scales the INR value of a fixed USD price) and log coefficients read
directly as elasticities.

### 14.2 Result: pass-through explains the overwhelming majority of variance

| Species | R² | global_price coef | usd_inr coef | n |
|---|---|---|---|---|
| Robusta | **0.887** | +0.789 (p<0.001) | +1.206 (p<0.001) | 144 |
| Arabica | **0.962** | +0.937 (p<0.001) | +0.947 (p<0.001) | 144 |

Both FX coefficients are positive as expected (rupee depreciation raises the
INR-denominated domestic price) and both variables are highly significant for
both species. This is not a partial or marginal explanation — global
pass-through plus FX accounts for 89-96% of the variance in India's domestic
coffee price. The external review's diagnosis was correct, and decisively so.

### 14.3 Residual re-test: climate still doesn't explain what's left over — and for Robusta, in a genuinely surprising direction

Re-ran the same flowering-SPI-3-deficit gate (≥ +0.30 annual r, same lag sweep
as §4b) against the pass-through **residual** instead of raw price — the
~4-11% of variance the regression doesn't already explain. Required one
genuine adjustment from a literal reuse of §3's helpers: the residual is a
signed log-quantity that crosses zero, so `fwd12_from_month`'s percent-change
transform is not meaningful on it (division near zero, ratio sign doesn't mean
what it means for a price level); added a small parallel helper
(`fwd_change_from_month`) that takes an additive forward difference instead,
appropriate for a signed residual. `fwd12_from_month` and
`fwd_from_month_at_lag` themselves are untouched.

- **Robusta: r=−0.587 (p=0.045, n=12) — FAIL, and notably *more* significant
  and *more* wrong-signed than the raw-price test (r=−0.357, p=0.254).** The
  lag sweep confirms this isn't a one-horizon artifact — residual r stays
  negative from 6-24m, deepening to −0.502 to −0.587 in the 12-24m band. Read
  plainly: a *wetter*, not drier, flowering season associates with a *higher*
  pass-through-adjusted Robusta price 12-24 months later. This is a genuinely
  surprising result, reported as such — it argues against "the residual
  history is just too short" and toward "this specific climate construction
  doesn't capture the right mechanism for Robusta," a materially different
  conclusion than an inconclusive null result.
- **Arabica: r=+0.033 (p=0.918, n=12) — FAIL, indistinguishable from zero.**
  The lag sweep is noisy with no consistent direction (−0.495 to +0.426),
  consistent with "no real signal" rather than "signal at the wrong horizon."

### 14.4 What this changes

- **Does not mean the pipeline is broken** — if anything it's further
  confirmation the India price series is clean: pass-through regressions this
  clean (R²>0.88, all coefficients correctly signed and highly significant) on
  real-world data are themselves a strong data-quality signal.
- **Resolves, rather than deepens, the open question §13.5 left standing.**
  Three concrete tests (multi-district weighting, the Arabica 24m hint, and
  now global pass-through) all point the same direction: India's domestic
  coffee price is overwhelmingly a global-price-plus-FX phenomenon, and local
  flowering-season Karnataka rainfall is not a meaningful independent driver of
  it at this sample size.
- **Product-narrative implication, not yet acted on:** a validated "India
  signal" is far more accurately framed as *global price + FX pass-through*,
  with local climate/supply data serving descriptive/context copy rather than
  a local-weather timing mechanism — a materially different product concept
  than `generate_india_signal()`'s current 2-input (price-position +
  climate-risk) composite. This should inform the still-pending card-copy
  review (§13.5), not something resolved by this analysis alone.
- **Two items remain genuinely untested, deliberately out of scope for this
  pass** (larger scope than the pass-through test, each deserving its own
  dedicated pass rather than being bundled in): discrete regulatory/policy
  shocks (EUDR compliance deadline, India-EFTA duty changes) as event-study
  step dummies rather than continuous features; and harvest-window (Nov-Feb,
  not flowering-window) rainfall as a structurally different climate pathway
  (berry drop / fungal disease during an already-picked-or-picking crop).

## 15. Validating the global composite's *forecasting* transferability to India — RUN, FAIL

External review of §14 flagged a precise gap between what's proven and what a
"translate the global signal into an India signal" product would need: §14's
R²=0.887/0.962 is a **contemporaneous** relationship — India price and (global
price + FX) move together *at the same time*. The global composite's actual
job is **forecasting** — using current stocks-to-use/ENSO/rainfall/positioning
to flag that price is likely under/overpriced relative to fundamentals. Those
are different claims, and §14 only tested the first one.

**The concrete test, once it's unblocked:** the global (Brazil) composite's
own production wiring is still pending (`CLAUDE.md` Build Sequence step 5 —
`build_recommendation`'s formula/weights need to move from notebook-06-derived
constants into the production feature files first). Once that composite
produces a real forward-looking multiplier/recommendation at each historical
point, translate it through the §14 pass-through equation
(`india_price_predicted = global_price_predicted^0.937 × fx^0.947` for
Arabica, using that species' own elasticities) and correlate the translated
forecast against forward India price changes, gated the same way the original
composite was gated against forward global price changes. If it holds, the
transfer is validated for real, not just assumed from the contemporaneous fit.
If it doesn't, that's a genuinely useful finding in its own right — it would
mean India price *levels* track global+FX closely but India price *timing/
momentum* moves differently (adjustment lags, sticky domestic pricing), a
real and distinct phenomenon commodity pass-through can have.

**Scope this to Arabica first, deliberately.** Arabica's pass-through residual
(3.8% unexplained) is less than half of Robusta's (11.3%) — and that extra
unexplained room in Robusta is exactly where §14's wrong-signed-but-real-
looking climate residual result (r=−0.587, p=0.045) showed up. Arabica is
closer to a pure pass-through story; a straight translation is safer and
cleaner to validate there first, with Robusta's "something else going on"
treated as a separate, harder problem rather than assumed away.

**Not free even if the test passes — FX becomes a first-class product
variable, not something folded silently into "the coffee story."** The
usd_inr elasticity (0.947) nearly matches the coffee elasticity itself — a
meaningful share of any future India price move would be rupee strength
(RBI policy, capital flows, US rate decisions), which has nothing to do with
coffee. A translated India signal needs an explicit view on FX (or an honest
"we don't have a view on this, flagged separately" stance), not an implicit
one.

**Also raises an unresolved product-definition question, worth deciding
explicitly before or alongside this test:** who is the India roaster customer?
- An India-based roaster paying in rupees for domestically-auctioned lots —
  for them, the FX component is directly actionable (a weakening rupee is a
  real cost signal even with flat global coffee prices).
- A US/EU roaster sourcing India-origin lots through a USD-pricing importer —
  for them, FX pass-through mostly washes out (already absorbed into the
  quoted USD price), and what matters is closer to the raw global signal plus
  India-specific quality/availability risk (the yield/disease angle from the
  climate work, not the price-pass-through angle).

These are two different products under one "India signal" label. Worth
deciding which one (or both, clearly separated) is being built for, rather
than defaulting to one implicitly.

**Why this matters beyond India, if it validates:** the architecture
implication is bigger than "less work for one origin" — it would mean the
product doesn't need N independently-backtested composites per origin
(coffee's other origins, or cacao per the expansion path), just one
well-validated global composite plus a lightweight per-origin translation
layer (a pass-through elasticity, an explicit FX view, a short list of known
event risks like EUDR flagged separately). The three "failed" India climate
experiments (§13, §14) aren't wasted effort toward that — they're what ruled
out "local weather is the story" and correctly landed on "pass-through plus
FX is the story," which is the piece that actually generalizes.

**Status: RUN — FAIL, decisively and reportably.** The global composite's
production wiring (`CLAUDE.md` Build Sequence step 5) landed
(true-vintage L2a rebuild, finalized weights, `classify_normalized()`
rolling-24m normalization), unblocking this test. Notebook 09 §10:
**r(Brazil composite normalized_mult, fwd-12m India Arabica price) = −0.250**
(p=0.005, n=127, 2014-06 to 2024-12), wrong-signed against the +0.30 gate —
BUY months averaged −0.38% forward India price vs +17.71% for NEUTRAL and
+14.51% for CAUTION. An FX-adjusted version (isolating the coffee-only
story from FX, answering the customer-definition question above
empirically) gives nearly the same result (r=−0.235, p=0.008) — this is not
primarily an FX-noise artifact masking a real coffee-timing signal.

**Read plainly against §14, not smoothed over:** §14 proved India price
*levels* move with global price + FX at the same time — that finding is
untouched. This test proves that contemporaneous relationship does **not**
mean the global composite's forward-looking BUY/CAUTION regime carries
forecasting power for India price specifically. Likely explanation:
adjustment lags or sticky domestic pricing at the India-origin level,
decoupling *when* India price moves from what the level relationship alone
would suggest — a real, distinct phenomenon, not a contradiction.

**Product implication:** the "one global composite, translated per-origin"
architecture this section flagged as the bigger prize does **not** hold for
India via this route. A validated India timing signal, if one exists, needs
its own independently-validated forecasting relationship — not a straight
translation of Brazil's regime through the pass-through equation. This
narrows what's still open (the India-customer-definition question above
remains genuinely unresolved) rather than closing the India workstream
entirely.

---

*GreenSignal · India Origin Signal — Full Build Plan v2.6 · §15 run to
completion (2026-08-04): the forecast-transferability test FAILS, decisively
and wrong-signed (r=−0.250, p=0.005) — India price levels track
global-plus-FX (§14, unchanged) but the global composite's timing regime
does not transfer to India price. Rules out the global-composite-translation
route to an India timing signal specifically, narrows rather than closes the
open questions §15 raised; §14 tests and confirms external review's
global-pass-through-plus-FX diagnosis of the climate gate's FAIL
(2026-07-28); §13 closes out both follow-up experiments flagged in §12.8 and
documents a district-alias bug fix plus an external TLS/data-loss incident
(2026-07-22, same day as v2.2); §12 supersedes §1-11's price-source and
gate-result claims (2026-07-22); v2.1 corrected v2 against repo state
(2026-07-21); v2 itself superseded v1 (`india_origin_signal_plan.md`).*
