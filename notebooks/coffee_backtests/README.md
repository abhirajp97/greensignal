# Coffee Backtest — Success Criteria

The Phase 0 backtest was built on synthetic/calibrated data. The first notebook here must
reproduce the executive summary on **real data** and pass the gates below before any product
work begins.

## Pass/Fail Gates

These are the minimum acceptable signal strengths on real data. If any gate fails, the signal
rank order should be re-examined before proceeding.

| Signal | Metric | Synthetic (Phase 0) | Real-data minimum | Status |
|--------|--------|---------------------|-------------------|--------|
| L1 — price position 52w | Pearson r vs YoY price change | +0.64 | ≥ +0.50 | ⬜ pending |
| L2a — stocks-to-use % | Pearson r vs YoY price change | −0.35 | ≤ −0.25 | ⬜ pending |
| L2b — ENSO ONI 24m lag | Pearson r vs YoY price change | −0.30 | ≤ −0.20 | ⬜ pending |
| L3 — Brazil CHIRPS drought | Pearson r vs YoY price change | +0.21 | ≥ +0.12 | ⬜ pending |
| L5 — COT contrarian | Pearson r vs YoY price change | +0.15 | ≥ +0.08 | ⬜ pending |
| Full composite | Forward 3–6m prescience after BUY | 4.54% | ≥ 3.50% | ⬜ pending |
| Spike avoidance | Cost saving, 200 kg/mo roaster, 2024 rally | ~$3,000 | Confirm directionally | ⬜ pending |

**Signal rank order must be preserved:** L1 > L2a > L2b > L3 > L5 by absolute r value.
If this order breaks on real data, reweight the composite before building the product.

## Data period

Backtest window: **2010–2025** (matches Phase 0 synthetic baseline).
Buffer period needed for lags: 2008–2009 data required for ENSO 24m lag alignment.

## Notebooks in this directory

| Notebook | Purpose |
|----------|---------|
| `01_ice_price_signal.ipynb` | L1: fetch real ICE KC data, compute price_position_52w, validate r |
| `02_enso_signal.ipynb` | L2b: parse NOAA ONI, apply 18m/24m lags, validate r |
| `03_cot_signal.ipynb` | L5: parse CFTC COT disaggregated, compute COT index, validate r |
| `04_usda_supply_signal.ipynb` | L2a: parse USDA PSD bulk CSV, compute STU, validate r |
| `05_chirps_signal.ipynb` | L3: extract Minas Gerais rainfall, validate r (requires GEE) |
| `06_composite_backtest.ipynb` | Full composite: combine all signals, measure forward prescience |

Work through these in order — the first three use data that needs no GEE approval.
