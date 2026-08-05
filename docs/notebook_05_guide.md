# Notebook 05 — CHIRPS Rainfall Signal (L3): Reader's Guide

This document explains what each section of `notebooks/coffee_backtests/05_chirps_signal.ipynb` is doing, the math behind it, and how to interpret the outputs. It is intended as a teaching reference for anyone reading the notebook for the first time.

---

## What the notebook is trying to answer

Two questions, answered in sequence:

1. **Does below-normal rainfall over Minas Gerais (Brazil's primary Arabica state) during the Sep–Nov flowering season predict higher Arabica prices, and at what lag?**
2. **Does that relationship translate into an actual purchasing edge**, tested the same way notebooks 01 and 02 test theirs?

**Thesis:** drought at flowering → fewer cherries set → smaller harvest ~6–12 months later → higher price. Data comes from CHIRPS (satellite-derived rainfall), aggregated to a monthly area-mean over the Minas Gerais state polygon via Google Earth Engine.

---

## §0 — Setup

Imports, path setup, and loads `EARTHENGINE_PROJECT` from the environment for the live GEE fetch in §1. If that variable isn't set (no GEE credentials available), a `GEE_AVAILABLE` flag is set to `False` and §1 falls back to the already-saved `data/chirps_minas_monthly.csv` instead of failing outright — useful for re-running the notebook somewhere without GEE auth configured, at the cost of using a previously-cached data snapshot rather than a fresh pull.

---

## §1 — Fetch CHIRPS Data via GEE

Live path: one `getInfo()` round trip to Earth Engine aggregates monthly area-mean rainfall over the Minas Gerais GAUL polygon server-side (avoids pulling raw pentad data client-side). Fallback path: reads the cached CSV's `precip` column directly. Either way, produces `rain['precip']`, a monthly rainfall series (216 months, 2008–2025, range [4.4, 353.6] mm).

---

## §2 — Data Quality + Seasonality

Confirms no NaN/negative rainfall over the 2010–2024 core window, then prints the monthly climatology (mean mm by calendar month). Confirms the expected pattern: wet Nov–Mar (~150–240mm), dry Jun–Aug (~9–11mm), with the Sep–Nov flowering months (marked `<- flowering`) sitting in the transition from dry to wet.

---

## §3 — Feature Engineering: Anomaly + Drought Signal

Builds the derived columns used everywhere downstream:

```
clim     = that calendar month's 2008-2025 mean rainfall
anomaly  = precip - clim
flowering = month in {Sep, Oct, Nov}
dryness   = -anomaly          # positive when drier than normal
drought_risk = drought_risk_score(anomaly, flowering)
```

`drought_risk_score()` (from `domains/coffee/sources/chirps.py`) is a clamped linear 0–1 score: `deficit = max(0, -anomaly)`, `risk = min(1, deficit / 60mm)`, halved outside the flowering season. It's the CHIRPS equivalent of `enso_risk_score()` in notebook 02.

---

## §4 — Correlation vs ICE KC Price

**The method:** merges CHIRPS features with ICE KC=F month-end settle prices, then sweeps lags 0–24 months, correlating `dryness` (and the scored `drought_risk` variant) against the **forward** YoY price change:

```python
for lag in range(0, 25):
    yoy_lead = trail_yoy.shift(-lag)
    r_dry  = pearsonr(dryness, yoy_lead)
    r_risk = pearsonr(drought_risk, yoy_lead)
best = argmax(r_dry)
```

**What the results show:** `best = 14` months. `r(dryness, fwd YoY) = +0.100` at that lag (contemporaneous r ≈ 0, as expected — drought today doesn't move price today). The `drought_risk_score` variant scores slightly better, +0.114, both still below the +0.12 gate threshold.

A separate **annual mechanistic test** — flowering-season dryness in year Y vs. the price change over the following 12 months — is more encouraging: r=+0.398 (n=15, p=0.14), the right sign and magnitude but underpowered with only 15 crop years of data.

---

## §5 — Gate Validation: r(drought, YoY change) ≥ +0.12

Formalizes the Section 4 result against the stated gate. **Result: FAIL** — best lagged r = +0.1002 @ 14m, just under the +0.12 threshold. Supporting numbers (contemporaneous r, the `drought_risk_score` variant, and the annual test) are printed alongside for context. A scatter plot of annual flowering dryness vs. forward 12-month price change (with a fitted trend line) visualizes the underlying (weak, noisy) relationship.

---

## §6 — Walk-Forward Purchase Simulation

**Why this replaced the old "Rolling Stability" section:** the notebook originally had a 36-month rolling-correlation stability check here, but it computed the rolling correlation at **lag 0** (contemporaneous) — a relationship Section 4 already showed is ≈0. The notebook's actual mechanistic claim is the 14-month lead, so the old section was testing the stability of the wrong relationship entirely, and its "62% of windows positive" statistic didn't speak to the signal actually being proposed. It's been replaced with a correctly-lagged, decision-relevant walk-forward test — the same design used in notebooks 01 and 02.

**The weight rule:**

```
weight_t = drought_risk_{t - best}
```

Month *t*'s purchase weight reuses the already-computed `drought_risk` column (which already has the correct flowering flag baked in per-row), shifted back by `best` (14) months — the lag identified in Section 4. Tested in isolation, no blending with L1 or other signals.

**What the results show:**

| | Avg saving vs naive | Positive years |
|---|---|---|
| 2010–2024 (full) | **+1.01%** | 8/15 |
| Excluding 2023–24 | +0.96% | 7/13 |

Marginally positive, but barely more than half the years beat naive buying, and the average saving (~1%) is a small fraction of L1's walk-forward result (+7.34% avg). CHIRPS alone doesn't produce a reliable economic edge, though it's directionally less bad than ENSO's isolated result (−0.07% avg) tested the same way in notebook 02.

---

## §7 — Save Reference CSV

Writes the full `rain` DataFrame (`precip`, `clim`, `anomaly`, `flowering`, `dryness`, `drought_risk`) to `data/chirps_minas_monthly.csv` — this is also what §1's fallback path reads back in when GEE isn't reachable.

---

## §8 — Summary

Prints a consolidated summary: data coverage, the Section 4/5 correlation results, the gate outcome, and the new walk-forward headline (avg saving, positive years, exclude-2023–24 robustness cut).

---

## §9 — Interpretation & Composite Implication

**Gate narrowly FAILS, but L3 is mechanistically sound.** The peak lag (14m) matches the flowering→harvest→price chain exactly, and the contemporaneous r≈0 is exactly what you'd expect if drought today doesn't move price today. The likely reason it lands just under +0.12: monthly area-mean rainfall mixes the whole state across the whole year, but the price-relevant information is concentrated in a 3-month flowering window once a year — a plain monthly Pearson r dilutes it.

**Composite implication:** keep L3 as a **low-weight flowering-season amplifier** via `drought_risk_score` (0.22 weight in the climate sub-score) — useful for *explaining* why a buy window is opening ("Minas Gerais flowering was dry"), but Section 6's walk-forward result is the more decision-relevant check on how much standalone conviction it deserves relative to L1.

---

## Key numbers to know

| Metric | Value | Where |
|--------|-------|-------|
| Best lag | 14 months | §4 |
| Best r(dryness, fwd YoY) | +0.100 | §4 |
| Best r(drought_risk, fwd YoY) | +0.114 | §4/§5 |
| Gate L3 (r ≥ +0.12) | FAIL | §5 |
| Annual flowering vs fwd 12m price | +0.398 (n=15, p=0.14) | §4 |
| Walk-forward avg saving, 2010–2024 | +1.01% | §6 |
| Walk-forward positive years | 8/15 | §6 |
| Excluding 2023–24 | +0.96% avg, 7/13 positive | §6 |
| Composite role (CLAUDE.md) | Low-weight flowering-season amplifier, weight 0.22 | — |

Like ENSO in notebook 02, CHIRPS's correlation result — whether it passes or fails its gate — doesn't map cleanly onto a standalone walk-forward edge. Neither signal beats naive buying by more than ~1% in isolation; only L1 (price position) does.
