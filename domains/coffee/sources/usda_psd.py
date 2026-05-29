"""USDA Production, Supply and Distribution (PSD) — global coffee supply balance.

Source:  USDA Foreign Agricultural Service — PSD Online
URL:     https://apps.fas.usda.gov/psdonline/downloads/psd_coffee_csv.zip
Auth:    None (free bulk CSV, no API key)
Freq:    Annual by marketing year; the bulk file holds the latest vintage only
         (one row per country / marketing-year / attribute).

The signal (L2a) is **world stocks-to-use %** = world ending stocks / world
domestic consumption × 100, per marketing year. A low buffer historically
precedes higher Arabica prices.

CSV columns: Commodity_Code, Commodity_Description, Country_Code, Country_Name,
Market_Year, Calendar_Year, Month, Attribute_ID, Attribute_Description,
Unit_ID, Unit_Description, Value.

Quirks discovered against the live file (2026-05):
  - `Commodity_Code` is the integer 711100 (not the string "0711100").
  - **There is no World aggregate row** — PSD coffee lists 94 individual
    countries; the world total must be SUMMED across countries per market year.
  - Attribute IDs: **176 = Ending Stocks, 125 = Domestic Consumption**.
    (Attribute 57 is *Imports*, not consumption — do not use it.)
  - Values are in 1000 60-kg bags and are retroactively revised; the bulk file
    is always the newest vintage. Production logs each fetch as a SourceRun to
    build a vintage history of what was known when.

Date assignment: each marketing year's stocks-to-use is anchored to Dec 31 of
the `Market_Year`. PSD is annual; downstream features forward-fill to monthly
before correlating with price (see notebook 04).
"""

import io
import logging
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pandas as pd

from core.models.observation import FeatureObservation
from core.models.source_run import RunStatus, SourceRun
from core.services import data_quality
from domains.coffee.registry.assets import USDA_STU

_BULK_URL = "https://apps.fas.usda.gov/psdonline/downloads/psd_coffee_csv.zip"

_SOURCE_ID = "coffee:usda_psd"
_SOURCE_TAG = "usda:psd_coffee"
_FEATURE_NAME = "stocks_to_use_pct"

_COMMODITY_CODE = 711100
_ENDING_STOCKS_ATTR = 176
_CONSUMPTION_ATTR = 125

# Sanity bounds for a world stocks-to-use ratio (percent)
_STU_MIN = 0.0
_STU_MAX = 100.0

# Provisional risk-score bounds (percent) — calibrate against notebook 04.
# Tight buffer (low S/U) = high supply risk.
_STU_RISK_TIGHT = 12.0   # S/U <= 12% → risk 1.0
_STU_RISK_AMPLE = 35.0   # S/U >= 35% → risk 0.0

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────────


def fetch(start: date, end: date) -> tuple[list[FeatureObservation], SourceRun]:
    """Download the USDA PSD coffee bulk CSV and return world stocks-to-use %.

    Returns a tuple of (observations, source_run); the source_run is always
    returned even on failure. One observation per marketing year in [start, end],
    each carrying the world stocks-to-use ratio (percent) anchored to Dec 31 of
    that marketing year.
    """
    started_at = datetime.now(UTC)

    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            resp = client.get(_BULK_URL)
            resp.raise_for_status()
            content = resp.content
    except httpx.HTTPStatusError as exc:
        return [], _failed_run(
            started_at, f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        )
    except httpx.RequestError as exc:
        return [], _failed_run(started_at, f"Request error: {exc}")

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
            text = zf.read(csv_name).decode("utf-8", errors="replace")
    except (zipfile.BadZipFile, KeyError, StopIteration) as exc:
        return [], _failed_run(started_at, f"Bad archive: {exc}")

    try:
        df = pd.read_csv(io.StringIO(text))
    except (pd.errors.ParserError, ValueError) as exc:
        return [], _failed_run(started_at, f"CSV parse error: {exc}")

    observations, structural_error = _world_stu(df, start, end)

    if structural_error:
        return [], _failed_run(started_at, structural_error)

    if observations:
        dates = [o.observed_date for o in observations]
        values = [o.value for o in observations]
        gaps = data_quality.check_no_gaps(dates, max_gap_days=400)  # annual cadence
        oob = data_quality.check_value_range(values, low=_STU_MIN, high=_STU_MAX)
        if gaps:
            logger.warning(
                "%s: gap check found %d gap(s) in PSD years", _SOURCE_ID, len(gaps)
            )
        if oob:
            logger.warning(
                "%s: %d stocks-to-use value(s) outside [%.0f, %.0f]%%",
                _SOURCE_ID, len(oob), _STU_MIN, _STU_MAX,
            )

    return observations, SourceRun(
        source_id=_SOURCE_ID,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=RunStatus.SUCCESS,
        records_fetched=len(observations),
        records_stored=0,
        error_message=None,
    )


def load_from_csv(path: Path) -> list[FeatureObservation]:
    """Parse a local USDA PSD bulk CSV and return world stocks-to-use observations.

    Offline counterpart to `fetch()` — useful for analysing archived vintage
    snapshots. Returns the full series (no date filtering, no SourceRun).
    """
    df = pd.read_csv(path)
    observations, structural_error = _world_stu(df, date(1900, 1, 1), date(2100, 12, 31))
    if structural_error:
        raise ValueError(f"{_SOURCE_ID}: {structural_error}")
    return observations


def stocks_to_use(ending_stocks: float, consumption: float) -> float:
    """Compute stocks-to-use ratio as a percentage."""
    return (ending_stocks / consumption) * 100 if consumption else 0.0


def stu_risk_score(stu_pct: float) -> float:
    """Convert a world stocks-to-use % to a 0–1 supply-risk score for the composite.

    Risk rises as the buffer tightens. Bounds are provisional pending calibration
    in notebook 04:
        S/U <= 12%  → risk 1.0  (very tight buffer, high supply risk)
        S/U  = 23.5% → risk 0.5
        S/U >= 35%  → risk 0.0  (ample buffer, low supply risk)
    """
    span = _STU_RISK_AMPLE - _STU_RISK_TIGHT
    return float(max(0.0, min(1.0, (_STU_RISK_AMPLE - stu_pct) / span)))


# ── Private helpers ────────────────────────────────────────────────────────────


def _world_stu(
    df: pd.DataFrame, start: date, end: date
) -> tuple[list[FeatureObservation], str | None]:
    """Aggregate the PSD frame to world stocks-to-use % per marketing year.

    Returns (observations, structural_error). A structural_error (non-None)
    means the file is missing required columns or attributes and the caller
    should treat the run as FAILED. Per-year gaps (a marketing year missing one
    attribute) are skipped silently — not an error.
    """
    required_cols = {"Commodity_Code", "Market_Year", "Attribute_ID", "Value"}
    missing = required_cols - set(df.columns)
    if missing:
        return [], f"PSD CSV missing columns: {missing}"

    coffee = df[df["Commodity_Code"] == _COMMODITY_CODE]
    sub = coffee[coffee["Attribute_ID"].isin([_ENDING_STOCKS_ATTR, _CONSUMPTION_ATTR])]
    if sub.empty:
        return [], "PSD CSV has no Ending Stocks / Domestic Consumption rows for coffee"

    # Sum across all countries → world total per marketing year per attribute
    pivot = sub.pivot_table(
        index="Market_Year", columns="Attribute_ID", values="Value", aggfunc="sum"
    )
    if _ENDING_STOCKS_ATTR not in pivot.columns or _CONSUMPTION_ATTR not in pivot.columns:
        return [], (
            f"PSD pivot missing attribute "
            f"{_ENDING_STOCKS_ATTR} or {_CONSUMPTION_ATTR}"
        )

    observations: list[FeatureObservation] = []
    for market_year, row in pivot.iterrows():
        ending = row[_ENDING_STOCKS_ATTR]
        consumption = row[_CONSUMPTION_ATTR]
        if pd.isna(ending) or pd.isna(consumption) or consumption == 0:
            continue  # incomplete marketing year — skip silently

        observed_date = date(int(market_year), 12, 31)
        if observed_date < start or observed_date > end:
            continue

        observations.append(
            FeatureObservation(
                asset_id=USDA_STU.asset_id,
                observed_date=observed_date,
                feature_name=_FEATURE_NAME,
                value=stocks_to_use(float(ending), float(consumption)),
                source=_SOURCE_TAG,
            )
        )

    observations.sort(key=lambda o: o.observed_date)
    return observations, None


def _failed_run(started_at: datetime, error_message: str) -> SourceRun:
    logger.error("USDA PSD fetch failed: %s", error_message)
    return SourceRun(
        source_id=_SOURCE_ID,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=RunStatus.FAILED,
        records_fetched=0,
        records_stored=0,
        error_message=error_message,
    )
