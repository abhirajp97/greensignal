"""Shared forecasting interface — wraps model backends (NeuralProphet, ARIMA-X)."""
import pandas as pd

from core.models.forecast import Forecast


def fit_and_forecast(
    prices: pd.DataFrame,
    features: pd.DataFrame,
    asset_id: str,
    horizon_days: int = 90,
) -> Forecast:
    """Fit a time-series model and return a Forecast for the given horizon."""
    ...
