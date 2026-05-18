"""Price feature engineering — 52-week range, position, YoY change, momentum."""
import pandas as pd


def price_position_52w(prices: pd.Series) -> pd.Series:
    """Compute (price - 52w_low) / (52w_high - 52w_low), range 0–1.

    0 = lowest price in 52 weeks (buy signal), 1 = highest (caution signal).
    Uses 252 trading-day rolling window on daily data.
    """
    ...


def yoy_price_change(prices: pd.Series) -> pd.Series:
    """Year-over-year price change as a decimal (e.g. 0.10 = +10%)."""
    ...


def price_momentum_12m(prices: pd.Series) -> pd.Series:
    """12-month trailing return. Use for wind-direction context only — not entry signal.

    WARNING: r=+0.93 correlation is partly reflexive. Do not use as a buy/sell signal.
    """
    ...
