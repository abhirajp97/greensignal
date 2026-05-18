"""CHIRPS rainfall — monthly precipitation anomaly for coffee-growing regions.

Status: PENDING Google Earth Engine approval (1–2 day turnaround).
GEE dataset: UCSB-CHG/CHIRPS/PENTAD aggregated to monthly.
Fallback: direct NetCDF download from data.chc.ucsb.edu (no approval needed).
Region: Minas Gerais, Brazil (see domains/coffee/registry/regions.py for bbox).
Strongest signal during flowering season: September–November.
"""
from datetime import date
from pathlib import Path

from core.models.observation import FeatureObservation


def fetch_via_gee(start: date, end: date) -> list[FeatureObservation]:
    """Extract area-averaged monthly precipitation for Minas Gerais via GEE API."""
    ...


def load_from_netcdf(path: Path) -> list[FeatureObservation]:
    """Parse CHIRPS NetCDF file and extract Minas Gerais region average."""
    ...


def drought_risk_score(anomaly_mm: float, is_flowering_season: bool) -> float:
    """Convert rainfall anomaly to 0–1 drought risk score.

    Negative anomaly (below-normal rain) during flowering season → high risk.
    """
    ...
