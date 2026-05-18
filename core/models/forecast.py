"""Forecast schema — stores model prediction outputs and backtest metadata."""
from datetime import date, datetime

from pydantic import BaseModel, Field


class Forecast(BaseModel):
    """A price or signal forecast for an asset over a future horizon."""

    asset_id: str
    generated_at: datetime
    horizon_start: date
    horizon_end: date
    predicted_value: float
    confidence_low: float
    confidence_high: float
    model_name: str
    features_used: list[str] = Field(default_factory=list)
    backtest_mae: float | None = None
