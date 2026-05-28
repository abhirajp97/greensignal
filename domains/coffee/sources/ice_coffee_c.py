"""ICE Arabica C futures — daily prices via Nasdaq Data Link CHRIS/ICE_KC1.

Phase 0 priority: implement first (no auth beyond API key, no GEE needed).
Series: continuous front-month adjusted — avoids manual roll management.
"""
import logging
import os
from datetime import UTC, date, datetime

import httpx

from core.models.observation import MarketObservation
from core.models.source_run import RunStatus, SourceRun
from core.services import data_quality
from domains.coffee.registry.assets import ICE_ARABICA_BENCHMARK

_SERIES = "CHRIS/ICE_KC1"
_BASE_URL = "https://data.nasdaq.com/api/v3/datasets"
_SOURCE_ID = "coffee:ice_coffee_c"
_ASSET_ID = ICE_ARABICA_BENCHMARK.asset_id
_SOURCE_TAG = f"nasdaq:{_SERIES}"
_UNIT = "USc/lb"

logger = logging.getLogger(__name__)


def fetch(start: date, end: date) -> tuple[list[MarketObservation], SourceRun]:
    """Fetch daily settle prices for ICE KC=F between start and end dates."""
    started_at = datetime.now(UTC)
    api_key = os.environ["NASDAQ_API_KEY"]

    url = f"{_BASE_URL}/{_SERIES}.json"
    params = {
        "api_key": api_key,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "order": "asc",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return [], _failed_run(
            started_at,
            f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
        )
    except httpx.RequestError as exc:
        return [], _failed_run(started_at, f"Request error: {exc}")

    observations, parse_errors = _parse_response(response.json())

    dates = [obs.observed_date for obs in observations]
    if dates:
        # ICE trades ~5 days/week; allow 7-day gap to cover holiday weeks
        for gap_start, gap_end in data_quality.check_no_gaps(dates, max_gap_days=7):
            logger.warning("Gap in ICE KC data: %s → %s", gap_start, gap_end)

        values = [obs.value for obs in observations]
        for idx in data_quality.check_value_range(values, low=30.0, high=500.0):
            logger.warning("Suspicious price at %s: %.2f USc/lb", dates[idx], values[idx])

    status = RunStatus.PARTIAL if parse_errors else RunStatus.SUCCESS
    error_message = f"{parse_errors} rows skipped due to parse errors" if parse_errors else None

    return observations, SourceRun(
        source_id=_SOURCE_ID,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=status,
        records_fetched=len(observations),
        records_stored=0,
        error_message=error_message,
    )


def _parse_response(data: dict) -> tuple[list[MarketObservation], int]:
    """Parse Nasdaq Data Link dataset response. Returns (observations, error_count)."""
    dataset = data["dataset"]
    column_names: list[str] = dataset["column_names"]
    rows: list[list] = dataset["data"]

    try:
        date_idx = column_names.index("Date")
        settle_idx = column_names.index("Settle")
    except ValueError as exc:
        raise ValueError(f"Unexpected column layout in Nasdaq response: {exc}") from exc

    observations: list[MarketObservation] = []
    error_count = 0

    for row in rows:
        try:
            observed_date = date.fromisoformat(row[date_idx])
            settle = float(row[settle_idx])
            observations.append(
                MarketObservation(
                    asset_id=_ASSET_ID,
                    observed_date=observed_date,
                    value=settle,
                    unit=_UNIT,
                    source=_SOURCE_TAG,
                    raw=dict(zip(column_names, row)),
                )
            )
        except (TypeError, ValueError, IndexError) as exc:
            logger.warning("Skipping malformed row %s: %s", row, exc)
            error_count += 1

    return observations, error_count


def _failed_run(started_at: datetime, error_message: str) -> SourceRun:
    return SourceRun(
        source_id=_SOURCE_ID,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=RunStatus.FAILED,
        records_fetched=0,
        records_stored=0,
        error_message=error_message,
    )
