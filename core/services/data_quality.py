"""Data quality checks — detect missing values, outliers, and unexpected gaps."""
from datetime import date


def check_no_gaps(dates: list[date], max_gap_days: int) -> list[tuple[date, date]]:
    """Return list of (start, end) pairs where consecutive dates exceed max_gap_days apart."""
    if len(dates) < 2:
        return []
    sorted_dates = sorted(dates)
    return [
        (sorted_dates[i - 1], sorted_dates[i])
        for i in range(1, len(sorted_dates))
        if (sorted_dates[i] - sorted_dates[i - 1]).days > max_gap_days
    ]


def check_value_range(values: list[float], low: float, high: float) -> list[int]:
    """Return indices of values outside [low, high]."""
    return [i for i, v in enumerate(values) if v < low or v > high]
