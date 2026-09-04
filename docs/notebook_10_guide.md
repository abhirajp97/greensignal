# Notebook 10 — ML Composite Model: Reader's Guide

This document explains what `notebooks/coffee_backtests/10_ml_composite_model.ipynb` is doing, the math behind it, and — most importantly — what it found. Unlike notebooks 01–05 (each validating one signal), this notebook asks a different question: **can a tree-based model learn to combine all five validated signals itself, and does that beat the existing hand-specified composite formula?**

The honest short answer: not yet, and the notebook spends most of its length explaining precisely *why*, which turns out to be more useful than the headline number.

---

## What the notebook is trying to answer

Three questions, in sequence:

1. **Can XGBoost/LightGBM/RandomForest learn a genuinely predictive relationship between the five signals and forward Arabica price movement**, validated with a leakage-safe time-series cross-validation?
2. **Does that predictive skill translate into actual purchasing savings**, tested against a real constrained inventory simulation (a user-configurable monthly usage, storage cap, and budget) — not just a correlation?
3. **When it doesn't, why not — and can the problem be fixed**, either by changing how the model's prediction is turned into a purchase decision, or by changing how the model is trained?

---

## §0–2: Setup and Feature Engineering

Builds one row per month from 2008 onward, assembling 15 causal features across all five validated signals plus one new one:

- **L1 (price)**: `price_pos_52w`, `price_pos_78w`, `price_pos_104w` — all three windows from notebook 01, fed as separate columns rather than picking one upfront.
- **L2a (stocks-to-use)**: `stu_wmt` — the true-vintage semiannual series from notebook 04 (CLAUDE.md's stronger evidence, Gate 1 r=−0.488), forward-filled to monthly. Not the look-ahead-contaminated PSD bulk series.
- **L2b (ENSO)**: six separate ONI lag columns (0, 6, 12, 15, 18, 24 months) rather than pre-committing to the single ~15m lead validated in notebook 02 — lets the trees discover which lag is useful.
- **L3 (CHIRPS/SPI)**: `spi3_nolook`, `flowering_drought_nolook` — rebuilt from raw rainfall using notebook 05 §6's no-look-ahead expanding-window gamma calibration, but with `MIN_PRIOR_YEARS` reduced from notebook 05's `8` to `2`. This makes the first live CHIRPS year **2010** instead of 2016, matching COT's own hard start (the disaggregated report doesn't exist before 2010) — so COT becomes the binding constraint on training history, not CHIRPS. Explicitly **not** the cached `05_flowering_annual.csv` columns, which notebook 05 itself found were calibrated on the full sample (a genuine look-ahead violation for a backtest).
- **L5 (COT)**: `cot_index` — already causal (156-week trailing window).
- **New: realized volatility** — `rv_daily` (21-trading-day rolling, ×252 annualized) and `rv_monthly` (12-month rolling), exact formulas from notebook 01 §5. Not used in any prior notebook's composite.

**§2h (look-ahead sanity check)** prints the first-valid date of every column before any model sees the data — confirms nothing starts earlier than it legitimately could. Result: **174 usable months (2010-12 to 2025-05)**, split into **133 training months (2010–2021)** and a **36-month test window (2022–2024)**.

---

## §3: Time-Series-Safe Cross-Validation

`TimeSeriesSplit` (5 splits, expanding window) with a **2-month embargo** dropped from the end of each fold's training set before validation — several features (`rv_monthly`, `cot_index`'s 156-week window) are rolling constructions, so a validation row's near-neighbor could otherwise leak across the train/validation boundary if not embargoed. Operates only on the 2010–2021 training data; the 2022–2024 test window is never touched here.

Three models trained identically: **XGBoost** (primary, per the original ask), **LightGBM**, **RandomForest**.

---

## §4: Final Fit + Prediction-to-Multiplier Transform

Refits each model on the full training window, predicts forward 12-month return (`fwd_12m`) for every test month, then converts that prediction into a purchase multiplier via a z-score against the *training set's own* prediction distribution (never the test period's — kept causal), mapped to **[0, 2]** centered at 1.0.

**Real predictive skill, confirmed out of sample:**

| Model | Test r(predicted, actual `fwd_12m`) |
|---|---|
| XGBoost | +0.421 (p=0.011) |
| LightGBM | +0.329 (p=0.050) |
| RandomForest | +0.203 (p=0.234) |

---

## §5: Constrained Walk-Forward Simulation

The economic test, and the reason this notebook exists as a separate track from notebook 06's composite. Unlike every prior notebook's `cost_improvement_backtest` (which forces total purchase volume to exactly match naive by construction — it's a purely relative metric), this simulates a **real inventory** with a user-configurable monthly usage rate, storage capacity, and budget:

```
Each month:
  target_buy = usage_kg * multiplier(signal)
  room_left  = storage_cap_kg - current_inventory
  afford_max = budget / current_price
  buy = clip(target_buy, 0, min(room_left, afford_max))
  inventory += buy - usage_kg
  cost += buy * current_price
Naive: buy = usage_kg every month, same storage/budget caps applied
```

**A real bug was caught and fixed here**: the first implementation compared a dollar budget directly against price quoted in USc/lb without unit conversion, silently collapsing every scenario to an identical "0.00% saving" regardless of strategy. Fixed with an explicit USc/lb → $/kg conversion (`× 1/45.3592`).

**Two illustrative scenarios** (small roaster: 200kg/mo, 600kg storage, $1500 budget; larger operation: 1000kg/mo, 2000kg storage, $6000 budget) — units are illustrative for this proof-of-concept, not calibrated to real green-coffee pricing.

**Result: every ML model lost to naive buying**, despite having real forecast skill:

| | Small roaster | Larger operation |
|---|---|---|
| XGBoost | −1.46% | −1.38% |
| LightGBM | −1.54% | −1.63% |
| RandomForest | −1.32% | −1.37% |

---

## The diagnostic: why does a genuinely predictive model lose money?

This is the core finding of the notebook. The multiplier from each model correlates **positively** with the *contemporaneous* price:

```
r(purchase multiplier, contemporaneous price):
  XGBoost        r=+0.430  p=0.009
  LightGBM       r=+0.446  p=0.006
  RandomForest   r=+0.405  p=0.014
```

The models buy **more** precisely when price is **already elevated** — anticipating a further rise (momentum) — rather than buying more when price is cheap (value). Being right about the future direction doesn't by itself lower what you pay *today* if the purchase happens into an already-expensive month. This is the exact same momentum-vs-value mismatch found for the COT signal in notebook 03.

**Root cause, confirmed via feature importances**: `price_pos_52w` — the one feature independently validated to beat naive buying on its own (notebook 01, +7.34% walk-forward) — ranked **last or near-last** in every model's feature importances (0.3–5%), dwarfed by CHIRPS and ONI features (up to ~27% combined). The model is trained to minimize forecast error on `fwd_12m`, not to time cheap purchases — so it leans on whichever features best explain *that* target during training, and price position turns out to be weakly predictive of 12-month-forward returns in this data (consistent with notebook 01's own finding that Arabica's mean-reversion signal is close to zero at 12 months and only emerges at 24 months).

The critical distinction: **having a feature available as model input is not the same as the model being optimized to rely on it.** The tree only uses what reduces its actual training loss, and value-timing was never what it was asked to optimize for.

---

## §6: Comparison vs. the Legacy Hand-Specified Composite

Builds the CLAUDE.md canonical formula (`multiplier = (1.5 - price_position) × (1.0 + 0.65 × climate_risk_score)`) using the real production risk-score functions from `domains/coffee/sources/*`, run through the identical Sec 5 simulation:

```
Small roaster:     Legacy +4.82%  |  Best ML -1.32%
Larger operation:  Legacy +3.94%  |  Best ML -1.37%
```

The documented formula — built to be large exactly when price is cheap, regardless of any forecast — beats every ML model tried.

---

## §7: Three Attempted Fixes for the Momentum/Value Mismatch

Three interventions, at three different points in the pipeline, testing whether the ML approach can be salvaged.

### 7a. Fix 1 — blend the ML forecast into a value-first skeleton (output-transform level)

```
value_factor   = 1.5 - price_pos_52w
ml_risk_score  = clip((z + z_cap) / (2 * z_cap), 0, 1)
multiplier_v1  = clip(value_factor * (1.0 + 0.65 * ml_risk_score), 0, 2)
```

Structurally identical to the legacy formula, with `climate_risk_score` replaced by an ML-derived risk score — the ML forecast becomes an *amplifier* on a value-first base, not the sole driver.

**This worked.** The momentum correlation flipped from ~+0.42 to **~−0.73** (all three models — now buys more precisely when price is *low*), and the walk-forward result flipped from losing to winning:

```
Small roaster:     +3.82% to +3.84%   (vs. legacy's +4.82%)
Larger operation:  +3.01% to +3.05%   (vs. legacy's +3.94%)
```

Within about 1 percentage point of the legacy formula, while still letting the genuine ML forecast skill contribute.

### 7b. Fix 2 — monotonic constraints (tree-structure level)

Forces `price_pos_52w/78w/104w` to a strictly non-increasing relationship with the predicted return (XGBoost's `monotone_constraints`, LightGBM's equivalent, scikit-learn 1.4+'s `RandomForestRegressor(monotonic_cst=...)`) — no output blending, same `to_multiplier()` transform as the original model. Tests whether constraining the tree's own structure, without touching the output, is enough on its own.

**This did not work.** Momentum correlation barely moved (+0.34 to +0.40, vs. +0.40 to +0.45 originally), and the walk-forward result stayed negative (−1.1% to −1.4%) — statistically indistinguishable from the unconstrained model.

### 7c. Fix 3 — feature-weighted column sampling (tree-structure level, XGBoost only)

Biases which features get considered as split candidates (XGBoost's `feature_weights`, 5× weight on the three `price_pos_*` columns) — increases the *opportunity* for price position to be used without forcing a direction. LightGBM and scikit-learn's RandomForest have no equivalent mechanism, so this fix is XGBoost-only.

**This did not work either.** Momentum correlation was essentially unchanged (r=+0.450, same as the original XGBoost's +0.430), and the walk-forward result was, if anything, slightly *worse* (−1.4% to −1.6%). `price_pos_104w`'s feature importance rose modestly (0.068→0.100) but `price_pos_52w`/`78w` barely moved despite 5× more sampling chances.

### Why the tree-structural fixes failed where the output-transform fix worked

Both Fix 2 and Fix 3 can only **increase the opportunity or constrain the direction** of how `price_pos` gets used inside the tree — neither can force the model to actually *rely* on it if doing so doesn't reduce training error. The model is fit to minimize forecast error on `fwd_12m`, and price position genuinely has weak forward-return skill at exactly this 12-month horizon in this dataset. So the loss-minimizing objective keeps preferring CHIRPS/ONI features that explain more of the training target's variance, no matter how much extra freedom or opportunity price position is given. A monotonic constraint can be technically satisfied by making the price-position effect nearly flat everywhere — compliant, but practically irrelevant.

This reframes the finding: it isn't that Fix 1 merely tested better by chance — it's that this is a genuine **objective mismatch** between what the model is trained to predict (forward returns) and what the product actually needs (time a cheap purchase). That kind of mismatch can only be resolved by constraining the model's *output*, not by nudging its *training process*.

---

## Key numbers to know

| Metric | Value | Where |
|---|---|---|
| Training window | 133 months, 2010-12 to 2021-12 | §2h |
| Test window | 36 months, 2022-01 to 2024-12 | §2h |
| Binding constraint on training start | COT (disaggregated report starts 2010) | §2 |
| Test-set forecast skill, XGBoost | r=+0.421 (p=0.011) | §4 |
| Momentum correlation, original ML | r=+0.40 to +0.45 | §5 diagnostic |
| Walk-forward saving, original ML | −1.3% to −1.6% (loses to naive) | §5 |
| Walk-forward saving, legacy composite | +3.9% to +4.8% (beats naive) | §6 |
| Walk-forward saving, **Fix 1** (recommended) | **+3.0% to +3.9%** | §7a |
| Momentum correlation, Fix 1 | r=−0.73 (flipped) | §7a |
| Walk-forward saving, Fix 2 (monotonic) | −1.1% to −1.4% (no improvement) | §7b |
| Walk-forward saving, Fix 3 (feature-weight) | −1.4% to −1.6% (no improvement, XGBoost only) | §7c |

**Bottom line:** the ML models have real, statistically significant forecast skill, but that skill alone does not produce a good purchasing rule — it needs to be constrained by a value signal at the output stage. Nudging the tree's training process (direction constraints, sampling bias) does not substitute for that constraint. Fix 1 is the recommended direction for further development; this notebook is a proof-of-concept for the framework (causal feature construction, leakage-safe CV, constrained inventory simulation, systematic remediation), not a validated production signal.
