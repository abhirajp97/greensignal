"""CFTC Commitments of Traders — speculative positioning on ICE Coffee KC.

Phase 0 priority: implement third (free, no auth, annual CSVs from cftc.gov).
Use disaggregated report (NOT legacy) to get the "Managed Money" breakdown.
Market filter: rows where Market_and_Exchange_Names contains 'COFFEE C - ICE'.
Align weekly Tuesday positions to month-end for backtest.
"""

import pandas as pd

from core.models.observation import FeatureObservation

_BASE_URL = "https://www.cftc.gov/files/dea/history"
_MARKET_NAME = "COFFEE C - ICE FUTURES U.S."


def fetch(year: int) -> list[FeatureObservation]:
    """Download disaggregated COT report for a given year and extract KC positions."""
    ...


def _cot_index(series: pd.Series, window: int = 156) -> pd.Series:
    """Compute rolling COT index: (val - min) / (max - min) over trailing `window` weeks."""
    ...


def cot_contrarian_signal(cot_index: float) -> float:
    """Return contrarian signal: +1 if index < 25 (buy), -1 if > 75 (caution), else 0."""
    if cot_index < 25:
        return 1.0
    if cot_index > 75:
        return -1.0
    return 0.0
