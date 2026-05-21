# Skill: implement-source

Implement a GreenSignal data source from stub to working code with tests.

## When to use

Run this when you are implementing any file in `domains/coffee/sources/` that is currently a stub (`🔲 Stub` in `docs/FILE_MAP.md`).

## Contract every source must satisfy

1. **Return type:** `list[MarketObservation]` or `list[FeatureObservation]` — always a list, never a DataFrame
2. **SourceRun log:** every `fetch()` call must return a `SourceRun` alongside the observations (use a tuple)
3. **Data quality:** call `core/services/data_quality.py` checks before returning — log warnings, never raise on gaps
4. **No side effects:** sources do not write to the database — that is the job's responsibility
5. **Env vars only:** API keys come from `os.environ` — never hardcoded, never from function args

## Implementation steps

1. Read the stub file — note the `_URL` / `_BASE_URL` and any `_QUIRK` comments
2. Read `CLAUDE.md` → "Data Sources & Key Quirks" section for the specific source
3. Implement `fetch(start: date, end: date) -> tuple[list[MarketObservation | FeatureObservation], SourceRun]`
4. Parse raw response into canonical objects — use the models from `core/models/`
5. Write a test in `tests/domains/coffee/test_<source_name>.py` that:
   - Mocks the HTTP call (never hits live APIs in tests)
   - Asserts the return type, length, and field values on a known fixture
   - Asserts `SourceRun.status == "success"` on a clean response
   - Asserts `SourceRun.status == "partial"` or `"failed"` on error fixture
6. Run `make verify` — all checks must pass before declaring done
7. Update `docs/FILE_MAP.md` — change `🔲 Stub` to `✅ Done` for this file
8. Update `docs/NEXT_STEPS.md` — check off the implement task
9. Update `CLAUDE.md` if any quirk was discovered that is not yet documented

## File naming

| Source | File | Test |
|--------|------|------|
| ICE KC price | `domains/coffee/sources/ice_coffee_c.py` | `tests/domains/coffee/test_ice_coffee_c.py` |
| NOAA ENSO ONI | `domains/coffee/sources/noaa_enso.py` | `tests/domains/coffee/test_noaa_enso.py` |
| CFTC COT | `domains/coffee/sources/cot.py` | `tests/domains/coffee/test_cot.py` |
| USDA PSD | `domains/coffee/sources/usda_psd.py` | `tests/domains/coffee/test_usda_psd.py` |
| CHIRPS | `domains/coffee/sources/chirps.py` | `tests/domains/coffee/test_chirps.py` |

## Quality bar

- No `type: ignore` without a comment explaining why
- No bare `except:` — catch specific exceptions
- All HTTP calls have a timeout (default 30s)
- Parse errors log the offending row and skip it — never crash on one bad record
