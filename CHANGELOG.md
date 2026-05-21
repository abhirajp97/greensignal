# Changelog

All notable changes to GreenSignal are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Versions are dated. Each entry covers what changed, why it matters, and who did it.

---

## [Unreleased]

Planned but not yet merged to `main`:
- Implement `ice_coffee_c.py` — real ICE KC price data via Nasdaq Data Link
- Implement `noaa_enso.py` — NOAA ONI signal with 24m lag
- Implement `cot.py` — CFTC COT disaggregated report
- Backtest notebooks 01–03 on real data

---

## [0.3.0] — 2026-05-21

### Added
- `.claude/settings.json` — project-level hooks: Ruff auto-format on every Edit/Write; hard block on `.env` writes
- `.mcp.json` — GitHub MCP (`@modelcontextprotocol/server-github`) and Supabase MCP (`@supabase/mcp-server-supabase`) wired via env vars
- `.claude/skills/implement-source/SKILL.md` — custom skill enforcing the source implementation contract (return type, SourceRun, error handling, test requirements, doc updates)
- `.claude/skills/backtest-notebook/SKILL.md` — custom skill with full notebook template for all 6 validation notebooks
- `.claude/agents/data-source-reviewer.md` — subagent for pre-merge review of source implementations; returns APPROVED or NEEDS WORK verdict

### Changed
- `CLAUDE.md` — added "Claude Code Automation Layer" section documenting hooks, MCP servers, skills, and agents
- `docs/FILE_MAP.md` — added `.claude/` and root `.mcp.json` entries

---

## [0.2.0] — 2026-05-18

### Added
- `CONTRIBUTING.md` — branching workflow, naming conventions, secrets rules, `make verify` as pre-commit gate
- `docs/NEXT_STEPS.md` — session handoff document; updated by Claude at end of each working session
- `CHANGELOG.md` — this file
- Branch protection on `main`: PRs required, 1 approving review, stale approvals dismissed, force-push blocked
- `@anshquant` (Anshumaan Gandhi) added as Admin collaborator

### Changed
- Repo made public (required for branch protection on free GitHub plan; no secrets in code)

---

## [0.1.0] — 2026-05-17

### Added
- Full repo skeleton: `core/`, `domains/coffee/`, `apps/api/`, `jobs/`, `notebooks/`, `tests/`
- Canonical Pydantic models: `Asset`, `MarketObservation`, `FeatureObservation`, `Recommendation`, `RiskSignal`, `Forecast`, `ScenarioInput/Output`, `SourceRun`
- Coffee domain stubs: all 5 signal sources (`ice_coffee_c`, `noaa_enso`, `cot`, `usda_psd`, `chirps`), feature engineering, `signal_generator`, `risk_scorer`
- FastAPI app with working `GET /health` and stubbed `/coffee` routes
- `Makefile` with `lint`, `test`, `check-imports`, `verify` targets
- `docs/FILE_MAP.md` — full file map with status column, kept current alongside code
- `docs/NEXT_STEPS.md` — prioritised task list and session handoff
- `notebooks/coffee_backtests/README.md` — per-signal pass/fail gates (r thresholds) that must be met on real data before product work begins
- `CLAUDE.md` — architecture rules, key decisions, commands, build sequence, and proactive update instructions for Claude Code
- `pyproject.toml` with uv, Python 3.12+, FastAPI, Pydantic v2, Ruff, pytest

### Architecture decisions
- Canonical models use `pydantic.BaseModel` (not dataclasses) — FastAPI serialization with no extra layer
- `core/` import boundary enforced by `make check-imports` — `grep -r "from domains" core/` must return nothing
- Jobs (`daily_prices`, `monthly_supply`, `monthly_climate`) are plain `run()` functions — scheduler deferred to Phase 1
- `domains/coffee/models/forecaster.py` not created — pointless wrapper until `core/services/forecasting.py` is real
