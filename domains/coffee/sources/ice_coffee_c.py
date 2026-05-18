"""ICE Arabica C futures — daily prices via Nasdaq Data Link CHRIS/ICE_KC1.

Phase 0 priority: implement first (no auth beyond API key, no GEE needed).
Series: continuous front-month adjusted — avoids manual roll management.
"""
from datetime import date

import pandas as pd

from core.models.observation import MarketObservation

_SERIES = "CHRIS/ICE_KC1"
_BASE_URL = "https://data.nasdaq.com/api/v3/datasets"


def fetch(start: date, end: date) -> list[MarketObservation]:
    """Fetch daily close prices for ICE KC=F between start and end dates."""
    ...


def _parse_response(data: dict) -> pd.DataFrame:
    """Parse Nasdaq Data Link dataset response into a tidy DataFrame."""
    ...
