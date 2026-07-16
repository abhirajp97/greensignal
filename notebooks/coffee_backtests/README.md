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
| L2a — stocks-to-use % | Pearson r vs YoY price change | −0.35 | ≤ −0.25 | ⚠️ YoY metric FAILS (r=−0.04) but signal strong on **price level**: r=−0.40 monthly / −0.56 annual / −0.59 @ 23m lag. YoY-change is wrong lens for an annual stock var — recommend redefining gate to price level (cf. L1) |
| L2b — ENSO ONI ~14m lead | Pearson r vs **fwd** YoY price change (gate redefined: positive, El Niño) | −0.30 | ≥ +0.20 in 10–18m band | ✅ PASS r=+0.288 @ 15m (KC, p=1.6e-4) / +0.327 @ 15m (WB 2000–24, p=1.4e-8); event study: El Niño months → +36.5% fwd-12m vs La Niña −1.7% (t=5.83, p<0.001). Original sign+lag were backwards — see notebook §intro |
| L3 — Brazil CHIRPS drought | **Redefined:** annual r(flowering SPI-3 deficit, fwd-12m price) | +0.21 | ≥ +0.30 (confirming signal) | ✅ PASS: r=+0.483 (p=0.069, n=15) after the **SPI rebuild**. Old monthly r≥+0.12 lens diluted an annual once-a-year signal (see notebook §intro). Deficit `max(0,−SPI3)` beats signed SPI (−0.412) → asymmetric tail risk; robust to look-ahead (expanding-window r=+0.494) and to a stocks-to-use control (partial r=+0.48); driest vs wettest flowering third → +33.6% vs +9.5% fwd-12m. Confirming amplifier, not a standalone timing signal |
| L5 — COT contrarian | Pearson r vs YoY price change | +0.15 | ≥ +0.08 | ❌ r=−0.05 @ fwd 12m (FAIL); contrarian thesis inverted — specs trend-follow, r(index)=+0.14 @ fwd 3–6m |
| Full composite | Forward 3–6m prescience after BUY | 4.54% | ≥ 3.50% | ⬜ pending |
| Spike avoidance | Cost saving, 200 kg/mo roaster, 2024 rally | ~$3,000 | Confirm directionally | ⬜ pending |

**Signal rank order must be preserved:** L1 > L2a > L2b > L3 > L5 by absolute r value.
If this order breaks on real data, reweight the composite before building the product.
**Caveat (post-rebuild):** L3's headline r=+0.483 is on the *annual crop-year* frame (n=15),
which is not directly comparable to the *monthly* frames used for L1/L2a/L2b. L3 remains a
low-to-mid-weight **confirming** amplifier, not a timing signal — do the apples-to-apples
rank reconciliation and reweighting in the composite notebook (06), not by comparing these
frame-mismatched r values.

## Data period

Backtest window: **2010–2025** (matches Phase 0 synthetic baseline).
Buffer period needed for lags: ~2009 data required for ENSO ~14m lead alignment.

## Notebooks in this directory

| Notebook | Purpose |
|----------|---------|
| `01_ice_price_signal.ipynb` | L1: fetch real ICE KC data, compute price_position_52w, validate r |
| `02_enso_signal.ipynb` | L2b: parse NOAA ONI, apply ~14m lead, validate positive r (El Niño thesis) |
| `03_cot_signal.ipynb` | L5: parse CFTC COT disaggregated, compute COT index, validate r |
| `04_usda_supply_signal.ipynb` | L2a: parse USDA PSD bulk CSV, compute STU, validate r |
| `05_chirps_signal.ipynb` | L3: extract Minas Gerais rainfall, validate r (requires GEE) |
| `06_composite_backtest.ipynb` | Full composite: combine all signals, measure forward prescience |
| `07_wb_physical_prices.ipynb` | L1 on World Bank Arabica/Robusta physical prices + basis vs KC=F |
| `08_producer_fx_signal.ipynb` | Producer FX PoC (USD/BRL → KC): G1 PASS (monthly r=−0.316); G2/G3 FAIL — co-moves, not an exploitable timing lead after DXY/KC controls |

Work through these in order — the first three use data that needs no GEE approval.
