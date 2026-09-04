# Notebook 02 — ENSO ONI Signal (L2b): Reader's Guide

This document explains what each section of `notebooks/coffee_backtests/02_enso_signal.ipynb` is doing, the math behind it, and how to interpret the outputs. It is intended as a teaching reference for anyone reading the notebook for the first time.

---

## What the notebook is trying to answer

Two questions, answered in sequence:

1. **Does the NOAA Oceanic Niño Index (ONI) — a measure of El Niño/La Niña strength — predict Arabica price direction, and at what lag?**
2. **If so, does that predictive relationship translate into an actual purchasing edge** when turned into a real month-by-month buying rule, or is the correlation a statistical artifact that doesn't survive contact with an economic test?

The notebook title says "corrected thesis" because an earlier version of this analysis got both the **sign** and the **lag** backwards — it tested whether *La Niña* predicted a price rise at a *24-month* lag and (correctly) found nothing. The corrected mechanism, grounded in `docs/enso_coffee_country_matrix.html`, is that **El Niño** (positive ONI) droughts Vietnam and Indonesia robusta at flowering and leads Arabica prices up roughly **14–16 months** later.

---

## Background: why El Niño, not La Niña

ENSO has *opposite* effects across origins, so there's no single "one phase is bad" rule:

- **Vietnam + Indonesia robusta (~40M bags)** — El Niño shifts Pacific rainfall east, drying the Central Highlands at flowering → reduced yield. This is the strongest, most robust link (2015–16 and 2023–24 both cut the Vietnam crop).
- **Colombia arabica** — El Niño is *beneficial* (drier/sunnier); it's La Niña's excess rain that cuts Colombian yield and raises leaf-rust pressure.
- **Brazil arabica (Minas Gerais)** — weak/ambiguous: El Niño warmth reduces frost risk, a slight offsetting *positive* effect.

Net effect: high ONI → drought in the dominant producers → supply shortfall → higher Arabica price ~12–16 months later, but the Brazil offset keeps the net correlation modest (|r| ~ 0.3), not strong.

The strong *contemporaneous* negative correlation you'd see at lag 0 (r ≈ −0.36) is a lead/lag artifact of ENSO's own quasi-periodicity — La Niña typically *follows* the El Niño that caused the shortage, so it coincides with the resulting price spike without causing it.

---

## §0 — Setup

Imports and `sys.path` setup so `domains/coffee` is importable. Pulls in `enso_risk_score` and `fetch` from `domains/coffee/sources/noaa_enso.py`. No analysis here.

---

## §1 — Fetch NOAA ONI Data

Fetches monthly ONI anomalies from 1980–2025 (552 months) via the real `fetch()` source. Confirms `RunStatus.SUCCESS` and a sane range: **[−1.85, +2.75] °C**.

The source itself has a couple of parsing quirks worth knowing about (see `domains/coffee/sources/noaa_enso.py` / CLAUDE.md): NOAA's fixed-width text format uses `-99.9` as a missing-value sentinel (skipped, not a parse error), and the season-to-year mapping needs a special case for the `NDJ` season (its January falls in `YR+1`, unlike every other season).

---

## §2 — Load ICE KC=F Reference Data

Reads the cached `data/ice_kc_monthly.csv` (221 months, 2008–2026) rather than re-fetching — this is the same Yahoo Finance `KC=F` series used throughout the other notebooks.

---

## §3 — Visual Inspection: ONI vs Arabica Price

Two stacked panels: ONI over time (El Niño/La Niña shaded above/below the ±0.5 °C thresholds), and KC=F price with faint red bands drawn **12–16 months after** each El Niño month — a purely visual check for whether price rises cluster inside those bands before running any statistics.

---

## §4 — Lag Analysis: Correlation at Each Lag (0–36 months)

**The question:** rather than assume the ~14-month lead, sweep every lag from 0 to 36 months and see where the correlation with price actually peaks.

**The method:** for each lag, compute two correlations against `ONI` shifted back by that many months:

```
r_price = Pearson r( ONI_{t-lag},  price_level_t )
r_yoy   = Pearson r( ONI_{t-lag},  12m_YoY_change_t )
```

`r_price` asks "does lagged ONI track the price regime?" `r_yoy` asks "does lagged ONI predict the *direction* of the next move?" — the second is what a purchasing signal actually needs.

**What the results show (2010–2024):**

| Lag | r(ONI, price level) | r(ONI, fwd YoY) |
|---|---|---|
| 0m | −0.338 | −0.357 |
| 8m | −0.194 | +0.013 |
| **15m** | −0.079 | **+0.288 (peak)** |
| 24m | −0.127 | +0.065 |
| 36m | −0.313 | −0.287 |

`r_price` stays negative across the **entire** 0–36m sweep — it never confirms the thesis at any lag. Only `r_yoy` flips sign, peaking at **lag 15m, r = +0.288**, inside the mechanistic 10–18m band the thesis predicts. This lag (`peak_lag`) is reused throughout the rest of the notebook.

**Statistical caveats worth knowing:**

- Because `r_yoy` is built from overlapping 12-month rolling windows, adjacent lags are highly autocorrelated — the p-values reported later (e.g. p=1.6e-4 at the gate) assume independent observations and likely overstate significance by a wide margin; the true effective sample size is much smaller than the nominal month count.
- The 10–18m band was set *before* looking at the data (mechanistically motivated), but the exact peak (15m) inside that band is chosen *from* the data — a mild form of the same in-sample selection notebook 01 flags for its window choice.
- Only `r_yoy` supports the thesis; `r_price` contradicts it at every lag tested. The "confirmation" is conditional on choosing YoY change as the target, not something both metrics agree on.

---

## §5 — Walk-Forward Purchase Simulation

**The question:** does the Section 4 correlation actually translate into cheaper average purchases when turned into a real month-by-month buying rule — tested the same way notebook 01 tests L1?

**The weight rule:**

```
weight_t = enso_risk_score( ONI_{t - peak_lag} )
```

Month *t*'s purchase weight is set by the ONI reading observed `peak_lag` (15) months earlier — literally the same lag structure the correlation test used. A high ONI reading 15 months ago raises this month's weight, i.e. the simulated roaster buys more heavily in months that follow an elevated-ONI reading by the mechanistic lead time. (This is a different design choice than "front-run the future price rise using today's ONI" — it mirrors the correlation test directly rather than acting on the most current information available.)

Tested in isolation — no blending with the L1 price-position signal — so results can be attributed to ENSO alone. Naive baseline and cost-saving metric are identical to notebook 01: `saving_pct = (naive_avg − sig_avg) / naive_avg × 100`, evaluated year by year over 2010–2024, no look-ahead.

**What the results show:**

| | Avg saving vs naive | Positive years |
|---|---|---|
| 2010–2024 (full) | **−0.07%** | 8/15 |
| Excluding 2023–24 | +0.65% | 8/13 |

**ENSO alone does not produce a reliable economic edge.** Despite clearing its correlation gate (r=+0.288, "PASS" by the r≥+0.20 threshold), weighting purchases by the lagged risk score is essentially a coin flip against naive buying — and it isn't a 2023–24 concentration artifact either; the result is weak with or without those years. This is a meaningful finding: **the correlation gate and the walk-forward economic result do not agree**, which is exactly why the walk-forward is the more decision-relevant number for how much conviction this signal deserves.

---

## §6 — Save Reference CSV

Writes `data/oni_monthly.csv` for downstream notebooks (e.g. the eventual composite backtest).

---

## §7 — Summary

Prints a consolidated summary: the Section 4 correlation basis, the walk-forward headline numbers, and an interpretation that adapts automatically to whichever result the walk-forward produces (rather than hard-coding a conclusion). Restates the mechanistic story and notes that the walk-forward number — not the correlation alone — should drive composite weighting.

---

## Key numbers to know

| Metric | Value | Where |
|--------|-------|-------|
| Peak lag | 15 months | §4 |
| Peak r(ONI, fwd YoY) | +0.288, p=1.6e-4 (likely overstated, see §4 caveats) | §4 |
| Gate L2b (r ≥ +0.20) | PASS | §4 |
| Walk-forward avg saving, 2010–2024 | −0.07% | §5 |
| Walk-forward positive years | 8/15 | §5 |
| Excluding 2023–24 | +0.65% avg, 8/13 positive | §5 |
| Composite role (CLAUDE.md) | Low-weight amplifier, weight ~0.24 | — |

The correlation gate passing does **not** imply a standalone purchasing edge — the walk-forward result is the number to weigh when deciding how much conviction ENSO deserves relative to L1 (which clears both its correlation gate *and* its walk-forward test, +7.34% avg / 10-12 positive years).
