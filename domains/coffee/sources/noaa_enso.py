"""NOAA CPC Oceanic Niño Index (ONI) — monthly ENSO state signal.

Phase 0 priority: implement second (free, no auth, direct URL download).
URL: https://cpc.ncep.noaa.gov/data/indices/oni.ascii.txt
Format: fixed-width text, NOT CSV. Seasons span year boundaries — parse carefully.
"""

import pandas as pd

from core.models.observation import FeatureObservation

_URL = "https://cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"

# ENSO thresholds (°C)
_LA_NINA_THRESHOLD = -0.5
_EL_NINO_THRESHOLD = 0.5


def fetch() -> list[FeatureObservation]:
    """Download and parse the full ONI time series, return as FeatureObservations."""
    ...


def _parse_oni_text(raw: str) -> pd.DataFrame:
    """Parse fixed-width ONI text file into a DataFrame with columns: date, oni."""
    ...


def enso_risk_score(oni: float) -> float:
    """Convert ONI value to a 0–1 supply risk score for use in the composite.

    La Niña (negative ONI) → higher Robusta supply risk.
    El Niño (positive ONI) → higher Arabica supply risk.
    """
    ...
