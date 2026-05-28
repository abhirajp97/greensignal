"""Price feature engineering — 52-week range, position, YoY change, momentum."""
import pandas as pd


def price_position_52w(prices: pd.Series) -> pd.Series:
    """Compute (price - 52w_low) / (52w_high - 52w_low), range 0–1.

    0 = lowest price in 52 weeks (buy signal), 1 = highest (caution signal).
    Auto-detects frequency: 252-period window for daily data, 12-period for monthly.
    """
    freq = pd.infer_freq(prices.index)
    is_monthly = bool(freq) and any(c in freq.upper() for c in ("M", "Q", "A", "Y"))
    window = 12 if is_monthly else 252
    min_periods = int(window * 0.7)

    rolling_min = prices.rolling(window=window, min_periods=min_periods).min()
    rolling_max = prices.rolling(window=window, min_periods=min_periods).max()
    spread = rolling_max - rolling_min
    return (prices - rolling_min) / spread.where(spread > 0)


def yoy_price_change(prices: pd.Series) -> pd.Series:
    """Year-over-year price change as a decimal (e.g. 0.10 = +10%).

    Uses 252-period lag for daily data, 12-period for monthly.
    """
    freq = pd.infer_freq(prices.index)
    is_monthly = bool(freq) and any(c in freq.upper() for c in ("M", "Q", "A", "Y"))
    return prices.pct_change(12 if is_monthly else 252)


def price_momentum_12m(prices: pd.Series) -> pd.Series:
    """12-month trailing return. Wind-direction context only — not a buy/sell signal.

    WARNING: r=+0.93 correlation with contemporaneous price is partly reflexive.
    """
    return yoy_price_change(prices)
