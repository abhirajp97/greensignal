"""CHIRPS rainfall — monthly precipitation for India's Arabica/Robusta districts.

Source:  UCSB Climate Hazards Group InfraRed Precipitation with Station data
GEE:     UCSB-CHG/CHIRPS/PENTAD (5-day, ~5.5 km), aggregated to monthly here
Auth:    Google Earth Engine — interactive `earthengine authenticate` (cached at
         ~/.config/earthengine/) plus a Cloud project in env `EARTHENGINE_PROJECT`.
Region:  FAO GAUL level-2 polygon (district granularity, not level-1/state like
         chirps.py's Minas Gerais). Supports Kodagu (default), Chikmagalur, and
         Hassan — Karnataka's three largest coffee districts by production (see
         coffee_board_india_supply.py) — via the `district` parameter, so a
         production-weighted multi-district signal can be built without
         duplicating this module three times. GAUL's own district spelling is
         used ("Chikmagalur", not Coffee Board's "Chikkamagaluru" — confirmed
         live: `ee.FeatureCollection("FAO/GAUL/2015/level2").filter(ADM1_NAME==
         "Karnataka")` lists "Chikmagalur").

This is a new module rather than a parameterization of chirps.py — that file backs
the validated, live Brazil composite, and refactoring tested/working code for
marginal reuse benefit isn't worth the risk. Only the module constants below differ
from chirps.py; the GEE query logic is otherwise identical.

The signal: below-normal rainfall over a district during the species-specific
blossom shower window threatens flowering, which is bullish for price — the same
causal role Brazil's Sep-Nov spring rain plays for Minas Gerais, but on India's
calendar, NOT copied from Brazil's. **Robusta and Arabica do not share one
window** (an earlier version of this file used a single Feb-Mar window for both —
corrected after checking real agronomy sources, see `_FLOWERING_MONTHS_BY_SPECIES`):
Robusta's pre-monsoon "blossom showers" arrive late Feb-mid Mar, while Arabica
needs rain by mid-April; both need a "backing shower" ~2 weeks after the initial
blossom for the cherries to set. The same windows are used across all three
districts (they share Karnataka's broad climate zone/agronomy timing) — a
simplifying assumption, not independently verified per-district.

`fetch()` returns RAW monthly area-mean precipitation (mm) — anomaly vs climatology
and flowering-season risk are derived downstream (see `drought_risk_score`),
mirroring chirps.py.

Fallback: `load_from_netcdf()` reads a direct CHIRPS NetCDF (data.chc.ucsb.edu),
needs no GEE approval but requires `xarray` (not a hard dependency).
"""

import calendar
import logging
import os
from datetime import UTC, date, datetime
from pathlib import Path

import ee

from core.models.asset import Asset
from core.models.observation import FeatureObservation
from core.models.source_run import RunStatus, SourceRun
from core.services import data_quality
from domains.coffee.registry.assets import CHIRPS_CHIKMAGALUR, CHIRPS_HASSAN, CHIRPS_KODAGU
from domains.coffee.registry.regions import CHIKMAGALUR, HASSAN, KODAGU, Region

_GEE_PROJECT_ENV = "EARTHENGINE_PROJECT"
_CHIRPS_COLLECTION = "UCSB-CHG/CHIRPS/PENTAD"
_GAUL_COLLECTION = "FAO/GAUL/2015/level2"  # district, not state — see module docstring
_CHIRPS_SCALE_M = 5566  # CHIRPS native resolution (~0.05°)

# district (GAUL ADM2_NAME spelling) -> (asset, netcdf-fallback bbox)
_DISTRICTS: dict[str, tuple[Asset, Region]] = {
    "Kodagu": (CHIRPS_KODAGU, KODAGU),
    "Chikmagalur": (CHIRPS_CHIKMAGALUR, CHIKMAGALUR),
    "Hassan": (CHIRPS_HASSAN, HASSAN),
}
_DEFAULT_DISTRICT = "Kodagu"

_SOURCE_ID = "coffee:chirps_india"
_SOURCE_TAG = "gee:chirps_pentad_india"
_FEATURE_NAME = "precip_mm"

# Species-specific Karnataka blossom-shower windows — NOT Brazil's Sep-Nov, and NOT
# one shared window (Robusta and Arabica blossom at different times; see module
# docstring). Provisional; calibrate against notebook 09, same status as
# _DROUGHT_REF_MM below.
#   Robusta: pre-monsoon blossom showers late Feb-mid Mar + ~2wk backing shower.
#   Arabica: needs rain by mid-April to blossom + ~2wk backing shower (into May).
_FLOWERING_MONTHS_BY_SPECIES: dict[str, set[int]] = {
    "robusta": {2, 3},
    "arabica": {4, 5},
}

# Sanity bounds for monthly area-mean rainfall over these districts (mm). Wetter
# than Minas Gerais (heavy SW monsoon, Jun-Sep) so the upper bound is higher.
_PRECIP_MIN = 0.0
_PRECIP_MAX = 2500.0

# Provisional drought-risk reference: a -60 mm monthly anomaly ≈ full risk during
# the blossom window. Same starting point as chirps.py's Brazil value; calibrate
# against notebook 09 rather than assuming it transfers as-is.
_DROUGHT_REF_MM = 60.0

# GEE's Dictionary.get(key, default) still raises if default is null/None (server-
# side "unless it is null" rule) — a real sentinel is needed to detect months with
# no CHIRPS coverage yet (e.g. very recent, not-yet-published months).
_NO_DATA_SENTINEL = -9999.0

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────────


def fetch(
    start: date, end: date, district: str = _DEFAULT_DISTRICT
) -> tuple[list[FeatureObservation], SourceRun]:
    """Fetch monthly area-mean CHIRPS rainfall over `district` via GEE.

    `district` must be one of `_DISTRICTS`' keys ("Kodagu", "Chikmagalur",
    "Hassan" — GAUL's own spelling) and defaults to Kodagu for backward
    compatibility with existing callers. Returns a tuple of (observations,
    source_run); the source_run is always returned even on failure. One
    observation per month in [start, end] carrying raw area-mean precipitation
    (mm), anchored to month-end.
    """
    started_at = datetime.now(UTC)

    if district not in _DISTRICTS:
        return [], _failed_run(
            started_at, f"Unknown district {district!r}, expected one of {list(_DISTRICTS)}"
        )
    asset, _region = _DISTRICTS[district]

    try:
        records = _query_monthly_precip(start, end, district)
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
                asset_id=asset.asset_id,
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


def load_from_netcdf(path: Path, district: str = _DEFAULT_DISTRICT) -> list[FeatureObservation]:
    """Parse a CHIRPS NetCDF file and extract `district`'s area mean.

    No-GEE fallback. Requires `xarray` (optional dependency); raises a clear
    ImportError if it is not installed. Averages over the district's bounding box
    (rectangular approximation — the GEE path uses the true GAUL polygon).
    """
    if district not in _DISTRICTS:
        raise ValueError(f"Unknown district {district!r}, expected one of {list(_DISTRICTS)}")
    asset, region = _DISTRICTS[district]

    try:
        import xarray as xr
    except ImportError as exc:  # pragma: no cover - exercised via test guard
        raise ImportError(
            "load_from_netcdf requires `xarray` (and a NetCDF engine). "
            "Install it or use fetch() via Google Earth Engine instead."
        ) from exc

    ds = xr.open_dataset(path)
    box = ds["precip"].sel(
        latitude=slice(region.lat_min, region.lat_max),
        longitude=slice(region.lon_min, region.lon_max),
    )
    monthly = box.mean(dim=["latitude", "longitude"])

    observations: list[FeatureObservation] = []
    for t, value in zip(monthly["time"].values, monthly.values, strict=True):
        d = _month_end(date(int(str(t)[:4]), int(str(t)[5:7]), 1))
        observations.append(
            FeatureObservation(
                asset_id=asset.asset_id,
                observed_date=d,
                feature_name=_FEATURE_NAME,
                value=float(value),
                source="netcdf:chirps_india",
            )
        )
    ds.close()
    return observations


def drought_risk_score(anomaly_mm: float, is_flowering_season: bool) -> float:
    """Convert a monthly rainfall anomaly to a 0–1 drought-risk score.

    Risk rises as rainfall falls below normal (negative anomaly). Off-season
    deficits matter less, so their risk is halved. `is_flowering_season` should
    come from `is_flowering_month(month, species)` — species-specific, since
    Robusta and Arabica blossom at different times (see module docstring).

    Scale (provisional, calibrate in notebook 09):
        anomaly ≥ 0           → risk 0.0  (at/above normal rain)
        anomaly = -60 mm      → risk 1.0  during that species' blossom window
        off-season            → risk is halved
    """
    deficit = max(0.0, -anomaly_mm)
    base = min(1.0, deficit / _DROUGHT_REF_MM)
    if not is_flowering_season:
        base *= 0.5
    return float(base)


def is_flowering_month(month: int, species: str) -> bool:
    """True if `month` (1-12) falls in `species`' Karnataka blossom window.

    `species` is "robusta" or "arabica" — they do NOT share one window (Robusta
    blossoms late Feb-mid Mar, Arabica needs rain by mid-April). Raises KeyError
    for any other value, rather than silently defaulting to one species' window.
    Same window used across all three districts (see module docstring).
    """
    return month in _FLOWERING_MONTHS_BY_SPECIES[species]


# ── Private helpers ────────────────────────────────────────────────────────────


def _initialize() -> None:
    """Initialise the Earth Engine client using the project from the environment."""
    project = os.environ.get(_GEE_PROJECT_ENV)
    if project:
        ee.Initialize(project=project)
    else:
        # May still succeed if a default project is configured in the EE config.
        ee.Initialize()


def _query_monthly_precip(
    start: date, end: date, district: str
) -> list[tuple[date, float | None]]:
    """Run the GEE query and return (month_start, area_mean_precip_mm | None) rows.

    All Earth Engine interaction is isolated here so callers (and tests) deal
    only in plain Python. One `getInfo()` round trip aggregates server-side.
    """
    _initialize()

    region = (
        ee.FeatureCollection(_GAUL_COLLECTION)
        .filter(ee.Filter.eq("ADM2_NAME", district))
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
        ).get("precipitation", _NO_DATA_SENTINEL)
        return ee.Feature(None, {"date": d0.format("YYYY-MM-dd"), "precip": mean})

    months = ee.List.sequence(0, n_months - 1)
    info = ee.FeatureCollection(months.map(monthly)).getInfo()

    out: list[tuple[date, float | None]] = []
    for feature in info.get("features", []):
        props = feature.get("properties", {})
        date_str = props.get("date")
        if not date_str:
            continue
        out.append((date.fromisoformat(date_str), _precip_or_none(props.get("precip"))))
    return out


def _precip_or_none(raw_precip: float | None) -> float | None:
    """Map GEE's no-coverage sentinel (and None) to None; pass real values through."""
    if raw_precip is None or float(raw_precip) == _NO_DATA_SENTINEL:
        return None
    return float(raw_precip)


def _month_end(d: date) -> date:
    """Return the last day of the month containing `d`."""
    last = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last)


def _failed_run(started_at: datetime, error_message: str) -> SourceRun:
    logger.error("CHIRPS India fetch failed: %s", error_message)
    return SourceRun(
        source_id=_SOURCE_ID,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=RunStatus.FAILED,
        records_fetched=0,
        records_stored=0,
        error_message=error_message,
    )
