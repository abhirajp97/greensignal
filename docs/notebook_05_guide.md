# Notebook 05 — CHIRPS Rainfall Signal (L3, SPI rebuild): Reader's Guide

This document explains what each section of `notebooks/coffee_backtests/05_chirps_signal.ipynb` is doing, the math behind it, and how to interpret the outputs. It is intended as a teaching reference for anyone reading the notebook for the first time.

**Note on history:** this notebook has been rebuilt twice. The original version used a raw millimeter rainfall anomaly, tested monthly (gate narrowly FAILED, r=+0.10 @ 14m). A later rebuild (2026-07-02) switched to a gamma-fit Standardized Precipitation Index (SPI) tested on an annual crop-year frame (gate PASSES, r=+0.483) — that SPI rebuild is what Sections 0–5 below describe. Sections 6 onward were rebuilt again in this session, replacing an earlier robustness-study design and a since-discarded standalone walk-forward with a walk-forward that layers the SPI drought signal on top of the validated L1 price-position signal, tested with a genuinely no-look-ahead calibration.

---

## What the notebook is trying to answer

Three questions, answered in sequence:

1. **Does a dry flowering season (Sep–Nov) in Minas Gerais predict higher Arabica prices, and at what lag?** (Sections 1–5)
2. **Does that correlation actually save money when turned into a purchasing rule** — specifically, as an amplifier layered on top of the already-validated L1 price-position signal, the way it would really be used in the product? (Section 6)
3. **Does the benefit hold up when tested honestly, year by year, the way someone actually running this model live would experience it** — not just as one number computed after the fact? (Section 6, sequential simulation)

---

## §0 — Setup

Imports, `.env` loading. Pulls in only `is_flowering_month` from `chirps.py` at the top; `fetch` is imported conditionally later, only if Google Earth Engine is available.

## §1 — Fetch CHIRPS Data

Tries a live GEE fetch first; falls back to the cached `data/chirps_minas_monthly.csv` if `EARTHENGINE_PROJECT` isn't set or the fetch fails. 216 months, 2008–2025, range [4.4, 353.6] mm.

## §2 — Data Quality + Seasonality

Standard sanity checks (no NaN/negative rainfall). Climatology confirms wet Nov–Mar (~150–240mm), dry Jun–Aug (~9–11mm), with the Sep–Nov flowering months sitting in the dry-to-wet transition.

## §3 — SPI Feature Engineering

**Standardized Precipitation Index.** Rather than a plain z-score `(x − mean)/std`, SPI fits a gamma distribution to the historical rainfall values (rainfall is bounded at zero and right-skewed, so a normal-distribution z-score misstates how rare an event actually is — especially on the dry/left tail, which is exactly what this signal cares about), maps the observation through that gamma's CDF to get its true percentile, then converts that percentile to a standard-normal z-score via `norm.ppf`. A zero-precipitation probability mass correction (`q`) handles months with literally no rain, since a continuous gamma can't represent an exact zero.

```
SPI ≈ 0     → median rainfall
SPI ≈ -1.0  → ~1-in-6 dry
SPI ≈ -1.5  → ~1-in-15 dry (severe)
SPI ≈ -2.0  → ~1-in-40 dry (extreme)
```

Two variants are built: **SPI-3** (a rolling 3-month accumulation, standardized per calendar month it ends in — November's SPI-3 is exactly Sep+Oct+Nov's combined total, standardized against other years' Sep+Oct+Nov totals) and **SPI-1** (single-month, no accumulation).

## §4 — Flowering-Season Deficit Feature

Builds the annual (one-row-per-crop-year) features:

- **`flowering_spi3`** — November's SPI-3 value (signed; negative = dry).
- **`flowering_drought`** = `max(0, −flowering_spi3)` — the **primary** feature. Clamped so every wet/normal year reads exactly 0.00 — a dry flowering season is treated as a real supply shock, but a wet one isn't treated as symmetrically bullish/bearish.
- **`monthly_deficit`** — a variant that standardizes each of Sep/Oct/Nov *separately*, then sums only the negative (dry) months' contributions. Unlike the SPI-3 form, a wet month can never offset a dry one in this construction.

## §5 — Annual Signal vs Forward Price (primary correlation test)

Correlates each crop-year's flowering signal against the price change over the following 12 months (Nov Y → Nov Y+1):

```
SPI-3 deficit (PRIMARY)   r=+0.483  p=0.069  spearman=+0.290  n=15
monthly-SPI deficit       r=+0.380  p=0.162  spearman=+0.139
raw signed SPI-3          r=-0.412  (sanity check — same relationship, opposite sign)
```

The clamped deficit form beats the raw signed form, and beats the monthly-deficit variant — both consistent with the notebook's mechanistic claims (asymmetric drought risk; the flowering season's *net* moisture balance matters more than any single dry patch that a wet month elsewhere might offset). A **tercile event study** (splitting the 15 years into driest/normal/wettest thirds) is a correlation-free cross-check: driest third averaged +33.6% forward, wettest averaged +9.5% (Welch t=+1.07).

**Caveats surfaced in discussion, worth carrying forward:** Spearman rank correlation (+0.290) is substantially weaker than Pearson (+0.483) for the primary signal, suggesting the Pearson number may be partly driven by one or two extreme years rather than a cleanly monotonic relationship. Each year's severity reading is itself derived from only 3 raw monthly rainfall values, calibrated against only ~17 other years — a thin construction that compounds with the already-small n=15 correlation sample. Severity does appear to carry real information (isolating the 6 historical drought years, magnitude alone correlates with forward price at r=+0.735), but that finding rests on n=6 and shouldn't be over-trusted on its own.

---

## §6 — Walk-Forward: L1 Price Signal + No-Look-Ahead SPI-3 Drought Amplifier

This section was rebuilt in this session. The original version tested the SPI signal **standalone**, with a continuous severity-scaled weight (`1.0 + min(1, flowering_drought/2.0)`), bucketed **per calendar year**. Both of those choices turned out to be flawed:

- **Per-year bucketing can't detect an annually-updating signal.** `flowering_drought` only changes once a year, so within any single calendar year the purchase weight is nearly constant — and a constant weight cancels out of a weighted average exactly (`weighted_avg = Σ(price × c)/Σc = Σprice/n = naive_avg`, regardless of the constant's value). The original per-year walk-forward showed years with a big weight boost (e.g. 2020 at ~1.5x for the whole year) producing essentially 0% saving anyway — not because the signal was bad, but because the metric was structurally blind to it.
- **Standalone testing doesn't match how the signal would actually be used.** L3 is meant to be an *amplifier* on top of L1, not an independent timer.

### The redesign

**Base signal:** L1's 78-week price-position window — notebook 01's own validated walk-forward winner (+7.34% avg saving, 10/12 positive years) — recomputed directly on ICE KC settle prices (`price_position_52w()` only exposes the default 12-month window; the 78w version needs the same inline rolling-min/max formula notebook 01 used).

**No-look-ahead SPI-3.** Sections 3–5's SPI-3 was calibrated on the *entire* 2008–2025 record — a look-ahead violation for a backtest (2016's drought score would have been computed knowing about 2023's drought too). Section 6 refits the gamma for every test year using only strictly-prior years, expanding as history accrues:

```
prior_years(Y)  = all years < Y
spi3_nolook[Y]  = spi_from_gamma(Y's Sep+Oct+Nov total, prior_years(Y)'s totals)
```

At least 8 prior years are required before a year gets scored at all — which makes **2008–2015 a pure calibration baseline** and **2016 the first live, walk-forward-tested year**, with no year ever scored against data it couldn't have had at the time.

**Binary flag, not severity-scaled.** `drought_flag[Y] = 1` if `spi3_nolook[Y] ≤ −1.0` (moderate-to-severe, the "~1-in-6 dry" bound from Section 3's own interpretation scale), else 0. This is a deliberate simplification: severity does appear to carry real information (§5's r=+0.735-within-drought-years finding), but that rests on only 6 historical drought years — not enough to validate a graded weighting scheme with any confidence. A plain "any dryness at all" threshold was already shown too weak on its own (binary-vs-continuous check: r=+0.216, not significant), so −1.0 sits deliberately between those two extremes.

**Weight rule:**

```
weight_t = buy_signal_78w_t × (1 + drought_flag[signal_year(t)])
```

The full L1 signal, doubled for the 12 months following a flagged flowering season (Dec Y through Nov Y+1), unchanged otherwise.

**Pooled, not per-year, comparison.** Given the per-year cancellation problem above, the walk-forward pools the entire test window into one weighted average and compares it against one naive average over the same months — rather than computing 8 separate near-meaningless per-year percentages and averaging them. A descriptive (non-headline) per-crop-year table is still shown for transparency.

### Results

```
Pooled 2017-2024 (96 months):
  L1 alone (78w)        : +20.39% saving vs naive
  L1 x SPI drought amp  : +21.34% saving vs naive
  Marginal effect       : +0.95pp

Excluding 2023-2024 (72 months):
  L1 alone              : +16.54%
  L1 x SPI drought amp  : +17.27%
  Marginal effect       : +0.73pp
```

**Important: the L1-alone figure here (+20.39%) is not comparable to notebook 01's own headline (+7.34%).** These are different metrics. Notebook 01 averages *per-year* savings (each normalized within its own year, capturing only within-year timing). This notebook pools the *entire* multi-year span into one weighted average, which additionally captures *between-year* effects — L1's 78-week rolling window drifts slowly across price regimes, so pooling lets it get credit for buying less across the entire expensive 2024 supercycle block, not just for good timing within any single year. Don't read +20.39% as "L1 performs 3x better than previously found" — it's answering a related but different question.

**Why the per-crop-year descriptive table shows L1 and L1×Amp as identical in every row:** this is expected, not a bug. Within any single crop-year block, the amplifier is a constant (×1 or ×2 for the whole block), and a constant multiplier cancels out of *that block's own* average — the same fact that broke the original per-year design. The real effect only emerges when pooling *across* blocks: a flagged (×2) block contributes twice the weight-mass to the combined average that an unflagged block would, and in this data the flagged years (2017, 2019, 2020) happened to be relatively cheap ones, so amplifying them pulls the pooled average down further.

### Sequential simulation — "how would this have looked running live"

A follow-up rebuild of the same test, run as an explicit year-by-year loop rather than a single static computation — mirroring how someone actually using this model would experience it (recalibrate once a year using the already-correct no-look-ahead SPI, observe the running cumulative result). Since an isolated single year can't show the amplifier's effect (same cancellation issue as above), what's tracked is the **cumulative** weighted average from the start of the test window through the end of each successive crop year:

```
Year   SPI3(no-look)  Flag  Months  Cum L1%  Cum L1xAmp%  Marginal(pp)
2016       -0.41        0     11     0.27       0.27          0.00
2017       -1.35        1     23     0.53       2.99         +2.45   <- biggest single jump
2018        1.02        0     35     0.71       0.94         +0.24
2019       -1.82        1     47     0.76       1.18         +0.42
2020       -1.76        1     59     7.87       7.94         +0.06   <- flagged, barely moved
2021        1.96        0     71    16.70      17.30         +0.61
2022        0.52        0     83    15.52      17.26         +1.74
2023       -2.20        1     95    19.54      20.49         +0.95   <- flagged, giveback vs 2022
2024        0.72        0     96    20.39      21.34         +0.95
```

The final row matches the static pooled result exactly (+21.34%), confirming the two computations are consistent.

**The real finding: the benefit is concentrated in one episode, not a steady accrual.** Almost the entire marginal edge appeared in a single jump right after the *first* flagged year (2017: +2.45pp) — the amplifier made one well-timed call (2017 turned out to be a genuinely cheap year to buy more in) and has given back some of that ground since. The subsequent flagged years contributed far less: 2020 barely moved the cumulative marginal at all (+0.06pp), and 2023's flag actually coincides with the marginal *shrinking* relative to where it stood after 2022 (+1.74pp → +0.95pp), since 2023 sat in the leadup to the 2024 price spike rather than a cheap buying window. Of the 5 historical drought flags observed live (2017, 2019, 2020, 2023, and 2025 which hasn't resolved yet), only one clearly paid off — consistent with everything else found about this signal: real, mechanistically sound, but thin and single-episode-dependent rather than a dependable year-in-year-out amplifier.

---

## §7 — Save Reference CSVs

Writes the monthly rainfall+SPI columns to `data/chirps_minas_monthly.csv`, and the annual flowering features + forward returns to `data/05_flowering_annual.csv`.

## §8 — Summary

Consolidates the §5 correlation evidence and the §6 walk-forward result (pooled, both cuts) into one printed block, with an adaptive verdict line based on whether the marginal effect is positive.

## §9 — Scope: Adopted vs Deferred

Documents what was adopted in the SPI rebuild and in this session's walk-forward redesign (no-look-ahead calibration as the backbone, binary flag, L1 amplifier framing), and what remains explicitly deferred: the full climate sub-score combining L3+ENSO+Vietnam monsoon (→ composite notebook 06), a new-crop futures contract as target (needs paid data), a Granger causality test (n=15 too small), severity-graded amplifier weighting (tried, dropped — n=6 too thin to validate), and the partial-correlation-vs-stocks-to-use robustness check (present in an earlier version of this notebook, not currently reinstated).

---

## Key numbers to know

| Metric | Value | Where |
|--------|-------|-------|
| Best correlation, SPI-3 deficit vs fwd-12m price | r=+0.483, p=0.069, n=15 | §5 |
| Gate (annual r ≥ +0.30) | PASS | §5 |
| Tercile dry vs wet flowering | +33.6% vs +9.5% fwd-12m | §5 |
| No-look-ahead calibration baseline | 2008–2015 (8yr); live from 2016 | §6 |
| Drought threshold | SPI-3 ≤ −1.0 (binary) | §6 |
| Pooled walk-forward, L1 alone (2017–2024) | +20.39% | §6 |
| Pooled walk-forward, L1 × SPI amp | +21.34% | §6 |
| Marginal effect of SPI amplifier on L1 | +0.95pp (full), +0.73pp (excl. 2023–24) | §6 |
| Sequential simulation verdict | Benefit concentrated in one episode (2017); later flags contributed little or gave back ground | §6 |

**The marginal amplifier effect is real, positive, and survives the 2023–24 exclusion — but the sequential simulation shows it isn't a steady, reliable edge.** It's driven almost entirely by one well-timed flag (2017), with the other flagged episodes (2020, 2023) contributing far less. Treat this the same way as ENSO and COT's isolated walk-forward results: directionally encouraging, mechanistically sound, but built on too few independent episodes (5 flagged years total) to be a confident standalone input. The pooled L1-alone figure (+20.39%) should not be compared directly to notebook 01's own walk-forward headline (+7.34%) — they measure different things (cross-year + within-year effects vs. within-year only).
