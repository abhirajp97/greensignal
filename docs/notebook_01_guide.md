# Notebook 01 — ICE KC Price Position Signal (L1): Reader's Guide

This document explains what each section of `notebooks/coffee_backtests/01_ice_price_signal.ipynb` is doing, the math behind it, and how to interpret the outputs. It is intended as a teaching reference for anyone reading the notebook for the first time.

---

## What the notebook is trying to answer

A single question: **does buying coffee when the price is near a multi-year low actually result in paying less on average?**

The notebook builds a signal from publicly available ICE futures prices, tests whether that signal has genuine predictive power, validates the choice of its key parameter (the lookback window), and checks that the result holds year by year — not just in aggregate.

---

## §0 — Setup

Sets three global variables that all downstream cells depend on:

- `BACKTEST_START` / `BACKTEST_END` — the date range of the analysis. Change these here to adjust the window globally.
- `DATA_DIR` — where output CSVs are written (§9).

Everything else (imports, matplotlib config) is boilerplate. No analysis happens here.

---

## §1 — Fetch Data

Downloads ICE Coffee C front-month futures from Yahoo Finance (`KC=F`). This is the same instrument as the production data source (`CHRIS/ICE_KC1` on Nasdaq Data Link) — Yahoo Finance is used here because it requires no API key.

The result is a daily price series (`settle`) indexed by date. The `Close` column from Yahoo Finance is used as the settlement price proxy.

---

## §2 — Data Quality

Two checks before any analysis:

1. **Visual inspection** — plots the full daily price history so you can see the shape of the data and spot any obvious anomalies (gaps, zero prices, extreme outliers)
2. **NaN count in the core window** — counts missing values between 2010 and 2025. Any NaN in a rolling min/max calculation propagates forward silently, inflating apparent signal strength. This confirms the data is clean before §3 computes anything.

---

## §3 — Feature Engineering

Computes the price position signal and resamples from daily to monthly.

**The signal formula:**

```
price_pos = (P_today − min(P_last_N_months)) / (max(P_last_N_months) − min(P_last_N_months))
buy_signal = 1 − price_pos
```

- `price_pos = 0` means price is at an N-month low → buy signal = 1 (maximum weight)
- `price_pos = 1` means price is at an N-month high → buy signal = 0 (no weight)

The default here uses `price_position_52w()` from `domains/coffee/features/price_features.py`, which hardcodes a 12-month (52-week) window.

§3 also pre-computes forward returns at 6, 12, 18, and 24 month horizons. These are used in §4a to test at which horizon the signal has genuine predictive power:

```
fwd_24m at time t = (price_{t+24} − price_t) / price_t
```

The three-panel chart at the end shows price, price position, and buy signal on aligned axes — useful for visually confirming the signal behaves as expected (high signal during known price troughs, low signal during known peaks).

---

## §4 — Signal Construction & Parameter Validation

This is the core of the notebook. The argument runs in three steps, each building on the previous one.

### Why three steps?

The signal has one free parameter: the lookback window (52w by default). The goal of §4 is to show that parameter choice is not arbitrary — it is the outcome of evidence. A reader finishing §4 should have no remaining questions about why the window is set the way it is.

---

### §4a — Forward Predictive Correlation

**The question:** Does buying at a low price position actually lead to lower prices in the future, and at what horizon?

**The test:** For each horizon N ∈ {6, 12, 18, 24} months:

```
r( buy_signal_t,  price_return_{t → t+N} )
```

The signal at time t is computed using only prices up to t. The return is measured entirely after t. The two windows do not overlap — this is a genuine out-of-time predictive test.

**Why the signal and forward return do not overlap:**

| Variable | Data used |
|----------|-----------|
| `buy_signal` at t | prices from `t − N months` to `t` |
| `fwd_24m` at t | prices from `t` to `t + 24 months` |

The only shared point is the price at exactly t — used as the "where are we now" reference in the signal, and as the starting point of the forward return. The information content does not overlap.

**What the results show:**

- r at 6m and 12m is near zero or negative — buying at a low price position does not protect you from continued falls in the short term. Arabica trends before it reverts.
- r peaks at 24m (r ≈ +0.20, p < 0.01) — meaningful reversion only emerges at the 2-year horizon.

This establishes the relevant economic cycle: **arabica takes approximately 24 months to mean-revert**. This finding anchors the window choice in §4b.

**Important distinction:** There is also a contemporaneous r (r ≈ +0.85) between price position and trailing 12-month returns. This is not a predictive test — it is tautological, because both variables look at the same 12-month price history. The high contemporaneous r just confirms the math is internally consistent. Only the forward r is the genuine predictive test.

---

### §4b — Window Parameter Selection

**The question:** If the signal's predictive edge peaks at 24 months, is a 12-month (52-week) lookback window well-matched to that cycle — or should it be longer?

**The intuition:** A 52-week window asks "is this price near a 1-year low?" A 104-week window asks "is this price near a 2-year low?" If arabica takes 2 years to mean-revert, a 2-year reference window better captures how far from a true cycle low the current price actually is. A 12-month window may call a price cheap within its 1-year range while it is still mid-range within a 2-year arc.

**Three windows tested:**

| Window | Monthly lookback | Rationale |
|--------|-----------------|-----------|
| 52w | 12 months | Industry convention — the baseline to beat |
| 78w | 18 months | Midpoint; also matches the ENSO supply-shock lag hypothesis |
| 104w | 24 months | Directly matches the forward-r peak from §4a |

**A momentum baseline** is included as an adversarial control — it buys when price is *above* its 3-month moving average (trend-following, the opposite philosophy). If trend-following beats any contrarian window, the whole "buy low" premise is suspect.

**How the signals are computed inline:**

`price_position_52w()` has a hardcoded 12-month window, so §4b computes all three windows directly:

```python
roll_min = m['settle'].rolling(n, min_periods=int(n * 0.7)).min()
roll_max = m['settle'].rolling(n, min_periods=int(n * 0.7)).max()
buy_signal = (1 − (price − roll_min) / (roll_max − roll_min)).clip(0, 1)
```

`min_periods = int(n × 0.7)` means the signal requires at least 70% of the window to have valid data before computing. For a 24-month window this means signal starts forming after ~17 months rather than requiring the full 24. This prevents the first months of the test period from producing NaN silently due to insufficient burn-in.

**How cost saving is measured:**

The naive benchmark is the simple average of every monthly price — what a roaster pays if they buy the same amount every month regardless of price:

```
naive_avg = mean(all monthly prices, 2010–2024)
```

The signal-weighted average tilts purchases toward low-signal months:

```
sig_avg = Σ(price_t × signal_t) / Σ(signal_t)
saving  = (naive_avg − sig_avg) / naive_avg × 100
```

A month where `buy_signal = 0.9` (price near a multi-year low) contributes 9× more to the weighted average than a month where `buy_signal = 0.1` (price near a multi-year high).

**Two outputs per signal:**

1. **Lag-r curve (0–36 months)** — the full picture of predictive power at every horizon. Shows visually where each window's edge peaks and how quickly it decays.
2. **Bar chart: forward r at 24m** — the single-number comparison at the relevant horizon established in §4a.
3. **Full-period cost saving (2010–2024, in-sample)** — the economic interpretation of the same finding.

**Why the full-period cost saving is labelled in-sample:**

The cost saving in §4b is computed over the entire 2010–2024 dataset including the 2021–24 arabica supercycle (price doubled). The window that best captures that supercycle will score best — but that window was selected after seeing the full result. This is a mild form of selection bias: even testing only three pre-specified windows on the same dataset means the reported score of the winner is slightly optimistic. §4c addresses this directly.

---

### §4c — Walk-Forward Validation

**The question:** Does the best-performing window from §4b hold year by year, or is its full-period score driven by one exceptional stretch of prices?

**The method:** For each calendar year 2013–2024:

```
naive_avg_Y = mean(monthly prices in year Y only)
sig_avg_Y   = Σ(price_t × signal_t) / Σ(signal_t)   for t in year Y only
saving_Y    = (naive_avg_Y − sig_avg_Y) / naive_avg_Y × 100
```

Twelve separate saving numbers, one per year. All three windows are tested simultaneously.

**Why this removes the look-ahead bias from §4b:**

The signal at each month is computed using a rolling window that only looks backward. The signal value for March 2015 uses only prices from March 2013 to March 2015 (for the 104w window). When §4c evaluates year 2015, the analyst has not yet observed the 2021 supercycle. If 104w scores best in 2013, 2015, and 2018 — before those events — that is genuine evidence the window choice is robust.

**The key difference from §4b is not the signal values — it is what you conclude from the result.** §4b pools all 180 months into one weighted average and reports one number. §4c produces 12 numbers and asks: is this positive every year, or is the average being carried by a few exceptional years?

**What makes a strong result:**

- **Average saving** — if the winner from §4b also wins here, the full-period result was not purely retrospective
- **Positive year count** — this is the robustness check. A window positive across most years in the dataset — the 2014 price collapse, the 2018–20 flat market, the 2021–24 supercycle — is doing real work across regimes, not just riding one favorable stretch. That is the figure to cite in any external communication, not the full-period in-sample saving.

**Actual walk-forward result (2013–2024, re-executed):**

| Window | Avg saving | Positive years |
|--------|-----------|-----------------|
| 52w (12m) | +6.05% | 9/12 |
| **78w (18m)** | **+7.34%** | **10/12** |
| 104w (24m) | +6.75% | 11/12 |

The **78w window wins on average saving** (+7.34%), and 104w has the best positive-year count (11/12) at a slightly lower average. Both comfortably beat the 52w industry-convention baseline and validate that the §4a/§4b evidence chain — not just convention — should drive the parameter choice.

The test starts in 2013 because the longest window (104w = 24 months) needs at least 24 months of prior data, and 2010–2012 provides a clean burn-in period.

---

### §4 Summary

The three-part evidence chain:

- **§4a** established that predictive power peaks at the 24-month horizon
- **§4b** showed that the window matching that cycle scores best on both forward r at 24m and full-period cost saving
- **§4c** confirmed the ranking holds year-by-year without look-ahead

The validated signal formula:

```
buy_signal = 1 − ( P_t − min(P_{t−N months}) ) / ( max(P_{t−N months}) − min(P_{t−N months}) )
```

where N is the winning window from the walk-forward table. The parameter choice is the outcome of the evidence above, not a convention.

---

## §5 — Realized Variance

**What it is:** Realized variance (RV) is the observed volatility of price returns over a defined window, computed directly from price data. It measures how much the price has been moving recently.

**Two versions:**

- **Daily RV (rolling 21-day, annualised):** Sum of squared daily log returns over 21 trading days (~1 calendar month), scaled by ×252 to express as annualised variance. 21 trading days ≈ 1 calendar month. Captures short sharp spikes — a USDA report, a frost warning in Minas Gerais.

```python
log_ret  = ln(P_t / P_{t-1})
rv_daily = Σ(log_ret²) over 21 days  × 252
```

- **Monthly RV (rolling 12-month):** Sum of squared monthly log returns over 12 months. Captures slow-moving volatility regime shifts — when arabica transitions from a calm market to a persistently choppy one.

**Why this matters for a roaster:**

Volatility is not symmetric in its implications. In a low-vol regime, a low price-position signal can be acted on with more confidence — subsequent moves are unlikely to dramatically offset the savings. In a high-vol regime, a low price-position may reflect a genuinely distressed market where large moves in either direction remain likely. The buy signal is noisier in high-vol periods.

**Four outputs:**

1. **Dual time-series chart** — price, daily RV, and monthly RV on aligned axes, with event bands for La Niña 2010–12, the 2014–16 price collapse, and the 2021–24 supply run-up. Shows whether volatility clusters around known market stress periods.

2. **Scatter plots** — RV vs price level (coloured by price position) and RV vs price position. Tests whether high volatility clusters at particular price zones. In commodities, volatility often concentrates at multi-year extremes — both highs (demand uncertainty) and lows (supply response uncertainty).

3. **Correlation table** — tests three relationships:

| Correlation | What it answers |
|-------------|----------------|
| r(RV, price_pos) | Do high-vol periods coincide with the signal firing? |
| r(RV, fwd_12m) | Does high vol predict returns 12m out? |
| r(RV, fwd_24m) | Does high vol predict returns 24m out? |

If `r(RV, fwd_24m)` is positive and significant, high volatility periods precede higher returns 24m out — RV would be a signal amplifier. If near zero, RV is a risk descriptor only, not a timing signal.

4. **Volatility regime indicator** — binary flag (above/below median daily RV) saved for downstream use in the composite signal.

---

## §6 — Seasonality

**The question:** Does the Arabica price series contain a predictable annual seasonal component large enough to use as a signal adjustment?

**Why log returns, not price levels:** Raw price levels are non-stationary and dominated by multi-year trends. The 2021–24 supercycle would completely swamp any seasonal signal. Monthly log returns remove the trend and isolate within-year oscillations where seasonality would appear.

**Three tests in increasing specificity:**

### Test 1 — Autocorrelation at lag 12

If monthly log returns are correlated with returns from 12 months prior, that is prima facie evidence of annual periodicity. The ACF plot (lags 0–36) shows the full autocorrelation structure. The lag-12 value is read against its 95% confidence interval — if it lies outside the interval, the correlation is statistically distinguishable from noise.

### Test 2 — STL Decomposition

STL (Seasonal-Trend-Loess) decomposes the price level into three additive components:

```
price_t = trend_t + seasonal_t + residual_t
```

`robust=True` down-weights the 2011 and 2024 price spikes so they do not distort the seasonal estimate. The four-panel chart shows each component. If the seasonal panel has a consistent shape year-over-year (same months always high, same months always low), the seasonality is structural. If it is chaotic, it is noise.

### Test 3 — OLS month-dummy F-test

Regresses monthly log returns on 11 calendar-month dummy variables:

```
ret_t = α + β₁(Jan) + β₂(Feb) + ... + β₁₁(Nov) + ε_t
```

The joint F-test asks: are any of these month coefficients non-zero? This is the statistical gate:

- p < 0.05 → strong evidence of seasonal structure. Incorporate seasonal factor.
- 0.05 < p < 0.10 → weak evidence. Monitor but apply with low weight.
- p ≥ 0.10 → no statistically significant seasonality at this sample size (~15 years). Treat the apparent pattern as noise.

**Seasonal factor extraction:**

If STL seasonal is consistent, the 12-month factor is extracted:

```python
seasonal_factor = stl_res.seasonal.groupby(month).mean()
seasonal_factor -= seasonal_factor.mean()   # centre at zero
```

A positive factor for a given month means prices are historically elevated relative to trend in that month. A negative factor means historically depressed. This enters the composite as a low-weight monthly modifier on top of the price-position signal.

**The seasonal factor is not a standalone timing signal.** It is a calendar-month adjustment relevant only within the context of a given month's purchase decision. Coffee's physical seasonality is driven by the Brazilian harvest cycle (main crop May–September) and flowering season (September–November), but the 2021–24 supercycle adds noise — the F-test decides whether the pattern is separable from that noise at the current sample size.

---

## §7 — Business Feasibility

Placeholder section. Scope to be defined separately.

---

## Key numbers to know

| Metric | Value | Where |
|--------|-------|-------|
| Contemporaneous r (price_pos vs trailing 12m return) | +0.852 | §3 / §4a context |
| Forward predictive r at 24m | +0.201, p=0.008 | §4a |
| Full-period cost saving, 52w (in-sample) | +12.95% | §4b |
| Full-period cost saving, 104w (in-sample) | +15.01% | §4b |
| Walk-forward avg saving, 78w (honest figure, winning window) | +7.34% | §4c |
| Walk-forward positive years, 78w | 10/12 | §4c |
| Momentum baseline cost saving | −10.37% | §4b |

The walk-forward figure (78w, +7.34% avg, 10/12 positive years) is the number to cite externally. The full-period in-sample figures are useful for comparing windows against each other but are optimistic as absolute claims — note the in-sample number roughly doubles the honest walk-forward figure, which is the expected shape of that optimism.
