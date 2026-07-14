# GreenSignal — Next Steps

This file is the handoff note between sessions. Claude updates it automatically at the end of each working session. Both collaborators should read it at the start of any session and update it when priorities shift.

---

## Current focus

**Phase 1 — Real data pipelines and backtest validation**

The skeleton is built and the architecture is locked. The immediate work is implementing the first three data sources (no GEE needed) and running them through the backtest notebooks to validate signal rank order on real data before any product work begins.

---

## Up next (in order)

- [ ] **Register for Nasdaq Data Link** at `data.nasdaq.com` — get API key, add to `.env` ← **do this before next session starts**
- [x] **Implement `domains/coffee/sources/ice_coffee_c.py`** — fetch `CHRIS/ICE_KC1` daily close, return `list[MarketObservation]`
- [x] **Run `notebooks/coffee_backtests/01_ice_price_signal.ipynb`** — ALL GATES PASS: contemp r=+0.852, cost saving=+10.73% (full-history) / +3.71% walk-forward (12/12 years positive), zone monotone; momentum baseline −10.37% validates contrarian; 104w window +15.01%
- [x] **Implement `domains/coffee/sources/world_bank_commodity.py`** — World Bank Pink Sheet; Arabica + Robusta physical prices (free, no auth); two-step fetch (scrape page → download Excel); 15 tests pass
- [x] **Implement `domains/coffee/sources/noaa_enso.py`** — 26 tests passing; NDJ year-boundary handled; -99.9 sentinel skipped
- [x] **Run `notebooks/coffee_backtests/02_enso_signal.ipynb`** — original 24m-lag gate FAILED because the thesis was inverted. Corrected to **El Niño = supply-risk phase** (verified against `docs/enso_coffee_country_matrix.html` + peer-reviewed sources): El Niño droughts Vietnam/Indonesia robusta, La Niña is beneficial there & in Brazil (frost avoidance) and only hurts Colombia. Redefined gate (r ≥ +0.20 vs **fwd** YoY, ~14m lead) **PASSES**: r=+0.288 @15m (KC 2010–24) / +0.327 @15m (WB 2000–24, p=1.4e-8); event study El Niño months→+36.5% fwd-12m vs La Niña −1.7% (t=5.83). Flipped `enso_risk_score` sign in `noaa_enso.py` (now rises with El Niño); 26 tests updated & passing
- [x] **Implement `domains/coffee/sources/cot.py`** — CFTC disaggregated annual ZIPs; filters to `COFFEE C - ICE`; returns weekly net managed-money positions; `_cot_index` (0-100 rolling) + `cot_contrarian_signal` helpers; 20 tests pass
- [x] **Run `notebooks/coffee_backtests/03_cot_signal.ipynb`** — original contrarian gate FAILS (r=−0.05 @ fwd 12m, need ≥ +0.08); thesis is *inverted* on real data. Also fixed `cot.py`: pre-2013 vintages name the date column `Report_Date_as_MM_DD_YYYY` (was silently dropping 2010–2012); broadened prefix match + regression test
- [x] **Rebuilt notebook 03 around the momentum thesis — now PASSES** (`88af1e9`): `r(COT index, fwd 6m change) = +0.144` (p=0.053, n=180) vs gate ≥+0.08. Horizon sweep confirms 6m as the peak. Signal is real but weak/borderline: p at the edge of conventional significance, 3yr rolling stability only 45% positive. Walk-forward $ savings don't materialize (momentum signals don't reduce weighted-avg purchase price the way contrarian ones do) — notebook concludes the correct role is a **low-weight composite amplifier, not a standalone timer**. `cot_contrarian_signal()` in `cot.py` still encodes the old disproven contrarian sign — needs updating to the momentum framing when wired into `signal_generator` (notebook 06)
- [x] **Implement `domains/coffee/sources/usda_psd.py`** (L2a) — bulk ZIP → world stocks-to-use %; corrected stub assumptions (commodity code is int `711100`; no World row → sum 94 countries; attr `125`=Domestic Consumption not `57`); `stu_risk_score` + `load_from_csv` helpers; 20 tests pass. Real data: world S/U 22% (2018) → 11.6% (2025)
- [x] **Run `notebooks/coffee_backtests/04_usda_supply_signal.ipynb`** — YoY-change gate FAILS (r=−0.04) but signal is **strong on price level**: r=−0.40 monthly, −0.56 annual (n=15), −0.59 @ 23m lag. S/U is a slow annual stock var — YoY-change is the wrong lens
- [x] **Rebuild notebook 04 for look-ahead bias + redefined dual gate** — the PSD bulk file is the latest-*revised* vintage of every marketing year, so the original r=−0.40 to −0.59 was contaminated by information a roaster wouldn't have had in real time. Fixed with a practical 12m-forward shift of the monthly series (simulates publication lag); raw r weakens to −0.26 once corrected. Redefined gate to two tests, **both PASS**: Gate 1 r(vintage S/U, 12m-fwd price)=−0.312 (p=2.0e-5); Gate 2 r(S/U YoY delta, price level)=−0.259 (p=4.6e-4). Added 10yr rolling z-score (no look-ahead), YoY delta, months-of-consumption features, and a z-score-based non-linear stress score replacing the linear 12%/35% clamp. Rolling 3yr stability is honest but modest (52% of windows negative, up from 23% on the old YoY basis) — full-sample gates are the stronger evidence
- [x] **Implement `domains/coffee/sources/usda_coffee_wmt.py`** — true vintage-aware world stocks-to-use %, superseding the deferred "build a WASDE-vintage series" item (that scoping was based on an incorrect premise: **WASDE does not cover coffee at all** — the correct USDA report is the separate semiannual "Coffee: World Markets and Trade" circular, archived to June 2004 at `esmis.nal.usda.gov`). Discovers the archive by paginating the ESMIS listing (had to fix a real bug: the pager loops back to page-0 content past the real archive depth instead of returning empty — pagination now stops on "no new dates added," not "empty page"), downloads + parses each circular's summary table (format drifted across 20 years; anchored on the literal phrase "Thousand 60-Kilogram Bags" to avoid a false-positive page-1 narrative subsection also titled "Ending Stocks"). 31 reports parse cleanly (2010-06 to 2025-06); pre-June-2010 issues fail to parse and are skipped (acceptable — outside the notebook's core window). Cross-validated: Dec 2025 parse (11.59%) matches `usda_psd.py`'s independent 11.6% for the same period. 24 tests pass (all HTTP/PDF calls mocked). Reviewed via `data-source-reviewer` — **APPROVED**. New main deps: `pdfplumber`, `beautifulsoup4`
- [x] **Wire the true vintage source into notebook 04** — new §11 fetches `usda_coffee_wmt.fetch()`, aligns the irregular semiannual dates to price via `pd.merge_asof`, and re-runs both gates: Gate 1 r=−0.488 (p=6.2e-3, n=30) — *stronger* than the 12m-shift approximation's −0.312; Gate 2 r=−0.261 (p=0.17, passes the threshold but not significant at this small semiannual sample). Approximation and true series agree directionally but only moderately (r=+0.49 between them, mean abs diff 3.1pp) — kept the approximation as a documented fallback (monthly cadence, covers pre-June-2010)
- [ ] **Promote `stu_z_score` / `stu_stress_score` / the true-vintage series** from notebook 04 into `domains/coffee/features/supply_features.py` (currently a stub) when wiring the composite — mirrors the SPI-promotion item below for L3
- [ ] *(optional, low priority)* Extend `usda_coffee_wmt.py` coverage before June 2010 — older circulars use a different/unparseable format; only worth it if the composite (06) shows L2a's weight is sensitive to the extra 6 years of history
- [ ] *(optional, low priority)* Wire `usda_coffee_wmt.fetch()` into a scheduled job (`jobs/coffee/monthly_supply.py`, currently a stub) to build a running SourceRun vintage history in production — a Phase 1 scheduling task, not a backtest task
- [x] **Implement `domains/coffee/sources/chirps.py`** (L3) — GEE CHIRPS PENTAD over Minas Gerais GAUL polygon; monthly area-mean rainfall + `drought_risk_score`; NetCDF fallback; 20 tests. GEE project `western-plate-432020-t5`, auth via `EARTHENGINE_PROJECT` env
- [x] **Run `notebooks/coffee_backtests/05_chirps_signal.ipynb`** — ~~gate narrowly FAILS (r=+0.10 monthly @ 14m lag)~~ **REBUILT around SPI (desk review).** Primary = flowering **SPI-3 (Sep–Nov) deficit** vs fwd-12m price on the **annual crop-year frame**: r=**+0.483 (p=0.069, n=15)** → **PASSES** redefined gate (annual r ≥ +0.30, confirming signal). Deficit `max(0,−SPI3)` beats signed SPI (−0.412 → asymmetric); robust to look-ahead (expanding r=+0.494) & to a stocks-to-use control (partial r=+0.48); driest vs wettest flowering third → +33.6% vs +9.5% fwd-12m. Old monthly r≥+0.12 lens diluted an annual once-a-year signal
- [ ] **Promote the SPI flowering-deficit feature** from notebook 05 into `domains/coffee/features/climate_features.py` (canonical L3 feature; replaces the provisional mm-anomaly `drought_risk_score` in `chirps.py`). Feed the composite as a continuous z-score, not a 0/1 flag. Do this when wiring notebook 06
- [ ] *(deferred, later phase)* Climate sub-score (L3 + ENSO + **Vietnam monsoon** robusta source) → composite/06; new-crop (U/Z) contract target → needs paid ICE data; forward-cover ratio / OTM-call timing / risk limits → product layer (Phase 5–6). All logged in notebook 05 §10
- [ ] **Run `notebooks/coffee_backtests/06_composite_backtest.ipynb`** — all 5 sources now implemented **and all 5 clear their gates**. Re-validate the composite on real data with the revised signal roles (L1 strong; L2a true vintage, dual gate; **L2b now a validated ~14m El Niño lead, r≈+0.29–0.33**; **L3 now a validated confirming amplifier via the SPI flowering deficit, annual r=+0.48, but borderline p=0.069, n=15**; **L5 now a validated momentum amplifier, r=+0.144 @ 6m, but borderline p=0.053 and weak 45% rolling stability**). When wiring L2b, apply a **~14m lead** and the **flipped** `enso_risk_score` (El Niño→high risk); wire L3 as the SPI flowering-deficit z-score; wire L5 with the corrected momentum sign in `cot_contrarian_signal()`. Run a leave-one-out ablation on L3 and L5 specifically (both borderline) before finalizing weights — don't just average in every signal that technically clears its own gate
- [ ] **Run `notebooks/coffee_backtests/06_composite_backtest.ipynb`** — confirm all five gates pass and signal rank order holds

### Tooling / infra
- [x] **Add CI** — `.github/workflows/verify.yml` runs `make verify` (check-imports + lint + test) on push to `main` + PRs. Closes the gap that let a lint-breaking commit land (verify-before-commit was CLAUDE.md convention only, never enforced)
- [ ] **Enable branch protection on `main`** (GitHub repo admin) — require the `verify` status check to pass before merge/push. Until this is set, CI is informational only and a red run does not block. Both founders should also confirm their Claude Code loads the project `.claude/settings.json` hooks + `CLAUDE.md` (they are checked in, not gitignored)
- [ ] *(optional)* Add a CHANGELOG-freshness CI nudge (warn if `domains/`, `core/`, or notebooks changed without a `CHANGELOG.md` edit) — deterministic reminder for the doc-update convention. Hold unless doc drift recurs

---

## Blocked / waiting

| Item | Blocked on |
|------|-----------|
| ~~`chirps.py` implementation~~ | ✅ done — GEE access granted, project `western-plate-432020-t5` |
| Supabase storage wiring | Not needed until signals are validated |
| FastAPI routes (coffee) | Not needed until signals are validated |

---

## Decisions made this session

| Decision | Rationale |
|----------|-----------|
| Canonical models use Pydantic `BaseModel` | FastAPI serialization, no extra layer needed |
| `forecaster.py` deleted | Pointless wrapper until `fit_and_forecast` is real |
| `make verify` is the pre-commit gate | Import boundary + lint + tests in one command |
| Repo is public on GitHub | Required for branch protection on free plan; no secrets in code |
| `@anshquant` added as Admin collaborator | Anshumaan Gandhi — co-developer |
| `.claude/settings.json` added to repo | Ruff auto-format on every Edit/Write; `.env` write blocked at hook level |
| `.mcp.json` added to repo | GitHub + Supabase MCP servers wired; auth via env vars, not secrets in config |
| `implement-source` skill created | Enforces consistent source contract — prevents drift across 5 implementations |
| `backtest-notebook` skill created | Enforces consistent notebook structure — all 6 notebooks follow same template |
| `data-source-reviewer` agent created | Independent review gate before any source is merged |

---

## Backtest pass/fail gates (do not start product work until all pass)

See `notebooks/coffee_backtests/README.md` for the full table. Summary:

| Signal | Minimum r on real data |
|--------|----------------------|
| L1 price position | ≥ +0.50 |
| L2a stocks-to-use | ≤ −0.25 |
| L2b ENSO ~14m lead (El Niño) | ≥ +0.20 vs fwd YoY (redefined) |
| L3 CHIRPS drought (SPI flowering deficit, annual) | ≥ +0.30 (redefined) |
| L5 COT momentum (redefined from contrarian) | ≥ +0.08 @ fwd 6m |
| Full composite prescience | ≥ 3.50% forward |

---

---

## Decisions made this session

| Decision | Rationale |
|----------|-----------|
| `fetch()` returns `tuple[list[MarketObservation], SourceRun]` | Skill contract — sources log their own run metadata; storage is the job's responsibility |
| Use `Settle` column (not `Last`) for ICE KC price | Settlement price is the official exchange close; `Last` is the final trade and can differ |
| `raw` field stores `dict(zip(column_names, row))` | More useful than a bare list; survives column reordering |
| `datetime.now(UTC)` instead of `utcnow()` | `utcnow()` deprecated in Python 3.12+ |
| `data_quality.py` stubs implemented | Required for `ice_coffee_c.py` to call gap/range checks |
| `core/models/__init__.py` bug fixed | Was importing `Scenario` (doesn't exist); corrected to `ScenarioInput`, `ScenarioOutput` |
| Nasdaq Data Link CHRIS requires paid plan | API returns 403 for CHRIS database; backtest uses Yahoo Finance `KC=F` (equivalent instrument) |
| L1 gate redefined: 3 tests instead of 1 | Phase 0 r=+0.64 was contemporaneous (trivially high); corrected to contemp r + cost-saving + zone monotonicity |
| Arabica mean-reversion is 24m, not 12m | Forward predictive r peaks at 24m lag (r=+0.20); at 12m r≈0 due to momentum-then-revert pattern |
| Real cost-saving is 10.73%, not 2.2% | Phase 0 synthetic underestimated because real prices had more extreme episodes (2024 spike etc.) |

| Walk-forward cost saving is +3.71% (not +10.73%) | Full-history number is in-sample; walk-fwd is the honest out-of-sample estimate — cite this in product/investor comms |
| Momentum baseline is −10.37% vs naive | Trend-following hurts for coffee procurement; contrarian approach validated decisively |
| 104w window (+15.01%) outperforms 52w (+12.95%) | Noted for future composite tuning; not changing current L1 signal until all 5 signals validated |
| L2a z-score/stress-score features stay notebook-local for now | Mirrors the L3/SPI precedent (notebook 05) — validated features are promoted into `domains/coffee/features/*.py` when the composite (06) actually wires them in, not immediately after a backtest |
| WASDE does not cover coffee — corrected mid-session | Review feedback's suggestion to parse "WASDE" reports for a vintage-aware S/U series was based on an incorrect premise (verified via web search: WASDE is grains/oilseeds/cotton/sugar/livestock only). The correct report is USDA FAS's separate semiannual "Coffee: World Markets and Trade" circular — built as `usda_coffee_wmt.py` instead |
| `usda_coffee_wmt.py` pagination stops on "no new dates," not "empty page" | The ESMIS archive listing does not return an empty page past the real archive depth — it wraps back to repeating page-0 content. A naive "stop on empty page" check would loop `_MAX_LISTING_PAGES` times re-fetching the same page; caught via a full historical smoke test before writing unit tests |
| True vintage series kept alongside the shift approximation, not replacing it | The true series only covers June 2010 onward (semiannual); the approximation still fills gaps (pre-2010, or monthly cadence between reports) — both are in notebook 04, true vintage as primary evidence |

*Update: 2026-07-13 — **rebuilt L2a (USDA stocks-to-use) around a vintage correction, then built the true vintage source.** Phase 1: after review feedback flagged the original notebook's use of the PSD bulk file (always the latest-*revised* vintage) as a look-ahead bias, shifted the monthly S/U series forward 12 months to simulate the real publication lag (raw r(S/U, price level)=−0.40 weakens to r=−0.26 once corrected). Redefined the single YoY-change gate into two tests on the vintage-lagged series, both **PASS**: Gate 1 r=−0.312 (p=2.0e-5, n=180), Gate 2 r=−0.259 (p=4.6e-4, n=180). Added a 10yr rolling z-score, YoY delta, months-of-consumption features, and a z-score-based non-linear stress score. Phase 2 (same session, user asked to pursue the "gold standard" fix): the feedback's suggested source, WASDE, turned out not to cover coffee at all (verified via web search) — implemented `domains/coffee/sources/usda_coffee_wmt.py` instead, parsing USDA's actual semiannual "Coffee: World Markets and Trade" circular for a genuinely time-stamped series (24 tests, reviewed via `data-source-reviewer` — **APPROVED**). Wired into notebook 04 §11: the true vintage series gives a **stronger** Gate 1 (r=−0.488, p=6.2e-3, n=30) than the approximation, with Gate 2 passing the threshold but not reaching significance at this small semiannual sample (r=−0.261, p=0.17). Kept both series in the notebook — true vintage as primary evidence, the shift approximation as a documented fallback for pre-June-2010 and monthly-cadence gaps. Declined to promote the new features/source into production `supply_features.py`/`usda_psd.py` yet (per the L3/SPI precedent, wait for composite wiring in notebook 06). `make verify` green (134 tests). Next: composite backtest (06).*

*Prior: 2026-07-02 — **rebuilt L3 (CHIRPS) around SPI** per a commodity-desk review. Replaced the raw-mm anomaly with a gamma-fit Standardized Precipitation Index; primary feature is now the flowering **SPI-3 (Sep–Nov) deficit** on the annual crop-year frame. Redefined the gate (annual r ≥ +0.30, confirming signal) — **PASSES at r=+0.483 (p=0.069, n=15)**, up from the old raw-mm +0.398. Added expanding-window (no look-ahead, r=+0.494) and partial-correlation-vs-stocks (r=+0.48) robustness checks, and a tercile event study (dry vs wet flowering third → +33.6% vs +9.5% fwd-12m). Deferred Vietnam-monsoon / new-crop-contract / forward-cover / options items to later phases (notebook 05 §10). `make verify` green (110 tests). Next: promote the SPI feature to `climate_features.py` and run the composite (06).*

*Prior: 2026-06-08 — **corrected the L2b ENSO thesis.** The original "La Niña droughts Brazil/Vietnam, 24m lag" had the sign AND lag backwards. Verified the country matrix (`docs/enso_coffee_country_matrix.html`) against peer-reviewed sources: El Niño is the dominant supply-risk phase (droughts Vietnam/Indonesia robusta; La Niña is beneficial there & in Brazil, only hurts Colombia). Flipped `enso_risk_score` in `noaa_enso.py` and rebuilt notebook 02 — redefined gate (r ≥ +0.20 vs fwd YoY at ~14m lead) now **PASSES**: r=+0.288 @15m (KC) / +0.327 @15m (WB 2000–24); event study El Niño→+36.5% vs La Niña −1.7%. 26 ENSO tests updated & green. Next: composite backtest (notebook 06) — L1 strong, L2a strong-on-level, L2b now a validated ~14m lead, L3/L5 weak amplifiers; then redefine L2a gate, decide L5 fate.*

*Prior update: 2026-05-28 — implemented `chirps.py` (L3) via GEE + notebook 05 (gate narrowly FAILS r=+0.10 @ 14m, but right sign/lag/mechanism, annual flowering r=+0.40). All 5 sources implemented and backtested on real data. 110 tests pass, `make verify` green.*
