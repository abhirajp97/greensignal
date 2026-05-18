"""Freshness checks — detect stale or missing data across sources."""
from datetime import date


def is_stale(last_updated: date, max_age_days: int) -> bool:
    """Return True if last_updated is older than max_age_days."""
    ...


def staleness_report(sources: dict[str, date], thresholds: dict[str, int]) -> dict[str, bool]:
    """Return a mapping of source_id → is_stale for all tracked sources."""
    ...
