# GreenSignal — Next Steps

This file is the handoff note between sessions. Claude updates it automatically at the end of each working session. Both collaborators should read it at the start of any session and update it when priorities shift.

---

## Current focus

**Phase 1 — Real data pipelines and backtest validation**

The skeleton is built and the architecture is locked. The immediate work is implementing the first three data sources (no GEE needed) and running them through the backtest notebooks to validate signal rank order on real data before any product work begins.

---

## Up next (in order)

- [ ] **Register for Nasdaq Data Link** at `data.nasdaq.com` — get API key, add to `.env` ← **do this before next session starts**
- [ ] **Implement `domains/coffee/sources/ice_coffee_c.py`** — fetch `CHRIS/ICE_KC1` daily close, return `list[MarketObservation]`
- [ ] **Run `notebooks/coffee_backtests/01_ice_price_signal.ipynb`** — compute `price_position_52w`, validate r ≥ +0.50 vs Phase 0 gate
- [ ] **Implement `domains/coffee/sources/noaa_enso.py`** — parse NOAA ONI fixed-width text, handle year-boundary seasons carefully
- [ ] **Run `notebooks/coffee_backtests/02_enso_signal.ipynb`** — apply 24m lag, validate r ≤ −0.20
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

*Last updated: 2026-05-18 — end of skeleton + repo setup session*
