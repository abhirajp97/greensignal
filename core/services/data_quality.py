"""Data quality checks — detect missing values, outliers, and unexpected gaps."""
from datetime import date


def check_no_gaps(dates: list[date], max_gap_days: int) -> list[tuple[date, date]]:
    """Return list of (start, end) gaps exceeding max_gap_days."""
    ...


def check_value_range(values: list[float], low: float, high: float) -> list[int]:
    """Return indices of values outside [low, high]."""
    ...
