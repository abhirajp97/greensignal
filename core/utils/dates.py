"""Date utilities — month-end alignment, lag shifts, season helpers."""
from datetime import date


def month_end(d: date) -> date:
    """Return the last day of the month containing d."""
    ...


def shift_months(d: date, n: int) -> date:
    """Shift d by n calendar months (negative = back)."""
    ...


def flowering_season(d: date) -> bool:
    """Return True if d falls in Brazil's Arabica flowering season (Sep–Nov)."""
    return d.month in (9, 10, 11)
