# Notebook 03 — CFTC COT Signal (L5): Reader's Guide

This document explains what each section of `notebooks/coffee_backtests/03_cot_signal.ipynb` is doing, the math behind it, and how to interpret the outputs. It is intended as a teaching reference for anyone reading the notebook for the first time.

---

## What the notebook is trying to answer

Two questions, answered in sequence:

1. **Does speculative positioning in ICE Coffee C futures predict future prices?** The CFTC Commitments of Traders (COT) report gives a weekly snapshot of how hedge funds and managed money are positioned. If they are crowded long, does that predict higher or lower prices over the next 3–12 months?

2. **Can that relationship be translated into a purchasing rule that saves money?** If the signal has predictive power, does it survive as a standalone purchasing signal, or is it only useful as a modifier inside a composite?

The notebook originally tested a contrarian hypothesis — that extreme spec positioning predicts reversals. The real data inverted that thesis. This guide documents the corrected momentum interpretation and explains why the signal ultimately does not work standalone.

---

## Background: what the COT report is

Every Tuesday, the CFTC publishes the disaggregated Commitments of Traders report. It breaks down open interest in each futures market by trader type. The category we use is **Managed Money** — hedge funds, commodity trading advisors, and other systematic traders.

The raw signal is:

```
net_managed_money_t = long_contracts_t − short_contracts_t
```

A positive net means managed money is collectively long (bullish). A negative net means collectively short (bearish). The raw number in isolation is hard to interpret because the total level of spec participation in coffee futures has grown significantly since 2010 — a net of +40,000 contracts in 2012 and in 2024 mean very different things in relative terms.

---

## §0 — Setup

Standard imports and path setup. `sys.path.insert` makes the `domains/` package importable from the notebook directory. No analysis here.

---

## §1 — Fetch CFTC COT Data

Downloads the disaggregated futures-only ZIP files directly from `cftc.gov`, one per calendar year. The fetch range starts in 2008 to give the rolling COT index a 3-year burn-in before the 2010 analysis window opens.

**What the source does:**
- Downloads `fut_disagg_txt_{year}.zip` for each year in range
- Filters rows where `Market_and_Exchange_Names` contains `COFFEE C - ICE`
- Extracts `M_Money_Positions_Long_All` and `M_Money_Positions_Short_All`
- Returns weekly `FeatureObservation` records with `feature_name = "managed_money_net"`

**Expected output:**
- `RunStatus.PARTIAL` — the disaggregated report does not exist before 2010, so the 2008 and 2009 ZIPs return HTTP 404. PARTIAL is the correct status when some years succeed.
- ~835 weekly observations covering 2010 to the most recent year

---

## §2 — Data Quality Checks

Two checks:

1. **Gap detection** — flags any interval between consecutive weekly records greater than 30 days. The COT report is published every Tuesday; occasional holiday delays produce 14-day gaps but nothing longer under normal operation.
2. **NaN check over the core window** — asserts no missing values in `net` from 2010 to 2024. A NaN in the net position would silently corrupt the rolling percentile calculation in §3.

---

## §3 — Feature Engineering: COT Index

Normalises the raw net position to a 0–100 rolling percentile, producing the **COT index**.

**The formula:**

```
cot_index_t = 100 × (net_t − min(net_{t−W:t})) / (max(net_{t−W:t}) − min(net_{t−W:t}))
```

where W = 156 weeks (3 years). This answers: *where does this week's net position rank within the last 3 years of readings?*

- `cot_index = 100` — specs are more net-long than at any point in the past 3 years (maximally bullish)
- `cot_index = 50` — specs are exactly in the middle of their recent range (neutral)
- `cot_index = 0` — specs are more net-short than at any point in the past 3 years (maximally bearish)

**Why 156 weeks (3 years)?**

The window must be long enough to capture a full commodity cycle. Arabica price cycles are approximately 24–36 months (validated in notebook 01). A shorter window would recalibrate too quickly after an extreme and lose the memory of where "normal" positioning is. A much longer window would be slow to adapt if the structural level of spec participation changes — which it has.

**Edge case:** When the rolling window contains identical max and min (all net values equal — flat market), `_cot_index` returns 50 (neutral) rather than NaN. This prevents a divide-by-zero from propagating into downstream calculations.

The weekly series is then resampled to month-end by taking the last Tuesday reading in each month.

**The chart shows:**
- Top panel: raw net position (contracts), with zero line and shaded long/short regions
- Bottom panel: COT index (0–100), with 75 (crowded long) and 25 (crowded short) reference lines

---

## §4 — Correlation vs ICE KC Price

**The hypothesis being tested:** a high COT index (specs crowded long) predicts higher prices over the next 3–6 months — a **momentum** signal.

Aligns month-end COT index to the ICE KC=F month-end close, then sweeps forward horizons 1m through 24m.

**The correlation at each horizon:**

```
r_h = Pearson r( cot_index_t,  price_change_{t → t+h} )
```

Both variables use only data available at time t or later — the COT index uses only the rolling 156-week backward window, and the forward return is genuinely future. There is no look-ahead.

**What the results show:**

The correlation is positive and peaks at the 3–6 month horizon (r ≈ +0.14), then decays toward zero by 18–24 months. This means:

- Specs being crowded long today predicts prices being higher 3–6 months from now
- The relationship is not contrarian (reversal) — it is momentum (continuation)
- Beyond 12 months the edge dissipates

**Why the original contrarian thesis failed:**

The notebook originally tested `r(contrarian_signal, fwd_12m_return)` where `contrarian_signal = (50 − cot_index) / 50` (positive when specs are short). That test returned r = −0.05 at 12m — the contrarian thesis is inverted. Managed money in coffee trend-follows. Specs are long when prices have been rising, and they stay long while prices continue rising for another 3–6 months. The sign had to be flipped.

**The chart** plots r at every horizon from 1m to 24m, with the +0.08 gate threshold as a reference line. The peak and decay shape is immediately visible.

---

## §5 — Walk-forward Validation

### The signal rule

Units are a continuous linear function of the COT index:

```
units_t = cot_index_t / 50
```

| COT index | Units | Interpretation |
|-----------|-------|---------------|
| 0 | 0x | Specs maximally bearish — defer purchasing |
| 50 | 1x | Neutral — buy normally |
| 100 | 2x | Specs maximally bullish — buy ahead of expected price rise |

This mirrors L1's continuous `buy_signal = 1 − price_pos` rather than a hard threshold. At index = 50 you are buying at the baseline rate; the signal tilts purchases up or down proportionally.

### The three variants

To test whether the result depends on a single rolling-window calibration, the top 3 horizons from the §4 sweep are selected programmatically and each mapped to a proportional rolling window:

```
W_h = max(52,  horizon_months × 17)   weeks
```

This gives roughly:
- Best horizon ~3m → W ≈ 51w (1-year lookback)
- Best horizon ~6m → W ≈ 102w (2-year lookback)
- Best horizon ~9m → W ≈ 153w (3-year lookback)

All three use `units = cot_index / 50`. Running them side-by-side shows whether the walk-forward result is robust across window lengths or driven by one calibration.

### The cost-saving metric

For each year Y and each variant:

```
naive_avg_Y  = mean(settle_t)              for t in year Y
signal_avg_Y = Σ(units_t × settle_t) / Σ(units_t)   for t in year Y
saving_Y     = (naive_avg_Y − signal_avg_Y) / naive_avg_Y × 100
```

The grouped bar chart shows saving_Y for each of the 3 variants across 2013–2024.

### Why the savings do not materialise

**This is the critical finding of the notebook.** Despite r ≈ +0.14 at 3–6m, the walk-forward savings are near zero or negative across variants and years.

The reason is a fundamental mismatch between signal type and metric:

The walk-forward saves money when you buy **more units in cheap months and fewer in expensive months**. That works for contrarian signals (L1): low price position = prices are cheap right now = buy 2x = your weighted average is structurally below naive.

The COT momentum signal tells you something different: specs are crowded long because prices have already been rising. So high COT index months are months when prices are already elevated. Buying 2x at already-elevated prices increases your weighted average relative to naive — even if prices continue rising over the next 6 months, you are still paying above the annual average today. The savings framework does not capture the value of "you avoided buying at an even higher future price."

**Quantitatively:** r = +0.14 is too weak to consistently override this structural disadvantage. Even if 60% of high-COT months go on to see price rises, the absolute magnitude of those rises relative to the current price level is not large enough to show up as cost savings in this measurement framework.

### The two conclusions

1. **COT does not work as a standalone purchasing signal.** r = +0.14 at 3–6m is a real correlation but insufficient to drive standalone purchasing decisions. Compare with L1's walk-forward: r ≈ +0.85 contemporaneously and 12/12 positive years — the signal strength required to beat naive consistently in this framework is much higher.

2. **The right role for COT is as a composite modifier.** Rather than generating independent buy/sell decisions, the COT index amplifies or dampens the L1 price-position signal:
   - L1 says buy + COT high (momentum confirms the dip is real) → buy more aggressively
   - L1 says buy + COT low (momentum diverging) → buy more cautiously

   This is how COT is positioned in the composite formula: a low-weight amplifier of conviction, not a standalone timer.

---

## Key numbers to know

| Metric | Value | Where |
|--------|-------|-------|
| Peak forward r (momentum) | ≈ +0.14 at 3–6m | §4 sweep |
| Contrarian r at 12m (original thesis) | −0.05 | §4 / original Sec 5 |
| Walk-forward avg saving (all variants) | ≈ 0 or negative | §5 |
| Rolling window variants tested | 51w / 102w / 153w | §5 |
| Role in composite | Low-weight momentum amplifier | CLAUDE.md |

The forward r of +0.14 is real and statistically distinguishable from zero — but predictive power and standalone purchasing value are not the same thing. The contrarian-style measurement framework requires a much stronger signal to beat naive. COT earns its place in the composite as a modifier of L1, not as an independent timing signal.
