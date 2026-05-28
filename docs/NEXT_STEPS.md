# GreenSignal — Next Steps

This file is the handoff note between sessions. Claude updates it automatically at the end of each working session. Both collaborators should read it at the start of any session and update it when priorities shift.

---

## Current focus

**Phase 1 — Real data pipelines and backtest validation**

The skeleton is built and the architecture is locked. The immediate work is implementing the first three data sources (no GEE needed) and running them through the backtest notebooks to validate signal rank order on real data before any product work begins.

---

## Up next (in order)

- [ ] **Register for Nasdaq Data Link** at `data.nasdaq.com` — get API key, add to `.env` ← **do this before next session starts**
- [x] **Implement `domains/coffee/sources/ice_coffee_c.py`** — fetch `CHRIS/ICE_KC1` daily close, return `list[MarketObservation]`
- [x] **Run `notebooks/coffee_backtests/01_ice_price_signal.ipynb`** — ALL GATES PASS: contemp r=+0.852, cost saving=+10.73% (full-history) / +3.71% walk-forward (12/12 years positive), zone monotone; momentum baseline −10.37% validates contrarian; 104w window +15.01%
- [x] **Implement `domains/coffee/sources/world_bank_commodity.py`** — World Bank Pink Sheet; Arabica + Robusta physical prices (free, no auth); two-step fetch (scrape page → download Excel); 15 tests pass
- [x] **Implement `domains/coffee/sources/noaa_enso.py`** — 26 tests passing; NDJ year-boundary handled; -99.9 sentinel skipped
- [x] **Run `notebooks/coffee_backtests/02_enso_signal.ipynb`** — gate FAILS at 24m lag (r=−0.127); signal strongest contemporaneously (r=−0.338); ENSO revised to current-state amplifier role in composite
- [ ] **Implement `domains/coffee/sources/cot.py`** — download CFTC disaggregated annual CSVs, filter to `COFFEE C - ICE FUTURES U.S.`, compute COT index
- [ ] **Run `notebooks/coffee_backtests/03_cot_signal.ipynb`** — validate r ≥ +0.08
- [ ] **Download USDA PSD bulk CSV** — implement `usda_psd.py`, run notebook 04
- [ ] **Apply for Google Earth Engine access** at `earthengine.google.com` (1–2 day approval) — then implement `chirps.py`, run notebook 05
- [ ] **Run `notebooks/coffee_backtests/06_composite_backtest.ipynb`** — confirm all five gates pass and signal rank order holds

---

## Blocked / waiting

| Item | Blocked on |
|------|-----------|
| `chirps.py` implementation | GEE approval (apply now, it's free) |
| Supabase storage wiring | Not needed until signals are validated |
| FastAPI routes (coffee) | Not needed until signals are validated |

---

## Decisions made this session

| Decision | Rationale |
|----------|-----------|
| Canonical models use Pydantic `BaseModel` | FastAPI serialization, no extra layer needed |
| `forecaster.py` deleted | Pointless wrapper until `fit_and_forecast` is real |
| `make verify` is the pre-commit gate | Import boundary + lint + tests in one command |
| Repo is public on GitHub | Required for branch protection on free plan; no secrets in code |
| `@anshquant` added as Admin collaborator | Anshumaan Gandhi — co-developer |
| `.claude/settings.json` added to repo | Ruff auto-format on every Edit/Write; `.env` write blocked at hook level |
| `.mcp.json` added to repo | GitHub + Supabase MCP servers wired; auth via env vars, not secrets in config |
| `implement-source` skill created | Enforces consistent source contract — prevents drift across 5 implementations |
| `backtest-notebook` skill created | Enforces consistent notebook structure — all 6 notebooks follow same template |
| `data-source-reviewer` agent created | Independent review gate before any source is merged |

---

## Backtest pass/fail gates (do not start product work until all pass)

See `notebooks/coffee_backtests/README.md` for the full table. Summary:

| Signal | Minimum r on real data |
|--------|----------------------|
| L1 price position | ≥ +0.50 |
| L2a stocks-to-use | ≤ −0.25 |
| L2b ENSO 24m lag | ≤ −0.20 |
| L3 CHIRPS drought | ≥ +0.12 |
| L5 COT contrarian | ≥ +0.08 |
| Full composite prescience | ≥ 3.50% forward |

---

---

## Decisions made this session

| Decision | Rationale |
|----------|-----------|
| `fetch()` returns `tuple[list[MarketObservation], SourceRun]` | Skill contract — sources log their own run metadata; storage is the job's responsibility |
| Use `Settle` column (not `Last`) for ICE KC price | Settlement price is the official exchange close; `Last` is the final trade and can differ |
| `raw` field stores `dict(zip(column_names, row))` | More useful than a bare list; survives column reordering |
| `datetime.now(UTC)` instead of `utcnow()` | `utcnow()` deprecated in Python 3.12+ |
| `data_quality.py` stubs implemented | Required for `ice_coffee_c.py` to call gap/range checks |
| `core/models/__init__.py` bug fixed | Was importing `Scenario` (doesn't exist); corrected to `ScenarioInput`, `ScenarioOutput` |
| Nasdaq Data Link CHRIS requires paid plan | API returns 403 for CHRIS database; backtest uses Yahoo Finance `KC=F` (equivalent instrument) |
| L1 gate redefined: 3 tests instead of 1 | Phase 0 r=+0.64 was contemporaneous (trivially high); corrected to contemp r + cost-saving + zone monotonicity |
| Arabica mean-reversion is 24m, not 12m | Forward predictive r peaks at 24m lag (r=+0.20); at 12m r≈0 due to momentum-then-revert pattern |
| Real cost-saving is 10.73%, not 2.2% | Phase 0 synthetic underestimated because real prices had more extreme episodes (2024 spike etc.) |

| Walk-forward cost saving is +3.71% (not +10.73%) | Full-history number is in-sample; walk-fwd is the honest out-of-sample estimate — cite this in product/investor comms |
| Momentum baseline is −10.37% vs naive | Trend-following hurts for coffee procurement; contrarian approach validated decisively |
| 104w window (+15.01%) outperforms 52w (+12.95%) | Noted for future composite tuning; not changing current L1 signal until all 5 signals validated |

*Last updated: 2026-05-21 — 01_ice_price_signal.ipynb extended with §7 walk-forward and §8 signal variants; all gates still PASS*
