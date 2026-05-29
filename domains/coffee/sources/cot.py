"""CFTC Commitments of Traders — speculative positioning on ICE Coffee KC.

Source:  CFTC Disaggregated Commitments of Traders (futures-only)
URL:     https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip
Auth:    None (free, no API key required)
Freq:    Weekly — positions are as of each Tuesday's close, published the
         following Friday. Annual ZIP files, one CSV per year.

We use the DISAGGREGATED report (not the legacy report) because it breaks out
"Managed Money" — the speculative trader category we care about. The signal is
the net managed-money position (long - short), used contrarian: when specs are
crowded long (high COT index) prices often top; when crowded short (low index)
prices often bottom.

Format (comma-delimited CSV with header row inside the ZIP):
  - Market_and_Exchange_Names : e.g. "COFFEE C - ICE FUTURES U.S."
  - Report_Date_as_YYYY-MM-DD : the Tuesday the positions are measured
  - M_Money_Positions_Long_All  : managed-money long contracts
  - M_Money_Positions_Short_All : managed-money short contracts

Market filter: rows where Market_and_Exchange_Names contains 'COFFEE C - ICE'.

Usage in composite:
    fetch() returns the raw weekly net position. Convert to a 0-100 COT index
    over a trailing window with `_cot_index()`, then map to a contrarian
    score with `cot_contrarian_signal()`. Align weekly Tuesday positions to
    month-end downstream for the monthly backtest — the source stays faithful
    to the raw weekly cadence.
"""

import io
import logging
import zipfile
from datetime import UTC, date, datetime

import httpx
import pandas as pd

from core.models.observation import FeatureObservation
from core.models.source_run import RunStatus, SourceRun
from core.services import data_quality
from domains.coffee.registry.assets import COT_KC

_BASE_URL = "https://www.cftc.gov/files/dea/history"
_MARKET_SUBSTRING = "COFFEE C - ICE"

_SOURCE_ID = "coffee:cftc_cot"
_SOURCE_TAG = "cftc:disaggregated"
_FEATURE_NAME = "managed_money_net"

# Column names in the disaggregated report. Located by name (never by position)
# because CFTC occasionally reorders columns between report vintages.
_MARKET_COL = "Market_and_Exchange_Names"
# The report-date column is renamed across vintages: pre-2013 it is
# "Report_Date_as_MM_DD_YYYY", 2013+ it is "Report_Date_as_YYYY-MM-DD". Both
# columns actually carry ISO YYYY-MM-DD *values* despite the older header, so we
# match the common "Report_Date_as_" prefix and let pd.to_datetime parse it.
_DATE_COL_PREFIX = "Report_Date_as_"
_LONG_COL = "M_Money_Positions_Long_All"
_SHORT_COL = "M_Money_Positions_Short_All"

# Sanity bounds for a net managed-money position in KC (contracts). ICE Coffee C
# open interest runs ~150-250k contracts; net spec rarely exceeds ±80k.
_NET_MIN = -150_000.0
_NET_MAX = 150_000.0

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────────


def fetch(start: date, end: date) -> tuple[list[FeatureObservation], SourceRun]:
    """Download CFTC disaggregated COT reports spanning [start, end].

    One annual ZIP is fetched per calendar year in the range. Returns a tuple
    of (observations, source_run); the source_run is always returned even on
    total failure. Each observation is the net managed-money position
    (long - short) for one weekly (Tuesday) report date in KC futures.

    Year-level download failures are tolerated: if at least one year succeeds
    the run is PARTIAL; only a complete failure (no observations) is FAILED.
    """
    started_at = datetime.now(UTC)

    observations: list[FeatureObservation] = []
    parse_errors = 0
    download_errors: list[str] = []

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for year in range(start.year, end.year + 1):
            try:
                text = _download_year(client, year)
            except httpx.HTTPStatusError as exc:
                download_errors.append(
                    f"{year}: HTTP {exc.response.status_code}"
                )
                continue
            except httpx.RequestError as exc:
                download_errors.append(f"{year}: request error: {exc}")
                continue
            except (zipfile.BadZipFile, KeyError, StopIteration) as exc:
                download_errors.append(f"{year}: bad archive: {exc}")
                continue

            year_obs, year_errors = _parse_report(text, start, end)
            observations.extend(year_obs)
            parse_errors += year_errors

    observations.sort(key=lambda o: o.observed_date)

    if observations:
        dates = [o.observed_date for o in observations]
        values = [o.value for o in observations]
        # Weekly cadence; flag any gap longer than ~2 reporting weeks
        gaps = data_quality.check_no_gaps(dates, max_gap_days=14)
        oob = data_quality.check_value_range(values, low=_NET_MIN, high=_NET_MAX)
        if gaps:
            logger.warning(
                "%s: gap check found %d gap(s) in COT data", _SOURCE_ID, len(gaps)
            )
        if oob:
            logger.warning(
                "%s: %d net-position value(s) outside expected range [%.0f, %.0f]",
                _SOURCE_ID, len(oob), _NET_MIN, _NET_MAX,
            )

    # No data at all + something went wrong → FAILED
    if not observations and download_errors:
        return [], _failed_run(started_at, "; ".join(download_errors))

    if download_errors or parse_errors:
        bits = []
        if download_errors:
            bits.append("; ".join(download_errors))
        if parse_errors:
            bits.append(f"{parse_errors} rows skipped due to parse errors")
        status = RunStatus.PARTIAL
        error_msg = " | ".join(bits)
    else:
        status = RunStatus.SUCCESS
        error_msg = None

    return observations, SourceRun(
        source_id=_SOURCE_ID,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=status,
        records_fetched=len(observations),
        records_stored=0,
        error_message=error_msg,
    )


def cot_contrarian_signal(cot_index: float) -> float:
    """Return contrarian signal: +1 if index < 25 (buy), -1 if > 75 (caution), else 0.

    Managed money crowded short (low index) is a contrarian buy; crowded long
    (high index) is a caution. The index is the 0-100 percentile of the net
    position over its trailing window (see `_cot_index`).
    """
    if cot_index < 25:
        return 1.0
    if cot_index > 75:
        return -1.0
    return 0.0


# ── Private helpers ────────────────────────────────────────────────────────────


def _download_year(client: httpx.Client, year: int) -> str:
    """Download one annual disaggregated ZIP and return the contained CSV text.

    Raises httpx errors on network/HTTP failure, and zipfile.BadZipFile /
    StopIteration if the archive is missing or has no .txt member.
    """
    url = f"{_BASE_URL}/fut_disagg_txt_{year}.zip"
    resp = client.get(url)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        # The annual file is named f_year.txt, but locate it dynamically
        txt_name = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
        return zf.read(txt_name).decode("utf-8", errors="replace")


def _parse_report(
    text: str, start: date, end: date
) -> tuple[list[FeatureObservation], int]:
    """Parse one disaggregated CSV into net managed-money FeatureObservations.

    Returns (observations, error_count). Rows for other markets, out-of-range
    dates, and unparseable position values are skipped.
    """
    try:
        # low_memory=False: the file has 100+ columns with mixed types in
        # trader-count fields we don't use; chunked inference otherwise warns.
        df = pd.read_csv(io.StringIO(text), low_memory=False)
    except (pd.errors.ParserError, ValueError) as exc:
        logger.warning("%s: could not parse CSV: %s", _SOURCE_ID, exc)
        return [], 1

    date_col = _find_date_col(df.columns)
    required = {_MARKET_COL, _LONG_COL, _SHORT_COL}
    if date_col is None or not required.issubset(df.columns):
        missing = required - set(df.columns)
        logger.warning(
            "%s: missing expected columns %s (date_col=%r)",
            _SOURCE_ID, missing or "{}", date_col,
        )
        return [], 1

    market = df[_MARKET_COL].fillna("").astype(str)
    kc = df[market.str.contains(_MARKET_SUBSTRING, case=False, regex=False)]

    observations: list[FeatureObservation] = []
    error_count = 0

    for _, row in kc.iterrows():
        try:
            observed_date = pd.to_datetime(row[date_col]).date()
            long_pos = float(row[_LONG_COL])
            short_pos = float(row[_SHORT_COL])
        except (ValueError, TypeError) as exc:
            error_count += 1
            logger.warning("%s: cannot parse row %r: %s", _SOURCE_ID, row.get(date_col), exc)
            continue

        if observed_date < start or observed_date > end:
            continue

        observations.append(
            FeatureObservation(
                asset_id=COT_KC.asset_id,
                observed_date=observed_date,
                feature_name=_FEATURE_NAME,
                value=long_pos - short_pos,
                source=_SOURCE_TAG,
            )
        )

    return observations, error_count


def _find_date_col(columns: pd.Index) -> str | None:
    """Find the report-date column by prefix (handles vintage naming differences)."""
    for col in columns:
        if str(col).startswith(_DATE_COL_PREFIX):
            return str(col)
    return None


def _cot_index(series: pd.Series, window: int = 156) -> pd.Series:
    """Compute rolling COT index: 100 × (val - min) / (max - min) over `window` weeks.

    Default window is 156 weeks (≈3 years). Where the trailing window is flat
    (max == min), the index is undefined and set to 50.0 (neutral).
    """
    roll_min = series.rolling(window, min_periods=1).min()
    roll_max = series.rolling(window, min_periods=1).max()
    rng = roll_max - roll_min
    idx = 100.0 * (series - roll_min) / rng
    return idx.where(rng != 0, 50.0)


def _failed_run(started_at: datetime, error_message: str) -> SourceRun:
    logger.error("CFTC COT fetch failed: %s", error_message)
    return SourceRun(
        source_id=_SOURCE_ID,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=RunStatus.FAILED,
        records_fetched=0,
        records_stored=0,
        error_message=error_message,
    )
