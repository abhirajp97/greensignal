"""CHIRPS rainfall — monthly precipitation for Brazil's Arabica region (Minas Gerais).

Source:  UCSB Climate Hazards Group InfraRed Precipitation with Station data
GEE:     UCSB-CHG/CHIRPS/PENTAD (5-day, ~5.5 km), aggregated to monthly here
Auth:    Google Earth Engine — interactive `earthengine authenticate` (cached at
         ~/.config/earthengine/) plus a Cloud project in env `EARTHENGINE_PROJECT`.
Region:  FAO GAUL level-1 polygon, ADM1_NAME == "Minas Gerais" (true state shape,
         more accurate than the rectangular bbox in registry/regions.py).

The signal (L3): below-normal rainfall over Minas Gerais during the Sep-Nov
flowering season threatens the next crop, which is bullish for Arabica price.

`fetch()` returns RAW monthly area-mean precipitation (mm) — anomaly vs
climatology and flowering-season risk are derived downstream (see
`drought_risk_score` and notebook 05), mirroring how ENSO returns raw ONI.

Fallback: `load_from_netcdf()` reads a direct CHIRPS NetCDF (data.chc.ucsb.edu),
needs no GEE approval but requires `xarray` (not a hard dependency).
"""

import calendar
import logging
import os
from datetime import UTC, date, datetime
from pathlib import Path

import ee

from core.models.observation import FeatureObservation
from core.models.source_run import RunStatus, SourceRun
from core.services import data_quality
from domains.coffee.registry.assets import CHIRPS_MINAS
from domains.coffee.registry.regions import MINAS_GERAIS

_GEE_PROJECT_ENV = "EARTHENGINE_PROJECT"
_CHIRPS_COLLECTION = "UCSB-CHG/CHIRPS/PENTAD"
_GAUL_COLLECTION = "FAO/GAUL/2015/level1"
_REGION_ADM1 = "Minas Gerais"
_CHIRPS_SCALE_M = 5566  # CHIRPS native resolution (~0.05°)

_SOURCE_ID = "coffee:chirps"
_SOURCE_TAG = "gee:chirps_pentad"
_FEATURE_NAME = "precip_mm"

# Flowering season for Brazilian Arabica (Southern Hemisphere spring)
_FLOWERING_MONTHS = {9, 10, 11}

# Sanity bounds for monthly area-mean rainfall over Minas Gerais (mm)
_PRECIP_MIN = 0.0
_PRECIP_MAX = 1500.0

# Provisional drought-risk reference: a -60 mm monthly anomaly ≈ full risk.
# Calibrate against notebook 05.
_DROUGHT_REF_MM = 60.0

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────────


def fetch(start: date, end: date) -> tuple[list[FeatureObservation], SourceRun]:
    """Fetch monthly area-mean CHIRPS rainfall over Minas Gerais via GEE.

    Returns a tuple of (observations, source_run); the source_run is always
    returned even on failure. One observation per month in [start, end] carrying
    raw area-mean precipitation (mm), anchored to month-end.
    """
    started_at = datetime.now(UTC)

    try:
        records = _query_monthly_precip(start, end)
    except ee.EEException as exc:
        return [], _failed_run(started_at, f"Earth Engine error: {exc}")

    observations: list[FeatureObservation] = []
    for month_start, precip in records:
        if precip is None:
            continue  # no CHIRPS coverage that month — skip silently
        observed_date = _month_end(month_start)
        if observed_date < start or observed_date > end:
            continue
        observations.append(
            FeatureObservation(
                asset_id=CHIRPS_MINAS.asset_id,
                observed_date=observed_date,
                feature_name=_FEATURE_NAME,
                value=float(precip),
                source=_SOURCE_TAG,
            )
        )

    observations.sort(key=lambda o: o.observed_date)

    if observations:
        dates = [o.observed_date for o in observations]
        values = [o.value for o in observations]
        gaps = data_quality.check_no_gaps(dates, max_gap_days=62)
        oob = data_quality.check_value_range(values, low=_PRECIP_MIN, high=_PRECIP_MAX)
        if gaps:
            logger.warning(
                "%s: gap check found %d gap(s) in CHIRPS months", _SOURCE_ID, len(gaps)
            )
        if oob:
            logger.warning(
                "%s: %d rainfall value(s) outside [%.0f, %.0f] mm",
                _SOURCE_ID, len(oob), _PRECIP_MIN, _PRECIP_MAX,
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


def load_from_netcdf(path: Path) -> list[FeatureObservation]:
    """Parse a CHIRPS NetCDF file and extract the Minas Gerais area mean.

    No-GEE fallback. Requires `xarray` (optional dependency); raises a clear
    ImportError if it is not installed. Averages over the MINAS_GERAIS bounding
    box (rectangular approximation — the GEE path uses the true GAUL polygon).
    """
    try:
        import xarray as xr
    except ImportError as exc:  # pragma: no cover - exercised via test guard
        raise ImportError(
            "load_from_netcdf requires `xarray` (and a NetCDF engine). "
            "Install it or use fetch() via Google Earth Engine instead."
        ) from exc

    ds = xr.open_dataset(path)
    box = ds["precip"].sel(
        latitude=slice(MINAS_GERAIS.lat_min, MINAS_GERAIS.lat_max),
        longitude=slice(MINAS_GERAIS.lon_min, MINAS_GERAIS.lon_max),
    )
    monthly = box.mean(dim=["latitude", "longitude"])

    observations: list[FeatureObservation] = []
    for t, value in zip(monthly["time"].values, monthly.values, strict=True):
        d = _month_end(date(int(str(t)[:4]), int(str(t)[5:7]), 1))
        observations.append(
            FeatureObservation(
                asset_id=CHIRPS_MINAS.asset_id,
                observed_date=d,
                feature_name=_FEATURE_NAME,
                value=float(value),
                source="netcdf:chirps",
            )
        )
    ds.close()
    return observations


def drought_risk_score(anomaly_mm: float, is_flowering_season: bool) -> float:
    """Convert a monthly rainfall anomaly to a 0–1 drought-risk score.

    Risk rises as rainfall falls below normal (negative anomaly). Off-season
    deficits matter less, so their risk is halved.

    Scale (provisional, calibrate in notebook 05):
        anomaly ≥ 0           → risk 0.0  (at/above normal rain)
        anomaly = -60 mm      → risk 1.0  during flowering season
        off-season            → risk is halved
    """
    deficit = max(0.0, -anomaly_mm)
    base = min(1.0, deficit / _DROUGHT_REF_MM)
    if not is_flowering_season:
        base *= 0.5
    return float(base)


def is_flowering_month(month: int) -> bool:
    """True if `month` (1-12) falls in the Sep-Nov Arabica flowering window."""
    return month in _FLOWERING_MONTHS


# ── Private helpers ────────────────────────────────────────────────────────────


def _initialize() -> None:
    """Initialise the Earth Engine client using the project from the environment."""
    project = os.environ.get(_GEE_PROJECT_ENV)
    if project:
        ee.Initialize(project=project)
    else:
        # May still succeed if a default project is configured in the EE config.
        ee.Initialize()


def _query_monthly_precip(start: date, end: date) -> list[tuple[date, float | None]]:
    """Run the GEE query and return (month_start, area_mean_precip_mm | None) rows.

    All Earth Engine interaction is isolated here so callers (and tests) deal
    only in plain Python. One `getInfo()` round trip aggregates server-side.
    """
    _initialize()

    region = (
        ee.FeatureCollection(_GAUL_COLLECTION)
        .filter(ee.Filter.eq("ADM1_NAME", _REGION_ADM1))
        .geometry()
    )
    chirps = (
        ee.ImageCollection(_CHIRPS_COLLECTION)
        .select("precipitation")
        .filterDate(start.isoformat(), end.isoformat())
    )

    n_months = (end.year - start.year) * 12 + (end.month - start.month) + 1
    start_ee = ee.Date(start.isoformat())

    def monthly(m):
        d0 = start_ee.advance(ee.Number(m), "month")
        d1 = d0.advance(1, "month")
        total = chirps.filterDate(d0, d1).sum()
        mean = total.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=_CHIRPS_SCALE_M,
            maxPixels=int(1e9),
        ).get("precipitation")
        return ee.Feature(None, {"date": d0.format("YYYY-MM-dd"), "precip": mean})

    months = ee.List.sequence(0, n_months - 1)
    info = ee.FeatureCollection(months.map(monthly)).getInfo()

    out: list[tuple[date, float | None]] = []
    for feature in info.get("features", []):
        props = feature.get("properties", {})
        date_str = props.get("date")
        if not date_str:
            continue
        precip = props.get("precip")
        out.append((date.fromisoformat(date_str), None if precip is None else float(precip)))
    return out


def _month_end(d: date) -> date:
    """Return the last day of the month containing `d`."""
    last = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last)


def _failed_run(started_at: datetime, error_message: str) -> SourceRun:
    logger.error("CHIRPS fetch failed: %s", error_message)
    return SourceRun(
        source_id=_SOURCE_ID,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=RunStatus.FAILED,
        records_fetched=0,
        records_stored=0,
        error_message=error_message,
    )
