"""
World Bank Commodity Price (Pink Sheet) — monthly Arabica and Robusta physical prices.

Source:  World Bank Research / Commodity Markets
Page:    https://www.worldbank.org/en/research/commodity-markets
Auth:    None (free, no API key required)
Freq:    Monthly (updated ~1 week into the following month)
Series:
  COFFEE_ARABIC — Other Mild Arabicas physical spot price (proxy for ICO Arabica indicator)
                  Colombia, Kenya, Tanzania washed coffees
  COFFEE_ROBUS  — Robusta physical spot price (proxy for ICO Robusta indicator)
                  Vietnam, Uganda robusta coffees
Units:  Source is USD/kg; converted to USc/lb (× 45.3592) for consistency with KC=F

Fetch strategy (two-step):
  1. GET the WB commodity markets page to scrape the current Excel download URL.
     The URL embeds a document hash that changes with each monthly update, so
     we cannot hardcode it.
  2. GET and parse the Excel file (sheet "Monthly Prices").

Quirks:
  - Date column uses "YYYYMmm" format, e.g. "2026M04" → end of April 2026.
  - Header row count is NOT stable — WB dropped the machine-code row entirely in
    a 2026-07-02 update (previously: row 4 = human name, 5 = unit, 6 = machine
    code, data from row 7; now: row 4 = human name, 5 = unit, data from row 6).
    The parser locates the first data row dynamically (first row whose column 0
    matches the "YYYYMmm" pattern) and searches every row above it for a target
    series label — matching either the legacy machine code (e.g. COFFEE_ARABIC)
    or the current human-readable name (e.g. "Coffee, Arabica") — rather than
    hardcoding row indices.
  - Some trailing rows may be empty — skip any row whose date does not match
    the expected pattern.
  - NaN values for recent months indicate data not yet published — skip silently.
"""

import calendar
import io
import logging
import re
from datetime import UTC, date, datetime

import httpx
import pandas as pd

from core.models.observation import MarketObservation
from core.models.source_run import RunStatus, SourceRun
from core.services import data_quality
from domains.coffee.registry.assets import WB_ARABICA_BENCHMARK, WB_ROBUSTA_BENCHMARK

_WB_PAGE_URL = "https://www.worldbank.org/en/research/commodity-markets"
_WB_EXCEL_RE = re.compile(
    r"https://thedocs\.worldbank\.org/en/doc/[^\"']+CMO-Historical-Data-Monthly\.xlsx"
)

# Conversion: 1 USD/kg = 100 cents/kg ÷ 2.20462 lb/kg = 45.3592 USc/lb
_USD_KG_TO_USC_LB: float = 100.0 / 2.20462

_SOURCE_ID = "coffee:world_bank_commodity"
_SOURCE_TAG = "world_bank:pink_sheet"
_UNIT = "USc/lb"
_DATE_RE = re.compile(r"^\d{4}M\d{2}$")

# Map WB series labels → asset_id. Both the legacy machine code and the current
# human-readable name are listed since WB has changed which one the file carries
# (see module docstring); whichever the live file has determines the column.
_SERIES_MATCH: dict[str, str] = {
    "COFFEE_ARABIC": WB_ARABICA_BENCHMARK.asset_id,
    "COFFEE_ROBUS": WB_ROBUSTA_BENCHMARK.asset_id,
    "Coffee, Arabica": WB_ARABICA_BENCHMARK.asset_id,
    "Coffee, Robusta": WB_ROBUSTA_BENCHMARK.asset_id,
}

# Sanity range in USc/lb.  Arabica 1960-present: ~35–700.  Robusta: ~20–450.
_PRICE_MIN_USC_LB = 15.0
_PRICE_MAX_USC_LB = 800.0

# Max allowable gap between monthly observations (62 days handles long months + delays)
_MAX_GAP_DAYS = 62

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────────


def fetch(start: date, end: date) -> tuple[list[MarketObservation], SourceRun]:
    """Fetch World Bank monthly coffee prices for the given date range.

    Returns a tuple of (observations, source_run).  Each calendar month in the
    range produces up to two observations: one for Arabica, one for Robusta.
    The source_run is always returned even on failure.
    """
    started_at = datetime.now(UTC)

    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            excel_url = _find_excel_url(client)
            if excel_url is None:
                return [], _failed_run(
                    started_at,
                    "Could not locate Excel download URL on World Bank commodity markets page",
                )
            excel_bytes = _download_excel(client, excel_url)
    except httpx.HTTPStatusError as exc:
        return [], _failed_run(
            started_at, f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        )
    except httpx.RequestError as exc:
        return [], _failed_run(started_at, f"Request error: {exc}")

    observations, parse_errors = _parse_excel(excel_bytes, start, end)

    if observations:
        dates = [o.observed_date for o in observations]
        values = [o.value for o in observations]
        gaps = data_quality.check_no_gaps(dates, max_gap_days=_MAX_GAP_DAYS)
        oob = data_quality.check_value_range(values, low=_PRICE_MIN_USC_LB, high=_PRICE_MAX_USC_LB)
        if gaps:
            logger.warning(
                "%s: gap check found %d gap(s) in price data", _SOURCE_ID, len(gaps)
            )
        if oob:
            logger.warning(
                "%s: %d value(s) outside expected range [%.0f, %.0f] USc/lb",
                _SOURCE_ID, len(oob), _PRICE_MIN_USC_LB, _PRICE_MAX_USC_LB,
            )

    status = RunStatus.PARTIAL if parse_errors else RunStatus.SUCCESS
    error_msg = f"{parse_errors} rows skipped due to parse errors" if parse_errors else None

    return observations, SourceRun(
        source_id=_SOURCE_ID,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=status,
        records_fetched=len(observations),
        records_stored=0,
        error_message=error_msg,
    )


# ── Private helpers ────────────────────────────────────────────────────────────


def _find_excel_url(client: httpx.Client) -> str | None:
    """Scrape the WB commodity markets page for the current monthly Excel URL.

    The URL embeds a document hash that changes with each monthly release, so
    we cannot hardcode it.  The link is present in the static HTML (not JS).
    """
    resp = client.get(_WB_PAGE_URL)
    resp.raise_for_status()
    match = _WB_EXCEL_RE.search(resp.text)
    if match:
        return match.group(0)
    logger.warning("WB commodity page HTML did not contain expected Excel URL pattern")
    return None


def _download_excel(client: httpx.Client, url: str) -> bytes:
    resp = client.get(url)
    resp.raise_for_status()
    return resp.content


def _parse_excel(
    excel_bytes: bytes, start: date, end: date
) -> tuple[list[MarketObservation], int]:
    try:
        df = pd.read_excel(
            io.BytesIO(excel_bytes),
            sheet_name="Monthly Prices",
            header=None,
            engine="openpyxl",
        )
    except Exception as exc:
        logger.error("Failed to parse World Bank Excel: %s", exc)
        return [], 1

    # Locate the first data row by its date-pattern cell rather than assuming a
    # fixed header-row count — WB dropped the machine-code header row in a
    # 2026-07-02 update, shifting data up by one row with no advance notice.
    col0 = df.iloc[:, 0].fillna("").astype(str)
    date_row_positions = [i for i, v in enumerate(col0) if _DATE_RE.match(v.strip())]
    if not date_row_positions:
        logger.error("Could not locate any date-pattern rows in World Bank Excel")
        return [], 1
    data_start = date_row_positions[0]

    # Search every header row above the first data row for our target series,
    # matching either the legacy machine code or the current human-readable name.
    # Use fillna("") before astype(str): mixed-dtype columns leave np.float64(nan)
    # as float objects when astype(str) is called on an object Series.
    series_cols: dict[int, tuple[str, str]] = {}
    matched_asset_ids: set[str] = set()
    for header_row_idx in range(data_start):
        row_vals = df.iloc[header_row_idx].fillna("").astype(str)
        for col_idx, cell in enumerate(row_vals):
            label = cell.strip()
            asset_id = _SERIES_MATCH.get(label)
            if asset_id is None or col_idx in series_cols or asset_id in matched_asset_ids:
                continue
            series_cols[col_idx] = (label, asset_id)
            matched_asset_ids.add(asset_id)

    if not series_cols:
        logger.error("No target series found in World Bank Excel")
        return [], 1

    data_rows = df.iloc[data_start:].reset_index(drop=True)

    observations: list[MarketObservation] = []
    error_count = 0

    for _, row in data_rows.iterrows():
        cell0 = row.iloc[0]
        raw_date = "" if pd.isna(cell0) else str(cell0).strip()
        if not _DATE_RE.match(raw_date):
            continue  # empty trailing rows or non-data rows

        try:
            observed_date = _parse_wb_date(raw_date)
        except (ValueError, IndexError) as exc:
            error_count += 1
            logger.warning("Cannot parse WB date %r: %s", raw_date, exc)
            continue

        if observed_date < start or observed_date > end:
            continue

        for col_idx, (label, asset_id) in series_cols.items():
            raw_val = row.iloc[col_idx]
            if pd.isna(raw_val):
                continue  # data not yet published for this month
            try:
                usd_kg = float(raw_val)
                usc_lb = round(usd_kg * _USD_KG_TO_USC_LB, 4)
            except (TypeError, ValueError) as exc:
                error_count += 1
                logger.warning(
                    "Cannot parse value for %s at %s (%r): %s", label, raw_date, raw_val, exc
                )
                continue

            observations.append(
                MarketObservation(
                    asset_id=asset_id,
                    observed_date=observed_date,
                    value=usc_lb,
                    unit=_UNIT,
                    source=_SOURCE_TAG,
                    raw={"wb_series": label, "date_str": raw_date, "usd_kg": usd_kg},
                )
            )

    return observations, error_count


def _parse_wb_date(s: str) -> date:
    """Convert WB date string to the last day of that month.

    Examples:
        "1960M01" → date(1960, 1, 31)
        "2026M04" → date(2026, 4, 30)
    """
    year = int(s[:4])
    month = int(s[5:])
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def _failed_run(started_at: datetime, error_message: str) -> SourceRun:
    logger.error("World Bank commodity fetch failed: %s", error_message)
    return SourceRun(
        source_id=_SOURCE_ID,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=RunStatus.FAILED,
        records_fetched=0,
        records_stored=0,
        error_message=error_message,
    )
