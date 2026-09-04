# Notebook 04 — USDA Stocks-to-Use Signal (L2a): Reader's Guide

This document explains what each section of `notebooks/coffee_backtests/04_usda_supply_signal.ipynb` is doing, the math behind it, and how to interpret the outputs. It is intended as a teaching reference for anyone reading the notebook for the first time.

**Note on scope:** unlike notebooks 01, 02, 03, and 05, this notebook is purely a **correlation / gate-validation** notebook — there is no purchase-simulation or walk-forward backtest here yet. It ends with a rolling-stability robustness check and an interpretation section that recommends *redefining* the gate metric itself, rather than a walk-forward economic test. Adding a walk-forward section (mirroring the other four notebooks) is a natural next step but is out of scope for this guide.

---

## What the notebook is trying to answer

**Does the world coffee stocks-to-use ratio (S/U %) — the size of the buffer between what's produced and what's consumed — predict Arabica price?**

**Thesis:** when world ending stocks fall relative to consumption, the supply cushion thins and prices rise. Data comes from the USDA's Production, Supply & Distribution (PSD) database — the bulk per-commodity CSV, no auth required.

**Caveat stated up front in the notebook:** PSD publishes the *latest revised vintage* of each marketing year, and it's an annual series (one point per marketing year) — so this is fundamentally a contemporaneous relationship, not a clean forward-predictive test the way notebooks 01/02/05's lag sweeps are. The annual S/U is forward-filled to monthly to align with price, and the notebook reports the annual-level correlation alongside the monthly one as a robustness check on the small effective sample (~15 marketing years).

---

## §0 — Setup

Imports and path setup. Pulls in `fetch` and `stu_risk_score` from `domains/coffee/sources/usda_psd.py`. No analysis here.

---

## §1 — Fetch USDA PSD Data

Downloads the bulk coffee CSV (`psd_coffee.csv`, inside a ZIP) live from USDA FAS, computes world stocks-to-use as **Σ(ending stocks) / Σ(domestic consumption) × 100** summed across all 94 individual countries PSD tracks (there's no built-in "World" aggregate row), one value per marketing year anchored to Dec 31.

**Result:** 26 marketing years (2000–2025), range **[11.6%, 91.5%]**. The most recent years show a steep decline:

```
2018: 22.3%    2022: 16.0%    2024: 12.4%
2019: 22.1%    2023: 14.1%    2025: 11.6%  <- tightest in the series
2020: 23.1%
2021: 19.0%
```

---

## §2 — Data Quality Checks

Confirms no NaN and all values fall within a sane (0, 100)% range over 2010–2024. Prints the tightest (11.6%, 2025) and amplest (91.5%, 2001) buffer years, and plots the full time series — visually, a long decline from the early-2000s highs down to the current multi-decade low.

---

## §3 — Feature Engineering: Forward-Fill to Monthly + Risk Score

PSD is annual, but price data is monthly, so the annual S/U value is **held constant within its marketing year** via forward-fill to month-end:

```python
stu_m = stu_df['stu'].resample('ME').ffill()
risk_m = stu_m.apply(stu_risk_score)
```

This produces 301 monthly points (2000–2025). The latest `stu_risk_score` value is **1.0** — the current 11.6% buffer is already at (or beyond) the risk-scoring function's tight-buffer bound. Merges with `data/ice_kc_monthly.csv` to get a combined monthly frame (216 months) and computes `trail_yoy` (12-month trailing % price change) for the correlation tests in §4.

---

## §4 — Correlation vs ICE KC Price

Three separate views of the same relationship, deliberately kept distinct because they tell different stories:

**1. Level vs. YoY-change correlation (2010–2024, n=180):**

```
r(S/U, price level)      = -0.4048   p=1.7e-08
r(S/U, trailing YoY chg) = -0.0442   p=0.556    <- this is the literal gate metric
```

**2. Lag sweep (0–24 months, S/U leading forward price level):** strongest (most negative) correlation at **lag 23m: r = −0.589**.

**3. Annual-level robustness check** (mean annual price vs. annual S/U, n=15 marketing years): **r = −0.559, p=0.03**.

**Why three views instead of one:** S/U is a slow-moving annual step function. It tracks the price *level* tightly (r=−0.40, strengthening to −0.59 at a 23-month lag) but has almost nothing to say about high-frequency, month-to-month price *momentum* (r=−0.04 on YoY change) — that's a mismatch between what the variable actually measures and what the YoY-change metric is asking of it, not evidence the underlying fundamental is weak.

---

## §5 — Gate Validation: r(S/U, YoY price change) ≤ −0.25

Tests the literal gate as originally specified. **Result: FAIL** — r = −0.0442 vs. the −0.25 threshold required. The supporting evidence (level r=−0.40, annual r=−0.56, best lagged r=−0.59 @ 23m) is printed alongside specifically because the notebook's conclusion (§9) is that the gate metric itself, not the signal, is the problem. A scatter plot of S/U vs. YoY price change with a fitted trend line visualizes just how weak that particular pairing is.

---

## §6 — Rolling Stability

A 3-year (36-month) rolling Pearson correlation between S/U and trailing YoY price change — the same style of stability check used in notebooks 03 and (originally) 05. **Result:** thesis-consistent (negative) sign in only **34/145 windows (23%)**, range **[−0.623, +0.730]** — unstable and frequently sign-flipping.

**Worth flagging:** like the version originally in notebook 05, this check uses the **YoY-change** pairing (the metric §4/§5 already showed is nearly uncorrelated, r=−0.04) rather than the much stronger price-level or 23-month-lagged pairing. So a low positive-window percentage here is expected given what §4 already established, and — as with notebook 05's now-removed rolling-stability section — it isn't strong evidence against the underlying fundamental, which the notebook's own interpretation (§9) argues is real and strong on the level/lag view. If this notebook gets the same walk-forward treatment as 01/02/03/05, this section would be a natural one to reconsider, this time weighting purchases by `stu_risk_score` at the lag where the signal is actually strongest (23m) rather than at YoY-change lag 0.

---

## §7 — Save Reference CSV

Writes `data/stu_monthly.csv` (`date, stu, settle, trail_yoy, stu_risk`) and `data/stu_annual.csv` (`date, stu`) for downstream use.

---

## §8 — Summary

Prints a consolidated summary of all correlation results, the gate outcome, the rolling-stability stat, and restates the target rank order (L1 > L2a > L2b > L3 > L5), noting L2a should be the strongest fundamental signal after price.

---

## §9 — Interpretation & Composite Implication

**The literal gate metric FAILS, but the notebook argues the underlying signal is strong** — two things are true at once:

- r(S/U, trailing YoY change) = **−0.04** → fails the stated gate (≤ −0.25).
- r(S/U, price level) = **−0.40** (p≈1.7e-8); annual-level r = **−0.56** (n=15, p=0.03); best lagged r = **−0.59 @ 23m**. By this view it's one of the strongest fundamentals in the whole signal suite.

**Why the YoY-change metric understates it:** S/U is a slow annual step function — it tracks the low-frequency price *level* tightly but has little to say about high-frequency, mean-reverting *momentum*. The notebook's recommendation (mirroring the precedent set by L1 in notebook 01, which also redefined its evaluation lens after an initial mismatch) is to **redefine the L2a gate around price-level correlation** rather than YoY change. On that basis L2a passes comfortably and preserves the target rank order.

**Composite role:** keep L2a as a core supply input via `stu_risk_score`. The current buffer (11.6%, MY2025) is the tightest in the series → `stu_risk ≈ 1.0`, a strong current BUY-side amplifier. The risk-score bounds (12% → risk 1.0, 35% → risk 0.0) are explicitly provisional in the source docstring and calibrated against this notebook's realized 11.6–23% range.

---

## Key numbers to know

| Metric | Value | Where |
|--------|-------|-------|
| r(S/U, price level) | −0.4048, p=1.7e-8 | §4 |
| r(S/U, trailing YoY change) — literal gate metric | −0.0442, p=0.56 | §4/§5 |
| Best lagged r(S/U, price) | −0.5893 @ 23m | §4 |
| Annual-level r(S/U, price), n=15 | −0.5587, p=0.03 | §4 |
| Gate L2a (r ≤ −0.25 on YoY change) | FAIL (recommend redefining to price-level) | §5 |
| Rolling 3yr r negative (thesis-consistent) | 34/145 windows (23%) | §6 |
| Current world S/U (MY2025) | 11.6% (tightest in series) | §1 |
| Current `stu_risk_score` | 1.0 | §3 |
| Composite role (CLAUDE.md) | Core supply input, redefine gate to price-level basis | — |

Unlike ENSO (notebook 02) and CHIRPS (notebook 05), where the correlation gate result and the walk-forward economic result *diverge* (gate passes/fails but the walk-forward edge is near zero either way), L2a hasn't been walk-forward tested yet — the −0.40 to −0.59 level/lag correlations are considerably stronger than either of those signals' figures, so it's a reasonable hypothesis that L2a would fare better in a walk-forward test too, but that's untested as of this guide.
