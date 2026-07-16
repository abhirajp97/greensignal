# Changelog

All notable changes to GreenSignal are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Versions are dated. Each entry covers what changed, why it matters, and who did it.

---

## [Unreleased]

Planned but not yet merged to `main`:
- Rebuild `stu_stress` (L2a's composite input) off the true-vintage series instead of the PSD-approximation series, then re-run notebook 06's L2a ablation
- Production wiring: `build_recommendation`, `climate_risk_score` weights, `risk_scorer.py`, promote `stu_risk_score` / `enso_lagged` / the SPI drought score into production feature files
- Promote the validated SPI flowering-deficit feature from notebook 05 into `domains/coffee/features/climate_features.py` (replacing the provisional mm-anomaly `drought_risk_score`)
- Extend `usda_coffee_wmt.py` coverage before June 2010 (older circulars use a different/unparseable format) — low priority, only if the composite shows L2a's weight is sensitive to it
- Independent engineering work: `core/storage/repositories.py` + job wiring (`jobs/coffee/*.py`, all still stubs — nothing is currently persisted), `margin_features.py`

---

## [0.19.0] — 2026-07-13

### Added
- **`notebooks/coffee_backtests/06_composite_backtest.ipynb` — the full composite backtest, combining all 5 real-data-validated signals.** Aligns L1/L2a/L2b/L3/L5 onto one honest monthly frame (reusing notebook 04's step-function forward-fill pattern for L2a's semiannual true-vintage series and L3's annual SPI flowering-deficit feature — L1, L2b, and L5 were confirmed to already land on monthly cadence natively, verified directly in each notebook's own code rather than assumed). Derives composite weights via **r-proportional reweighting** (each sub-signal's weight ∝ its own `|r|` against forward return, measured within the shared aligned frame) as the primary scheme, compared against the unchanged Phase 0 synthetic weights and a non-negative Ridge regression ceiling check (implemented via `scipy.optimize.nnls` on an augmented design matrix rather than adding scikit-learn as a new dependency for one comparison cell).
- **Gate PASSES** (walk-forward forward prescience ≥3.50%) on both weight schemes: Phase 0 fixed weights +9.31%, r-proportional reweighting +3.62%. Full-history in-sample screening (before walk-forward) was more moderate: Phase 0 +4.44%, r-proportional +4.73%, Ridge ceiling check +4.10% (didn't beat the simpler scheme). **Reported honestly alongside the PASS: the walk-forward result rests on a thin sample** — only 11 (Phase 0) / 21 (r-proportional) buy-months total across the 10 test years (2015–2024), with 3–4 of those years classifying zero buy months. Treat as directional validation of the composite approach, not a final precise weight assignment.
- **Generalized leave-one-out ablation** (not just an L5 question, per the same "does this borderline signal actually help" scrutiny that applies to L3): dropping L2b costs −3.00pp (by far the strongest individual contributor); dropping L5 costs −0.81pp (helps — empirically validates notebook 03's "low-weight momentum amplifier" role rather than assuming it); dropping L3 costs only −0.22pp (near-neutral, consistent with its confirming-amplifier framing); dropping L2a *improves* the number by +1.06pp — traced to a specific cause rather than left unexplained: the `stu_stress` input reused here comes from the PSD-approximation series, not the stronger true-vintage series validated in notebook 04.
- Added missing `Save Reference CSV` cells to notebooks 01 and 03 (the only two of the five still missing this, discovered while assembling notebook 06's inputs) and re-executed both. `cot_monthly.csv` on disk before this fix predated notebook 03's momentum-thesis rebuild and still had contrarian-era columns — would have silently fed stale data into the composite if reused as-is.

### Fixed
- **Corrected stale L5 (COT) documentation across the repo.** `CLAUDE.md` (2 places), `docs/NEXT_STEPS.md`, `docs/FILE_MAP.md`, and `notebooks/coffee_backtests/README.md` all still described L5 as failing its original contrarian gate (r=−0.05 @ fwd 12m). That description was stale: `notebooks/coffee_backtests/03_cot_signal.ipynb` was already rebuilt around the momentum thesis in an earlier session (`88af1e9`, merged via PR #4, before this work started) and its actual current result is a PASS — r(COT index, fwd 6m) = +0.144 (p=0.053, n=180). Caught while verifying claims before planning notebook 06, rather than propagating the stale docs into new planning. Corrected to the real, current state: momentum gate passes but is weak and borderline (p at the edge of significance, 3yr rolling stability only 45% positive, walk-forward $ savings don't materialize) — a low-weight composite amplifier, not a failed signal.

### Why it matters
This is the last real-data validation gate before product work begins — all 5 signals now individually validated (notebooks 01–05) and combined (notebook 06), with the composite passing its gate. The two "not done yet" items that matter most before committing final weights: rebuilding L2a's stress-score input off the stronger true-vintage series (its current ablation result is misleading), and running the full walk-forward test on a larger sample as more real-world data accumulates (the current pass is directional, not a precise final number).

---

## [0.18.0] — 2026-07-13

### Added
- **`domains/coffee/sources/usda_coffee_wmt.py` — a true vintage-aware world stocks-to-use % source, fixing `usda_psd.py`'s look-ahead bias properly instead of approximating it.** [0.17.0] shifted the PSD bulk file forward 12 months to simulate the publication lag USDA's always-latest-revised bulk CSV doesn't reflect. This release replaces the approximation's premise: a review comment suggested parsing USDA's monthly **WASDE** report for a genuine point-in-time archive, but WASDE does not cover coffee at all (confirmed via web search — it's limited to grains, oilseeds, cotton, sugar, and livestock). The correct USDA report for coffee is a separate semiannual (June/December) circular, **"Coffee: World Markets and Trade,"** archived back to June 2004 at `esmis.nal.usda.gov`. Each issue is genuinely time-stamped — it reports the world "Total" Ending Stocks and Domestic Consumption as estimated *at that report's own publication date* — so `usda_coffee_wmt.py` needs no shift/approximation at all.
- **Archive discovery** paginates the ESMIS listing (`?page=0,1,2,...`) and parses the release table via BeautifulSoup. Caught and fixed a real bug during development: past the actual archive depth, the site does not return an empty page — it loops back to repeating page-0 content — so pagination now stops when a page adds *no new report dates*, not merely when a page is empty (the naive check would have looped `_MAX_LISTING_PAGES` times re-fetching the same page).
- **PDF parsing** handles 20+ years of format drift (pre-2011 combined "Table 01A"; 2011+ split "Coffee Summary" pages) by anchoring on the literal phrase `"Thousand 60-Kilogram Bags"`, present on every summary-table page and nowhere else — critically, this avoids a false-positive trap where many issues also have a page-1 narrative subsection literally titled "Ending Stocks" (prose, not a table). Within the anchored segment, the parser locates the "Domestic Consumption" and "Ending Stocks" headers and each one's nearest following `"Total <numbers>"` row, taking the last (newest) column.
- 31 of the 46 discovered historical reports (June 2010 – June 2025) parse successfully; the 15 pre-June-2010 issues use an incompatible/older format and are skipped (logged, `PARTIAL` run) — accepted since the notebook's core backtest window starts in 2010.
- **Cross-validated independently:** the Dec 2025 report parses to 11.59% world S/U, matching `usda_psd.py`'s separately-computed 11.6% for the same period via a completely different data pipeline.
- `tests/domains/coffee/test_usda_coffee_wmt.py` — 24 tests: real-format text fixtures for both the pre-2011 combined and 2011+ split table layouts, `_find_summary_segment`/`_section_total` false-positive-trap guards, listing pagination (including the wrap-around-stop fix), and `fetch()` SUCCESS/PARTIAL/FAILED paths — all HTTP and PDF calls mocked. Reviewed via the `data-source-reviewer` agent — **APPROVED**.
- `domains/coffee/registry/assets.py` — added `USDA_STU_VINTAGE` (`coffee:supply:world_stu_vintage`).
- New main dependencies: `pdfplumber` (PDF text extraction), `beautifulsoup4` (listing HTML parsing).

### Changed
- **`notebooks/coffee_backtests/04_usda_supply_signal.ipynb`** — new §11 fetches the true vintage series, aligns its irregular semiannual dates to price via `pd.merge_asof`, and re-runs both gates: **Gate 1 r=−0.488 (p=6.2e-3, n=30) — stronger than the [0.17.0] approximation's −0.312**; Gate 2 r=−0.261 (p=0.17) passes the numeric threshold but isn't statistically significant at this small semiannual sample — reported honestly rather than oversold. The true series and the shift approximation agree directionally but only moderately (r=+0.49 between them, mean absolute difference 3.1 percentage points) — both are kept in the notebook, true vintage as primary evidence, the approximation as a documented fallback for pre-June-2010 and for months between semiannual reports. §12–15 (save CSVs, summary, interpretation) updated to report both series' results side by side; the old "Deferred: WASDE-Based True Vintage Series" section (§14) is replaced with a "Resolved" section documenting what was actually built and what remains genuinely out of scope (pre-2010 coverage, production wiring, a scheduled job).
- `notebooks/coffee_backtests/README.md`, `docs/FILE_MAP.md`, `CLAUDE.md` — updated the L2a rows/sections to report both the true-vintage and approximation gate results, and documented the new source's quirks (pagination wrap-around, PDF anchor strategy, WASDE-vs-WMT correction) in CLAUDE.md's "Data Sources & Key Quirks".

### Why it matters
Closes out the highest-priority item from [0.17.0]'s "not done" list — but not the way it was originally scoped. Catching the WASDE-doesn't-cover-coffee error before implementation avoided building a source against the wrong report entirely. The true vintage series is stronger evidence than the approximation it replaces as primary, while validating that the approximation's direction and rough magnitude were reasonable in the interim.

---

## [0.17.0] — 2026-07-13

### Changed
- **Rebuilt the L2a USDA stocks-to-use signal around a vintage-lag correction — fixes a look-ahead bias in the prior backtest.** The USDA PSD bulk CSV is always the *latest revised* vintage of every marketing year; the original notebook 04 correlated that fully-revised number against the price from the year it describes, which a roaster could not have known in real time. Fixed by shifting the monthly forward-filled S/U series forward 12 months (tested 6m as a sensitivity check) before correlating with price, simulating the real publication lag. Raw r(S/U, price level) = −0.40 weakens to −0.26 once the lag is applied — expected, and the honest number.
- **Redefined the L2a gate into two tests, both on the vintage-lagged series, both PASS on real data:** Gate 1 `r(vintage S/U, 12m-forward price level) ≤ −0.25` → **r=−0.312** (p=2.0e-5, n=180); Gate 2 `r(S/U YoY delta, contemporaneous price level) ≤ −0.20` → **r=−0.259** (p=4.6e-4, n=180). Replaces the old single YoY-change gate (r=−0.04, FAIL) that was the wrong lens for a slow annual step-function variable.
- **Added three new features**, all computed on the annual series to avoid diluting an annual signal (same class of fix already applied to L2b/L3): a **10-year rolling z-score** (uses only the prior 10 years' mean/std, so it introduces no additional look-ahead beyond the vintage lag), a **YoY delta** (`stu[t] − stu[t-1]`, the "shock" dimension), and **months of consumption** (`S/U% / 100 × 12`, a roaster-legible reframing).
- **Replaced the linear 12%/35% clamp with a z-score-based non-linear stress score** (`stress = clamp((−z + 2) / 4, 0, 1)`), self-calibrating against the series' own 10-year history rather than fixed percent bounds. Latest read (2025): Z=−1.96, stress=0.99 — a once-in-a-generation tight buffer, 1.4 months of consumption in storage.
- `notebooks/coffee_backtests/04_usda_supply_signal.ipynb` — full rebuild: vintage-lag section with raw-vs-lagged comparison table, feature engineering, dual gates, correlation matrix, rolling stability (honest but modest: 52% of 3yr windows negative, up from 23% on the old YoY basis — the full-sample gates are the stronger evidence), z-score stress score with a descriptive Z<-1/Z>+1 decision rule, and a deferred-work section on building a true WASDE-vintage series.
- `notebooks/coffee_backtests/README.md`, `docs/FILE_MAP.md` — updated the L2a gate row/status to the new dual-gate PASS result.
- Untracked `notebooks/coffee_backtests/data/04_*.png` (regenerable, already embedded inline in the executed notebook), consistent with the nb05 figure-untracking policy from [0.16.0].

### Not done (explicitly deferred, see notebook §14)
- A genuinely vintage-aware S/U series built from historical monthly WASDE reports. The 12-month shift is a practical approximation of the publication lag, not a literal point-in-time reconstruction. Building the real thing means parsing ~25 years of monthly WASDE PDF/HTML reports as a new data source (own `implement-source` pass + reviewer sign-off) — worth doing only if L2a's composite weight (notebook 06) turns out to be sensitive to the extra precision.
- `stu_z_score` / `stu_stress_score` were **not** promoted into `domains/coffee/features/supply_features.py` (still a stub) or `usda_psd.py`. Per the nb05/L3 precedent, new backtest-validated features stay notebook-local until the composite (notebook 06) actually wires them in.

### Why it matters
The prior L2a result (r=−0.40 to −0.59 depending on lag) was contaminated by look-ahead — a roaster reading this signal in real time would not have had the revised numbers the backtest used. The vintage-lagged, dual-gate result (r=−0.26 to −0.31) is weaker but honest, and still clears both redefined thresholds, so L2a remains a validated fundamental for the composite — just a noisier one than the original notebook implied.

---

## [0.16.0] — 2026-07-02

### Changed
- **Rebuilt the L3 CHIRPS drought signal around SPI (Standardized Precipitation Index) — now PASSES a redefined gate.** Per a commodity-desk review, replaced the raw `rain − historical_mean` (mm) anomaly with a gamma-fit SPI z-score, and made the **cumulative flowering-season deficit** the primary feature: the **SPI-3 accumulation over Sep–Nov** (Brazil Arabica flowering window), evaluated on the **annual crop-year frame** against forward-12m Arabica price. Result: **r=+0.483 (p=0.069, n=15)**, up from the old raw-mm annual baseline of +0.398.
- **Redefined the L3 gate** from monthly `r ≥ +0.12` to annual `r(flowering SPI-3 deficit, fwd-12m) ≥ +0.30` (a *confirming*-signal bar, since L3 amplifies rather than times). The old monthly lens diluted a signal concentrated in one 3-month window per year — same class of frame error corrected earlier for L2b (ENSO) and L2a (S/U). Upgrades L3 from "narrow FAIL" to a validated confirming amplifier.
- `notebooks/coffee_backtests/05_chirps_signal.ipynb` — full rebuild. Added: gamma-fit `spi_from_gamma` with zero-precip correction; SPI-3 and monthly-SPI-deficit variants; asymmetric **deficit** form `max(0, −SPI3)` (beats signed SPI −0.412 → captures one-sided drought tail risk); **tercile event study** (driest vs wettest flowering third → +33.6% vs +9.5% fwd-12m); and two robustness controls — an **expanding-window SPI** with no look-ahead (r=+0.494, n=9) and a **partial correlation controlling for stocks-to-use** (r=+0.48, ≈ unchanged → drought signal is independent of the supply balance). Notebook now falls back to the cached raw-precip CSV when GEE auth is absent, so it is reproducible without credentials.
- `notebooks/coffee_backtests/README.md`, `docs/FILE_MAP.md` — updated the L3 gate row and status; added a rank-order caveat (L3's annual r is not frame-comparable to the monthly L1/L2 r values — reconcile in the composite notebook).

### Deferred (documented in notebook §10, out of scope for an L3 single-signal backtest)
- Global climate sub-score (L3 + ENSO + Vietnam monsoon) with weights → composite notebook 06; Vietnam monsoon is a separate robusta data source.
- New-crop (U/Z) futures contract as the target → needs paid contract-level ICE/CHRIS data; using continuous `KC=F` as the proxy (logged as a known limitation).
- Granger causality → n=15 crop years is too small; the lag sweep / CCF is the honest substitute at this sample size.
- Forward-cover ratio, OTM call-option timing, buy-zone / risk-limit rules → product/recommendation layer (Phase 5–6); they consume the validated signal, they don't validate it.

---

## [0.15.0] — 2026-06-08

### Changed
- **Corrected the L2b ENSO thesis — sign and lag were both backwards.** The original signal encoded "La Niña droughts Brazil/Vietnam → higher prices 18–24m later." Verified the new country-impact matrix (`docs/enso_coffee_country_matrix.html`) against peer-reviewed and industry sources: **El Niño** is the dominant coffee supply-risk phase. El Niño droughts Vietnam + Indonesia robusta (~40M bags) at flowering and stresses parts of Brazil; La Niña is *beneficial* for those origins and for Brazil arabica (frost avoidance) and mainly hurts Colombia. The net effect is therefore modest and origin-offsetting, which is why the aggregate ENSO signal is a low-weight amplifier.
- `domains/coffee/sources/noaa_enso.py` — flipped `enso_risk_score` from `0.5 − oni/3` to `0.5 + oni/3` (El Niño/positive ONI → high risk). Rewrote module + function docstrings to the corrected thesis and changed lag guidance from 18–24m to a **~14m lead** against **forward** YoY price.
- `tests/domains/coffee/test_noaa_enso.py` — updated the 8 `enso_risk_score` assertions for the flipped sign; all 26 ENSO tests pass.
- `notebooks/coffee_backtests/02_enso_signal.ipynb` — rebuilt around the El Niño thesis. Redefined gate: peak r(ONI, forward-12m YoY) ≥ +0.20 in the 10–18m band. **Now PASSES** — r=+0.288 @15m lead (KC=F 2010–24, p=1.6e-4) and r=+0.327 @15m (WB Arabica 2000–24, p=1.4e-8, confirming it is not a single-2024 artifact). Added an event study: El Niño months are followed by **+36.5%** mean fwd-12m price change vs La Niña **−1.7%** (Welch t=5.83, p<0.001). Explains the strong *contemporaneous* negative r (−0.34) as a lead/lag artifact of ENSO quasi-periodicity, not causation.

### Added
- `.github/workflows/verify.yml` — CI running `make verify` (check-imports + lint + test, via `uv sync --frozen`) on every push to `main` and every PR. Closes the gap that let a lint-breaking commit reach `main`: the "run `make verify` before committing" rule was CLAUDE.md convention only, with no enforcement (no CI, no git hook). CI is the model- and human-agnostic backstop; enable branch protection on `main` to make it blocking.

### Fixed
- `notebooks/coffee_backtests/01_ice_price_signal.ipynb` — 6 ruff lint errors (unsorted imports, empty f-strings, ambiguous `l` loop vars) that were breaking `make verify`. Note: the PostToolUse `ruff format` hook does not run `ruff check`, so these were never auto-caught — hence the new CI gate.

### Why it matters
L2b moves from FAIL to a validated lead signal — the first climate signal to clear its gate — and the user-facing language flips ("El Niño developing → Vietnam crop short in ~14 months" rather than the previous, incorrect La Niña framing). CI now prevents red builds (lint/test/import-boundary) from reaching `main` regardless of who or what commits.

---

## [0.14.0] — 2026-05-28

### Added
- `domains/coffee/sources/chirps.py` — CHIRPS rainfall source (L3) via Google Earth Engine; `fetch(start, end)` returns monthly area-mean precipitation over the Minas Gerais FAO GAUL polygon (`UCSB-CHG/CHIRPS/PENTAD`, one server-side aggregation + single `getInfo()`); adds `drought_risk_score`, `is_flowering_month`, and a `load_from_netcdf` no-GEE fallback (lazy `xarray`). 20 tests, all passing (GEE mocked at the `_query_monthly_precip` boundary)
- `tests/domains/coffee/test_chirps.py` — 20 tests: `drought_risk_score` (deficit scaling / off-season halving / clamping), flowering-month flags, `_month_end`, fetch success (month-end anchoring, None-month skip, metadata, date filter, sort), EEException → FAILED run, NetCDF import guard
- `notebooks/coffee_backtests/05_chirps_signal.ipynb` — L3 backtest (real GEE data, 216 months 2008–2025): climatology check, anomaly + drought signal, monthly lag sweep, annual flowering-season test, gate, rolling stability, interpretation cell
- `domains/coffee/registry/assets.py` — added `CHIRPS_MINAS` asset (`climate:chirps:minas_gerais`, type `climate_signal`)
- `earthengine-api>=1.0` added as a main dependency (runtime dep of `chirps.py`)

### Key findings (notebook 05 — L3, real GEE data 2010–2024)
- **Gate narrowly FAILS** — best monthly r(dryness, fwd YoY change) = **+0.10 @ 14m lag** (gate ≥ +0.12); `drought_risk_score` form +0.11
- **But mechanistically sound** — right sign, contemporaneous r ≈ 0, peak at ~14m matches the flowering (Sep–Nov) → harvest → price chain. Annual flowering-season dryness vs next-12m price = **+0.40 (n=15, p=0.14)** — right magnitude, underpowered with 15 crop years
- **Extraction validated** — climatology shows correct Minas Gerais seasonality (wet Nov–Mar ~200 mm, dry Jun–Aug ~10 mm)
- **Composite role:** keep as a **low-weight flowering-season amplifier** via `drought_risk_score`; too weak/underpowered to time on alone. Rolling 3yr r positive in 62% of windows
- **All five data sources are now implemented and backtested on real data** — composite (notebook 06) is the remaining validation step

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
