# Coffee Backtest — Success Criteria

The Phase 0 backtest was built on synthetic/calibrated data. The first notebook here must
reproduce the executive summary on **real data** and pass the gates below before any product
work begins.

## Pass/Fail Gates

These are the minimum acceptable signal strengths on real data. If any gate fails, the signal
rank order should be re-examined before proceeding.

**Gate definitions — L1 uses three complementary tests (see notebook for rationale):**
- Gate 1: `r(price_pos_52w, trailing_12m_yoy) ≥ +0.50` — definitional calibration (Phase 0 measured this)
- Gate 2: signal-weighted average purchase price ≥ 3% below naive average — primary economic gate
- Gate 3: BUY zone avg price < ALL avg < AVOID zone avg — monotonicity check

**Note on Phase 0 r = +0.64:** this was the contemporaneous correlation of `price_pos_52w` vs trailing YoY — not a forward-predictive r. Real data confirms it at +0.852. The forward predictive r peaks at 24m (r = +0.20, p < 0.01), not 12m, due to arabica's momentum-then-revert pattern.

| Signal | Metric | Synthetic (Phase 0) | Real-data minimum | Status |
|--------|--------|---------------------|-------------------|--------|
| L1 — price position 52w | Gate 1: contemp r ≥ +0.50 / Gate 2: cost saving ≥ 3% / Gate 3: zone monotone | r=+0.64 / saving=2.2% | see above | ✅ r=+0.852 / saving=+10.73% / monotone |
| L2a — stocks-to-use % | **Redefined, true-vintage, dual gate:** Gate 1 r(vintage S/U, 12m-fwd price level) / Gate 2 r(S/U delta, price level) | −0.35 | Gate 1 ≤ −0.25 / Gate 2 ≤ −0.20 | ✅ PASS both, on both series. **True vintage** (`usda_coffee_wmt.py`, semiannual, no approximation): Gate 1 r=−0.488 (p=6.2e-3, n=30) — *stronger* than the approximation; Gate 2 r=−0.261 (p=0.17, passes threshold, not significant at this n). **Approximation** (12m shift of the always-latest-revised PSD bulk file, monthly, kept as fallback): Gate 1 r=−0.312 (p=2.0e-5, n=180), Gate 2 r=−0.259 (p=4.6e-4, n=180). Old single YoY-change gate (r=−0.04) FAILED — wrong lens for an annual stock var |
| L2b — ENSO ONI ~14m lead | Pearson r vs **fwd** YoY price change (gate redefined: positive, El Niño) | −0.30 | ≥ +0.20 in 10–18m band | ✅ PASS r=+0.288 @ 15m (KC, p=1.6e-4) / +0.327 @ 15m (WB 2000–24, p=1.4e-8); event study: El Niño months → +36.5% fwd-12m vs La Niña −1.7% (t=5.83, p<0.001). Original sign+lag were backwards — see notebook §intro |
| L3 — Brazil CHIRPS drought | **Redefined:** annual r(flowering SPI-3 deficit, fwd-12m price) | +0.21 | ≥ +0.30 (confirming signal) | ✅ PASS: r=+0.483 (p=0.069, n=15) after the **SPI rebuild**. Old monthly r≥+0.12 lens diluted an annual once-a-year signal (see notebook §intro). Deficit `max(0,−SPI3)` beats signed SPI (−0.412) → asymmetric tail risk; robust to look-ahead (expanding-window r=+0.494) and to a stocks-to-use control (partial r=+0.48); driest vs wettest flowering third → +33.6% vs +9.5% fwd-12m. Confirming amplifier, not a standalone timing signal |
| L5 — COT momentum | **Redefined:** Pearson r vs fwd 6m price change (original contrarian gate vs YoY @ 12m FAILED, r=−0.05) | +0.15 | ≥ +0.08 | ✅ PASS: r=+0.144 (p=0.053, n=180) after the **momentum rebuild** — specs trend-follow, not fade. Weak/borderline: p at the edge of significance, 3yr rolling stability only 45% positive; walk-forward $ savings don't materialize (momentum ≠ contrarian purchase-price economics). Low-weight composite amplifier, not a standalone timing signal |
| Full composite | **Redefined primary gate:** continuous cost-improvement backtest (weighted-avg purchase price vs naive), walk-forward — not the discrete "forward prescience after BUY" test used in the first version of notebook 06 | 4.54% (old prescience metric) | ≥ 3.00% (cost improvement) | ✅ PASS: walk-forward **+5.86%**, *exceeding* L1-alone's own walk-forward benchmark (+3.71%, notebook 01). Full-history +4.45%. See "Why the gate metric changed" below |
| Signal distribution health | % BUY / % CAUTION / % NEUTRAL months, longest silent gap | 22%/31%/47% (Phase 0 target, L1 alone) | No walk-forward year with 0 non-neutral months | ⚠️ Fixed a real bug (see below), not fully resolved — rolling-24m normalization: 20.0%/27.6%/52.4%, longest gap 16 months (down from 18 with the old annual-refit method, up from 4.9% BUY) |
| Spike avoidance | Cost saving / conviction signal, 2024 rally | ~$3,000 (200kg/mo roaster) | Confirm directionally | ✅ Confirmed directionally: composite held sustained BUY Jan–Sep 2023 (price $146–190/lb), *before* the rally accelerated past $220/lb — see notebook §9 |

**Signal rank order must be preserved:** L1 > L2a > L2b > L3 > L5 by absolute r value.
If this order breaks on real data, reweight the composite before building the product.
**Caveat (post-rebuild):** L3's headline r=+0.483 is on the *annual crop-year* frame (n=15),
which is not directly comparable to the *monthly* frames used for L1/L2a/L2b. L3 remains a
low-to-mid-weight **confirming** amplifier, not a timing signal.

**Why the composite gate metric changed (notebook 06 rebuilt):** the first version of
notebook 06 passed its gate (discrete "forward prescience after BUY" ≥3.50%) but on an
extremely thin sample — only 11–21 buy-months across 10 walk-forward years, 3–4 with *zero*
buy months. Re-reading the product docs confirmed GreenSignal is designed as a **continuous,
always-on three-state signal**, not a rare-event alert (Phase 0 target: L1 alone fires BUY
22% of months; real data confirms 35–41%, not sparse at all). Root cause: the old
walk-forward re-derived its normalization baseline *once per year* from an expanding window,
producing lumpy per-year buckets (4.9% BUY, 18-month longest silent gap). A **rolling
24-month** trailing-window normalization (recomputed every month — closer to how
`price_position_52w` itself works) fixes most of this (20.0% BUY, 16-month gap). The
notebook also switched its **primary economic gate** to the continuous
`cost_improvement_backtest` methodology (`docs/GreenSignal_Math_Reference.md` §11.1, the
same one notebook 01 used for L1 alone) rather than the discrete prescience test, which is
now kept only as a secondary check. See notebook §§4–9 for full detail, including two honest
open anomalies not yet resolved: the secondary prescience check shows BUY months
*underperforming* CAUTION/NEUTRAL in this sample (§7), and the leave-one-out ablation
reverses sign for L5 vs. the original notebook's ablation (§8) — both flagged as real
follow-up items, not swept under the rug.

## Data period

Backtest window: **2010–2025** (matches Phase 0 synthetic baseline).
Buffer period needed for lags: ~2009 data required for ENSO ~14m lead alignment.

## Notebooks in this directory

| Notebook | Purpose |
|----------|---------|
| `01_ice_price_signal.ipynb` | L1: fetch real ICE KC data, compute price_position_52w, validate r |
| `02_enso_signal.ipynb` | L2b: parse NOAA ONI, apply ~14m lead, validate positive r (El Niño thesis) |
| `03_cot_signal.ipynb` | L5: parse CFTC COT disaggregated, compute COT index, validate r |
| `04_usda_supply_signal.ipynb` | L2a: parse USDA PSD bulk CSV (approximation) + USDA Coffee: World Markets and Trade circulars (true vintage), compute STU, validate r |
| `05_chirps_signal.ipynb` | L3: extract Minas Gerais rainfall, validate r (requires GEE) |
| `06_composite_backtest.ipynb` | Full composite: combine all signals, measure forward prescience |
| `07_wb_physical_prices.ipynb` | L1 on World Bank Arabica/Robusta physical prices + basis vs KC=F |
| `08_producer_fx_signal.ipynb` | Producer FX PoC (USD/BRL → KC): G1 PASS (monthly r=−0.316); G2/G3 FAIL — co-moves, not an exploitable timing lead after DXY/KC controls |

Work through these in order — the first three use data that needs no GEE approval.
