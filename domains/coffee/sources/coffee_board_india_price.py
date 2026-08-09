"""India daily coffee price — Coffee Board of India's Daily Market Report archive.

Source:  Coffee Board of India, Bengaluru
Archive: https://coffeeboard.gov.in/Market_Info_Archives.aspx — a stateful ASP.NET
         WebForms flow, not a simple URL: Market_Info.aspx → (postback: "Archives")
         → Market_Info_Archives.aspx (year x month grid, 2012-present) →
         (postback: a specific month) → Archives_Month.aspx (day list for that
         month) → (postback: a specific day) → that day's PDF report, served
         inline as the POST response body (no separate download URL).
Auth:    None (free, no API key) — but every step requires carrying forward the
         previous response's __VIEWSTATE/__EVENTVALIDATION hidden fields, since
         ASP.NET WebForms postbacks are stateful. Reverse-engineered by replaying
         the real browser flow with requests.Session() and comparing against a
         live Claude Browser session click-through (see
         docs/india_origin_signal_plan_v2_full_build.md).

Each daily PDF contains, among other things, a "Raw Coffee Price (Karnataka)"
table — the genuine India-origin domestic price this source exists to capture:

    Raw Coffee Price (Karnataka) as on 29.05.2026 in ₹/50 Kg
    Ar.Pmt Ar.Chy Rob.Pmt Rob.Chy
    22300 - 23000 12750 - 14250 17500 - 18300 9300 - 10100

Four series (Arabica Parchment/Cherry, Robusta Parchment/Cherry), each a daily
low-high range in ₹/50kg — `value` is the midpoint, `raw` carries the full range.
The table's own "as on" date can differ from the report's nominal date (a few
days' lag is normal, e.g. weekend/holiday carry-forward) — each observation is
dated to ITS OWN "as on" date, not the report's nominal date, mirroring
usda_coffee_wmt.py's vintage-dating discipline.

Deliberately NOT parsed in this pass (documented scope, not an oversight): the
same PDF also has ICTA grade-level auction prices (many blank cells per grade per
day — noisier to parse reliably), the day's USD/INR rate (already covered more
simply by yfinance, see notebook 09), and cumulative export volumes (a genuinely
different, YTD-cumulative signal that would need differencing — a separate future
source, not a field on this one).

**Politeness:** this is a small government server, not a CDN. `fetch()` paces
day-level PDF requests with `_REQUEST_DELAY_S` between them — a full historical
backfill (archive goes back to 2012, ~230 trading days/year) is thousands of
requests and will legitimately take a long time. That's intentional, not a bug.
"""

import io
import logging
import re
import time
from datetime import UTC, date, datetime

import httpx
import pdfplumber
from bs4 import BeautifulSoup

from core.models.observation import MarketObservation
from core.models.source_run import RunStatus, SourceRun
from domains.coffee.registry.assets import INDIA_ARABICA, INDIA_ROBUSTA

_BASE_URL = "https://coffeeboard.gov.in/"
_MARKET_INFO_URL = _BASE_URL + "Market_Info.aspx"
_ARCHIVES_URL = _BASE_URL + "Market_Info_Archives.aspx"
_ARCHIVES_MONTH_URL = _BASE_URL + "Archives_Month.aspx"

_SOURCE_ID = "coffee:coffee_board_india_price"
_SOURCE_TAG = "coffee_board:daily_raw_price"
_UNIT = "inr_per_50kg"

# Politeness pacing between per-day PDF requests — see module docstring. Month-grid
# navigation (once per month, not once per day) uses the same delay for simplicity.
_REQUEST_DELAY_S = 2.0

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}

_MONTH_ROW_ORDER = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

# Series label (as printed in the PDF) -> (asset, grade metadata tag)
_SERIES_MAP = [
    ("Ar.Pmt", INDIA_ARABICA.asset_id, "arabica_parchment"),
    ("Ar.Chy", INDIA_ARABICA.asset_id, "arabica_cherry"),
    ("Rob.Pmt", INDIA_ROBUSTA.asset_id, "robusta_parchment"),
    ("Rob.Chy", INDIA_ROBUSTA.asset_id, "robusta_cherry"),
]

_RAW_PRICE_RE = re.compile(
    r"Raw Coffee Price \(Karnataka\) as on (\d{2})\.(\d{2})\.(\d{4})[^\n]*\n"
    r"Ar\.Pmt Ar\.Chy Rob\.Pmt Rob\.Chy\n"
    r"([\d,]+)\s*-\s*([\d,]+)\s+([\d,]+)\s*-\s*([\d,]+)\s+"
    r"([\d,]+)\s*-\s*([\d,]+)\s+([\d,]+)\s*-\s*([\d,]+)"
)

# Sanity bounds in ₹/50kg (observed live range ~9,000-23,000 as of 2026).
_PRICE_MIN = 1000.0
_PRICE_MAX = 60000.0

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────────


def fetch(start: date, end: date) -> tuple[list[MarketObservation], SourceRun]:
    """Fetch India daily "Raw Coffee Price (Karnataka)" for every archived report
    day in [start, end].

    Returns (observations, source_run); source_run is always returned even on
    total failure. A single day's download/parse failure degrades the run to
    PARTIAL rather than failing the whole fetch — same pattern as the other
    Coffee Board sources in this repo.

    This walks a stateful multi-step ASP.NET flow (see module docstring) and
    paces requests deliberately — a multi-year range will take a long time by
    design. Call with a narrower range for incremental/production use once an
    initial backfill exists.
    """
    started_at = datetime.now(UTC)
    observations: list[MarketObservation] = []
    failures = 0

    try:
        with httpx.Client(timeout=30.0, headers=_HEADERS, follow_redirects=True) as client:
            year_month_grid = _discover_year_month_grid(client)
    except httpx.HTTPError as exc:
        return [], _failed_run(started_at, f"Could not load the archive grid: {exc}")

    target_years = {y for y in year_month_grid if start.year <= y <= end.year}
    if not target_years:
        return [], _failed_run(
            started_at, f"No archived years overlap [{start}, {end}] in the grid"
        )

    with httpx.Client(timeout=30.0, headers=_HEADERS, follow_redirects=True) as client:
        for year in sorted(target_years):
            for month_idx in range(12):
                month_start = date(year, month_idx + 1, 1)
                if month_start > end or _month_end(month_start) < start:
                    continue
                control = year_month_grid.get(year, {}).get(month_idx)
                if control is None:
                    continue

                time.sleep(_REQUEST_DELAY_S)
                try:
                    day_controls, month_fields = _list_days(client, control)
                except httpx.HTTPError as exc:
                    logger.warning("Failed to list days for %s-%02d: %s", year, month_idx + 1, exc)
                    failures += 1
                    continue

                for day_label, day_control in day_controls:
                    time.sleep(_REQUEST_DELAY_S)
                    try:
                        pdf_bytes = _fetch_day_pdf(client, day_control, month_fields)
                        day_obs = _parse_raw_price_table(pdf_bytes)
                    except Exception as exc:  # noqa: BLE001 - one bad day shouldn't fail the run
                        logger.warning("Failed to fetch/parse %s: %s", day_label, exc)
                        failures += 1
                        continue

                    for observed_date, asset_id, grade, low, high in day_obs:
                        if not (start <= observed_date <= end):
                            continue
                        observations.append(
                            MarketObservation(
                                asset_id=asset_id,
                                observed_date=observed_date,
                                value=round((low + high) / 2, 2),
                                unit=_UNIT,
                                source=_SOURCE_TAG,
                                raw={"grade": grade, "range_low": low, "range_high": high},
                            )
                        )

    observations.sort(key=lambda o: o.observed_date)

    status = RunStatus.PARTIAL if failures else RunStatus.SUCCESS
    error_msg = f"{failures} day(s) failed to fetch/parse" if failures else None

    return observations, SourceRun(
        source_id=_SOURCE_ID,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=status,
        records_fetched=len(observations),
        records_stored=0,
        error_message=error_msg,
    )


# ── Private helpers — ASP.NET WebForms flow ─────────────────────────────────────


_HIDDEN_FIELD_RE = re.compile(
    r'<input[^>]+type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"'
)


def _hidden_fields(html: str) -> dict[str, str]:
    """Extract ASP.NET postback state (__VIEWSTATE etc.) from a page's hidden inputs."""
    return {m.group(1): m.group(2) for m in _HIDDEN_FIELD_RE.finditer(html)}


def _postback_target(href: str) -> str | None:
    """Extract the __EVENTTARGET control name from a `javascript:__doPostBack(...)` href."""
    match = re.search(r"__doPostBack\('([^']+)'", href)
    return match.group(1) if match else None


def _discover_year_month_grid(client: httpx.Client) -> dict[int, dict[int, str]]:
    """Navigate to the year x month archive grid and return
    {year: {month_index_0_11: postback_control_name}}.

    Control IDs are NOT a simple function of the year (e.g. 2020's column uses
    control "LinkButton64", not "LinkButton2020") — real, observed drift, not a
    guess — so this parses the live grid's row/column structure every time rather
    than constructing control names algorithmically.
    """
    r1 = client.get(_MARKET_INFO_URL)
    r1.raise_for_status()
    fields1 = _hidden_fields(r1.text)

    r2 = client.post(
        _MARKET_INFO_URL,
        data={**fields1, "__EVENTTARGET": "lbnarchives", "__EVENTARGUMENT": ""},
    )
    r2.raise_for_status()

    soup = BeautifulSoup(r2.text, "html.parser")
    table = soup.find(id="GridView1")
    if table is None:
        raise httpx.HTTPError("Archive grid (GridView1) not found on Market_Info_Archives.aspx")

    rows = table.find_all("tr")
    years = [th.get_text(strip=True) for th in rows[0].find_all("th")]

    grid: dict[int, dict[int, str]] = {}
    for month_idx, row in enumerate(rows[1 : 1 + 12]):
        cells = row.find_all("td")
        for year_text, cell in zip(years, cells, strict=False):
            a = cell.find("a")
            if not a:
                continue
            control = _postback_target(a.get("href", ""))
            if control:
                grid.setdefault(int(year_text), {})[month_idx] = control

    return grid


def _list_days(
    client: httpx.Client, month_control: str
) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """POST to select a specific year/month; return ([(day_label, day_control), ...],
    hidden_fields_for_the_resulting_page).

    Needs a fresh __VIEWSTATE each time (re-fetches Market_Info.aspx -> archives
    -> this month), rather than reusing state across months, since ASP.NET
    postback state is per-response, not safely reusable across separate
    navigations.
    """
    r1 = client.get(_MARKET_INFO_URL)
    r1.raise_for_status()
    fields1 = _hidden_fields(r1.text)

    r2 = client.post(
        _MARKET_INFO_URL,
        data={**fields1, "__EVENTTARGET": "lbnarchives", "__EVENTARGUMENT": ""},
    )
    r2.raise_for_status()
    fields2 = _hidden_fields(r2.text)

    r3 = client.post(
        _ARCHIVES_URL,
        data={**fields2, "__EVENTTARGET": month_control, "__EVENTARGUMENT": ""},
    )
    r3.raise_for_status()
    fields3 = _hidden_fields(r3.text)

    soup = BeautifulSoup(r3.text, "html.parser")
    day_list = soup.find(id="DataList1")
    if day_list is None:
        return [], fields3

    days: list[tuple[str, str]] = []
    seen_controls: set[str] = set()
    for a in day_list.find_all("a"):
        control = _postback_target(a.get("href", ""))
        if control and control not in seen_controls:
            seen_controls.add(control)
            days.append((a.get_text(strip=True), control))

    return days, fields3


def _fetch_day_pdf(
    client: httpx.Client, day_control: str, month_page_fields: dict[str, str]
) -> bytes:
    """POST to select a specific day; the response body IS that day's PDF."""
    resp = client.post(
        _ARCHIVES_MONTH_URL,
        data={**month_page_fields, "__EVENTTARGET": day_control, "__EVENTARGUMENT": ""},
    )
    resp.raise_for_status()
    if resp.content[:4] != b"%PDF":
        content_type = resp.headers.get("Content-Type")
        raise ValueError(f"Expected a PDF response, got content-type={content_type}")
    return resp.content


# ── Private helpers — PDF parsing ───────────────────────────────────────────────


def _parse_raw_price_table(pdf_bytes: bytes) -> list[tuple[date, str, str, float, float]]:
    """Parse the "Raw Coffee Price (Karnataka)" table out of one daily report.

    Returns [(observed_date, asset_id, grade, range_low, range_high), ...] — up to
    4 entries (Ar.Pmt, Ar.Chy, Rob.Pmt, Rob.Chy). Returns [] if the table isn't
    present/parseable in this report (degrades that day to a skip, not a crash).
    """
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    match = _RAW_PRICE_RE.search(text)
    if not match:
        return []

    dd, mm, yyyy = match.group(1), match.group(2), match.group(3)
    observed_date = date(int(yyyy), int(mm), int(dd))

    numbers = [float(g.replace(",", "")) for g in match.groups()[3:]]
    pairs = list(zip(numbers[0::2], numbers[1::2], strict=True))  # [(low, high), ...] x4

    out: list[tuple[date, str, str, float, float]] = []
    for (label, asset_id, grade), (low, high) in zip(_SERIES_MAP, pairs, strict=True):
        if not (_PRICE_MIN <= low <= _PRICE_MAX and _PRICE_MIN <= high <= _PRICE_MAX):
            logger.warning("%s %s out of sanity range: %s-%s", observed_date, label, low, high)
            continue
        out.append((observed_date, asset_id, grade, low, high))

    return out


def _month_end(d: date) -> date:
    import calendar

    last = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last)


def _failed_run(started_at: datetime, error_message: str) -> SourceRun:
    logger.error("Coffee Board India price fetch failed: %s", error_message)
    return SourceRun(
        source_id=_SOURCE_ID,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=RunStatus.FAILED,
        records_fetched=0,
        records_stored=0,
        error_message=error_message,
    )
