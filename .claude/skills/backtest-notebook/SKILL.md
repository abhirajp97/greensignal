# Skill: backtest-notebook

Create and run a GreenSignal backtest notebook for a single signal layer.

## When to use

Run this after a source in `domains/coffee/sources/` is implemented and `make verify` passes. The notebook validates the signal on real data against the pass/fail gate in `notebooks/coffee_backtests/README.md`.

## Notebook structure (all 6 notebooks follow this template)

```
## 0. Setup
- imports: pandas, numpy, matplotlib, scipy.stats
- load .env (python-dotenv)
- set BACKTEST_START = "2008-01-01", BACKTEST_END = today

## 1. Fetch data
- call the source's fetch() function with the backtest date range
- convert list[MarketObservation | FeatureObservation] → DataFrame
- show df.head(), df.info(), df.describe()

## 2. Data quality checks
- plot the raw series — look for gaps, spikes, flat stretches
- assert no NaN in the value column over the core 2010–2025 window
- print record count, date range, any gaps > 30 days

## 3. Feature engineering
- call the relevant feature function from domains/coffee/features/
- show the derived feature series alongside the raw signal
- for lagged signals (ENSO): explicitly plot raw vs lagged

## 4. Correlation vs ICE KC price
- align feature series to ICE KC month-end close (load from ice_coffee_c or CSV)
- compute Pearson r and p-value using scipy.stats.pearsonr
- plot scatter with regression line
- print: r = X.XX, p = X.XXXX, n = XXX

## 5. Pass/fail gate
- load the gate threshold from notebooks/coffee_backtests/README.md
- assert r meets or exceeds the gate
- print PASS ✅ or FAIL ❌ with the actual vs required r

## 6. Rolling stability (optional but recommended)
- 3-year rolling Pearson r — does the signal hold up across regimes?
- flag any window where r flips sign

## 7. Summary
- one markdown cell: signal name, r achieved, gate, PASS/FAIL, key observations
```

## Steps

1. Confirm the source's `fetch()` is implemented and tests pass
2. Create the notebook at `notebooks/coffee_backtests/0N_<signal_name>.ipynb`
3. Follow the structure above — do not skip sections
4. Run all cells top-to-bottom in a clean kernel — no hidden state
5. If FAIL: do not move on. Diagnose: wrong lag? data alignment issue? revisit the feature engineering
6. If PASS: update `notebooks/coffee_backtests/README.md` — change `⬜ pending` to `✅ r = X.XX`
7. Update `docs/FILE_MAP.md` — change notebook status from `🔲 Not created` to `✅ Done (r = X.XX)`
8. Update `docs/NEXT_STEPS.md` — check off the notebook run task

## Notebook naming

| Signal | Notebook |
|--------|----------|
| ICE KC price position | `01_ice_price_signal.ipynb` |
| ENSO ONI 24m lag | `02_enso_signal.ipynb` |
| CFTC COT index | `03_cot_signal.ipynb` |
| USDA STU | `04_usda_supply_signal.ipynb` |
| CHIRPS Brazil rainfall | `05_chirps_signal.ipynb` |
| Full composite | `06_composite_backtest.ipynb` |

## ICE KC price reference

All correlation notebooks need ICE KC month-end close as the dependent variable. Fetch it once and save as `notebooks/coffee_backtests/data/ice_kc_monthly.csv` so notebooks 02–06 can load it directly without re-hitting the API.

## Pass/fail gates (from README.md)

| Notebook | Signal | Gate |
|----------|--------|------|
| 01 | L1 price position (52w) | r ≥ +0.50 |
| 02 | L2b ENSO 24m lag | r ≤ −0.20 |
| 03 | L5 COT contrarian | r ≥ +0.08 |
| 04 | L2a USDA stocks-to-use | r ≤ −0.25 |
| 05 | L3 CHIRPS drought | r ≥ +0.12 |
| 06 | Full composite prescience | ≥ 3.50% forward |
