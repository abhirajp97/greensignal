"""Market and feature observation schemas — time-series data storage units."""
from datetime import date

from pydantic import BaseModel


class MarketObservation(BaseModel):
    """A single price or market-quoted data point for an asset."""

    asset_id: str
    observed_date: date
    value: float
    unit: str
    source: str          # e.g. "nasdaq:CHRIS/ICE_KC1"
    raw: dict | None = None


class FeatureObservation(BaseModel):
    """A derived feature value (signal input) for an asset at a point in time."""

    asset_id: str
    observed_date: date
    feature_name: str    # e.g. "price_position_52w", "stocks_to_use_pct"
    value: float
    source: str
