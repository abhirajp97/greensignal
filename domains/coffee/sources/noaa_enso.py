"""NOAA CPC Oceanic Niño Index (ONI) — monthly ENSO state signal.

Source:  NOAA Climate Prediction Center
URL:     https://cpc.ncep.noaa.gov/data/indices/oni.ascii.txt
Auth:    None (free, no API key required)
Freq:    Updated monthly; each row is a 3-month running mean of SST anomalies
         in the Niño 3.4 region (5N–5S, 120–170W), expressed in °C.

Format (fixed-width, space-delimited):
    SEAS YR   TOTAL  ANOM
     DJF 1950  26.03  -0.53
     JFM 1950  26.54  -0.51
     ...
  - SEAS: 3-letter season code (DJF, JFM, … NDJ)
  - YR:   4-digit year (see year-boundary note below)
  - TOTAL: absolute SST (°C) — not used
  - ANOM:  ONI anomaly (°C) — the signal value we keep

Year-boundary rule (NOAA convention):
  YR is the calendar year of the MIDDLE month of the season.
    DJF 1950 → Dec 1949, Jan 1950, Feb 1950 → middle = Jan 1950 → YR = 1950
    NDJ 1950 → Nov 1950, Dec 1950, Jan 1951 → middle = Dec 1950 → YR = 1950
  Observation date is assigned to the LAST day of the season's final month.
    DJF 1950 → 1950-02-28 (or 29 in a leap year)
    NDJ 1950 → 1951-01-31  ← end month is in YR+1

Missing-value sentinel: NOAA uses -99.9 for not-yet-published seasons.

ENSO thresholds:
    ONI ≥ +0.5 for ≥ 5 consecutive seasons → El Niño (warm)
    ONI ≤ −0.5 for ≥ 5 consecutive seasons → La Niña (cool)
    La Niña → drought risk in Brazil / Vietnam → higher coffee prices 18–24 m later.

Usage in composite:
    Apply 18- and 24-month lags before correlating with Arabica prices.
    `enso_risk_score()` converts a raw ONI anomaly to a 0–1 supply-risk score.
"""

import calendar
import logging
from datetime import UTC, date, datetime

import httpx

from core.models.observation import FeatureObservation
from core.models.source_run import RunStatus, SourceRun
from core.services import data_quality
from domains.coffee.registry.assets import ENSO_ONI

_URL = "https://cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"

_SOURCE_ID = "coffee:noaa_enso"
_SOURCE_TAG = "noaa:oni"
_FEATURE_NAME = "oni_anom"
_UNIT = "degC"

# ONI values outside this range are almost certainly sentinel / corrupt data
_ONI_MIN = -4.0
_ONI_MAX = 4.0

# NOAA sentinel for not-yet-published values
_MISSING_SENTINEL = -99.9

# Map season code → end month (the final month of the 3-month window)
# NDJ is the only season whose end month is in YR+1 (January of the following year)
_SEASON_END_MONTH: dict[str, int] = {
    "DJF": 2,
    "JFM": 3,
    "FMA": 4,
    "MAM": 5,
    "AMJ": 6,
    "MJJ": 7,
    "JJA": 8,
    "JAS": 9,
    "ASO": 10,
    "SON": 11,
    "OND": 12,
    "NDJ": 1,  # end month is January of YR+1
}

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────────


def fetch(start: date, end: date) -> tuple[list[FeatureObservation], SourceRun]:
    """Download the full ONI time series and return observations in [start, end].

    Returns a tuple of (observations, source_run). The source_run is always
    returned even on failure. Each returned observation holds the raw ONI
    anomaly (°C) for that season's end date. Apply a lag before use.
    """
    started_at = datetime.now(UTC)

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(_URL)
            resp.raise_for_status()
            raw_text = resp.text
    except httpx.HTTPStatusError as exc:
        return [], _failed_run(
            started_at,
            f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
        )
    except httpx.RequestError as exc:
        return [], _failed_run(started_at, f"Request error: {exc}")

    observations, parse_errors = _parse_oni_text(raw_text, start, end)

    if observations:
        dates = [o.observed_date for o in observations]
        values = [o.value for o in observations]
        gaps = data_quality.check_no_gaps(dates, max_gap_days=62)
        oob = data_quality.check_value_range(values, low=_ONI_MIN, high=_ONI_MAX)
        if gaps:
            logger.warning(
                "%s: gap check found %d gap(s) in ONI data", _SOURCE_ID, len(gaps)
            )
        if oob:
            logger.warning(
                "%s: %d value(s) outside expected ONI range [%.1f, %.1f]",
                _SOURCE_ID, len(oob), _ONI_MIN, _ONI_MAX,
            )

    status = RunStatus.PARTIAL if parse_errors else RunStatus.SUCCESS
    error_msg = f"{parse_errors} rows skipped due to parse errors" if parse_errors else None

    return observations, SourceRun(
        source_id=_SOURCE_ID,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=status,
        records_fetched=len(observations),
        records_stored=0,
        error_message=error_msg,
    )


def enso_risk_score(oni: float) -> float:
    """Convert a raw ONI anomaly to a 0–1 supply-risk score for the composite.

    Risk increases with La Niña severity (negative ONI) because La Niña causes
    drought in Brazil's Minas Gerais and Vietnam's Central Highlands ~18–24 m later.
    El Niño (positive ONI) also carries risk but the mechanism is different and
    the effect on Arabica prices is weaker at the same lag.

    Scale (linear, clamped):
        ONI ≤ −1.5  → risk = 1.0  (strong La Niña, high supply risk)
        ONI =  0.0  → risk = 0.5  (neutral, moderate background risk)
        ONI ≥ +1.5  → risk = 0.0  (strong El Niño, low near-term supply risk)
    """
    # Linear interpolation: score = 0.5 - oni/3, clamped to [0, 1]
    return float(max(0.0, min(1.0, 0.5 - oni / 3.0)))


# ── Private helpers ────────────────────────────────────────────────────────────


def _parse_oni_text(
    raw_text: str, start: date, end: date
) -> tuple[list[FeatureObservation], int]:
    """Parse NOAA ONI fixed-width text into FeatureObservation objects.

    Returns (observations, error_count).
    """
    observations: list[FeatureObservation] = []
    error_count = 0

    for line in raw_text.splitlines():
        parts = line.split()
        # Header and blank lines have fewer than 4 tokens or start with "SEAS"
        if len(parts) < 4 or parts[0] == "SEAS":
            continue

        season_code = parts[0].upper()
        if season_code not in _SEASON_END_MONTH:
            continue  # unrecognised season — skip silently

        try:
            yr = int(parts[1])
            oni_anom = float(parts[3])
        except (ValueError, IndexError) as exc:
            error_count += 1
            logger.warning("Cannot parse ONI row %r: %s", line.strip(), exc)
            continue

        # Skip NOAA's not-yet-published sentinel
        if abs(oni_anom - _MISSING_SENTINEL) < 0.01:
            continue

        try:
            observed_date = _season_to_date(season_code, yr)
        except (ValueError, KeyError) as exc:
            error_count += 1
            logger.warning(
                "Cannot convert season %r yr %d to date: %s", season_code, yr, exc
            )
            continue

        if observed_date < start or observed_date > end:
            continue

        observations.append(
            FeatureObservation(
                asset_id=ENSO_ONI.asset_id,
                observed_date=observed_date,
                feature_name=_FEATURE_NAME,
                value=oni_anom,
                source=_SOURCE_TAG,
            )
        )

    return observations, error_count


def _season_to_date(season: str, yr: int) -> date:
    """Convert a NOAA season code + year to the last day of the season's final month.

    NOAA's YR is the year of the middle month.  NDJ is the only season whose
    final month (January) falls in the year after YR.

    Examples:
        _season_to_date("DJF", 1950) → date(1950, 2, 28)
        _season_to_date("NDJ", 1950) → date(1951, 1, 31)
        _season_to_date("DJF", 2000) → date(2000, 2, 29)  # leap year
    """
    end_month = _SEASON_END_MONTH[season]
    end_year = yr + 1 if season == "NDJ" else yr
    last_day = calendar.monthrange(end_year, end_month)[1]
    return date(end_year, end_month, last_day)


def _failed_run(started_at: datetime, error_message: str) -> SourceRun:
    logger.error("NOAA ENSO fetch failed: %s", error_message)
    return SourceRun(
        source_id=_SOURCE_ID,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=RunStatus.FAILED,
        records_fetched=0,
        records_stored=0,
        error_message=error_message,
    )
