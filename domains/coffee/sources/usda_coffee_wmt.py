"""USDA Coffee: World Markets and Trade — vintage-dated world stocks-to-use %.

Source:  USDA Foreign Agricultural Service — "Coffee: World Markets and Trade"
         semiannual circular. **This is not the WASDE report** — WASDE (World
         Agricultural Supply and Demand Estimates) covers grains, oilseeds,
         cotton, sugar, and livestock, and does not include coffee at all.
URL:     https://esmis.nal.usda.gov/publication/coffee-world-markets-and-trade
Auth:    None (free, no API key required)
Freq:    Nominally semiannual (June + December); some early-archive years
         (2007-2009) were quarterly. Each issue is a time-stamped PDF circular
         archived back to June 2004.

Why this source exists (fixes a look-ahead bias in usda_psd.py):
  usda_psd.py's bulk CSV always returns the LATEST REVISED vintage of every
  marketing year — a real look-ahead bias for any backtest correlating it
  against historical prices (see notebooks/coffee_backtests/04). This source
  instead parses each historical circular's own "Coffee Summary" table (or,
  pre-2011, "Table 01A ... Consumption and Ending Stocks"), which reports the
  world total for the most recent handful of marketing years AS THEY WERE
  ESTIMATED AT THAT REPORT'S PUBLICATION DATE. We take only the newest
  (rightmost) column of each report's world "Ending Stocks" and "Domestic
  Consumption" Total rows and date the resulting stocks-to-use % to the
  report's own publication date — a genuinely point-in-time series with zero
  look-ahead, no forward-fill/shift approximation required.

Discovery: the ESMIS archive listing page is paginated (`?page=0,1,2,...`, 10
releases per page, most recent first) as an HTML <table>; each row has a
<time datetime="..."> (the report date) and a release-file link with class
"usa-tag" (the PDF href — filename varies across the archive, e.g.
"coffee.pdf" post-2011 vs. the older "tropprod-MM-DD-YYYY.pdf" naming, so we
locate it by CSS class, never by filename). We paginate until an empty page
is returned rather than hardcoding an end date, so future releases are
picked up automatically without a code change.

Parsing: report layout has drifted across 20+ years (pre-2011 issues use one
combined "Table 01A" with Production + Domestic Consumption + Ending Stocks
together; 2011+ issues split it across a paginated "Coffee Summary" /
"Coffee Summary, Continued" series). Both layouts share one structural
anchor: the literal phrase "Thousand 60-Kilogram Bags" appears immediately
under every summary-table page heading, nowhere else in the document
(narrative pages don't carry it). We scan the extracted text page-by-page,
using each such anchor to bound a "table segment," and use the first segment
that contains both a "Domestic Consumption" and an "Ending Stocks" section
header (they are always on the same page). Within that bounded segment we
locate each header and the nearest following "Total <n1> <n2> ...>" line,
taking the last (newest) number. This avoids two known false-positive traps:
a page-1 narrative subsection is also literally titled "Ending Stocks" in
many issues (prose, not a table — it carries no "Thousand 60-Kilogram Bags"
anchor so is never a candidate segment), and the same circular repeats
country-level Ending Stocks in a later table (Table 05) that would otherwise
be picked up as a spurious second candidate.

Reports whose text does not match this structure at all (badly scanned
older issues, or a future format change) are skipped with a logged warning
rather than failing the whole run — this mirrors cot.py's per-item
degradation (one bad year/report does not sink the whole fetch).
"""

import io
import logging
import re
from datetime import UTC, date, datetime
from urllib.parse import urljoin

import httpx
import pdfplumber
from bs4 import BeautifulSoup

from core.models.observation import FeatureObservation
from core.models.source_run import RunStatus, SourceRun
from core.services import data_quality
from domains.coffee.registry.assets import USDA_STU_VINTAGE

_LISTING_BASE = "https://esmis.nal.usda.gov"
_LISTING_URL = f"{_LISTING_BASE}/publication/coffee-world-markets-and-trade"
_MAX_LISTING_PAGES = 20  # safety cap; archive is currently ~5 pages (2004-2025)

_SOURCE_ID = "coffee:usda_coffee_wmt"
_SOURCE_TAG = "usda:coffee_wmt"
_FEATURE_NAME = "stocks_to_use_pct"

_STU_MIN = 0.0
_STU_MAX = 100.0

_TABLE_ANCHOR_RE = re.compile(r"Thousand 60-Kilogram Bags")
_CONSUMPTION_HEADER_RE = re.compile(r"Domestic Consumption\b")
_STOCKS_HEADER_RE = re.compile(r"Ending Stocks\b")
_TOTAL_LINE_RE = re.compile(r"\bTotal\s+((?:[\d,]+\s+){0,9}[\d,]+)")
_MAX_HEADER_TO_TOTAL_CHARS = 3000  # guard against grabbing an unrelated Total line

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────────


def fetch(start: date, end: date) -> tuple[list[FeatureObservation], SourceRun]:
    """Fetch vintage-dated world stocks-to-use % from historical WMT circulars.

    Returns a tuple of (observations, source_run); the source_run is always
    returned even on total failure. One observation per historical report
    published in [start, end], dated to that report's own publication date
    and valued from that report's own newest-column world Ending
    Stocks/Domestic Consumption estimate — see module docstring for why this
    avoids the look-ahead bias in usda_psd.py.

    Individual report download/parse failures are tolerated (skipped with a
    logged warning, PARTIAL run); only a failure to reach the listing page at
    all, or zero parseable reports in range, is FAILED.
    """
    started_at = datetime.now(UTC)
    observations: list[FeatureObservation] = []
    skipped: list[str] = []

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        try:
            reports = _discover_reports(client)
        except httpx.HTTPStatusError as exc:
            return [], _failed_run(
                started_at, f"HTTP {exc.response.status_code} listing WMT archive"
            )
        except httpx.RequestError as exc:
            return [], _failed_run(started_at, f"Request error listing WMT archive: {exc}")

        if not reports:
            return [], _failed_run(started_at, "No reports discovered in WMT archive listing")

        in_range = [(d, url) for d, url in reports if start <= d <= end]

        for report_date, pdf_url in in_range:
            try:
                content = _download(client, pdf_url)
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                msg = f"{report_date}: download failed: {exc}"
                logger.warning("%s: %s", _SOURCE_ID, msg)
                skipped.append(msg)
                continue

            try:
                text = _extract_text(content)
            except Exception as exc:  # noqa: BLE001 — pdfplumber/pdfminer raise varied types
                msg = f"{report_date}: PDF text extraction failed: {exc}"
                logger.warning("%s: %s", _SOURCE_ID, msg)
                skipped.append(msg)
                continue

            stu = _parse_stocks_to_use(text)
            if stu is None:
                msg = f"{report_date}: summary table not found/unparseable"
                logger.warning("%s: %s", _SOURCE_ID, msg)
                skipped.append(msg)
                continue
            if not (_STU_MIN < stu < _STU_MAX):
                msg = f"{report_date}: parsed S/U {stu:.1f}% out of bounds"
                logger.warning("%s: %s", _SOURCE_ID, msg)
                skipped.append(msg)
                continue

            observations.append(
                FeatureObservation(
                    asset_id=USDA_STU_VINTAGE.asset_id,
                    observed_date=report_date,
                    feature_name=_FEATURE_NAME,
                    value=stu,
                    source=_SOURCE_TAG,
                )
            )

    observations.sort(key=lambda o: o.observed_date)

    if observations:
        dates = [o.observed_date for o in observations]
        gaps = data_quality.check_no_gaps(dates, max_gap_days=400)
        if gaps:
            logger.warning(
                "%s: gap check found %d gap(s) in WMT report dates", _SOURCE_ID, len(gaps)
            )

    if not observations:
        return [], _failed_run(
            started_at, "; ".join(skipped) or "No reports in requested range"
        )

    status = RunStatus.PARTIAL if skipped else RunStatus.SUCCESS
    return observations, SourceRun(
        source_id=_SOURCE_ID,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=status,
        records_fetched=len(observations),
        records_stored=0,
        error_message="; ".join(skipped) if skipped else None,
    )


# ── Private helpers ────────────────────────────────────────────────────────────


def _discover_reports(client: httpx.Client) -> list[tuple[date, str]]:
    """Paginate the ESMIS archive listing and return (report_date, pdf_url) pairs.

    Stops once a page adds no new report dates, rather than a hardcoded page
    count, so future releases are picked up without a code change. This is
    deliberately not just "stop on an empty page": past the real archive
    depth, the ESMIS pager does not return an empty page — it wraps back to
    repeating earlier content — so an empty-page-only check would loop
    `_MAX_LISTING_PAGES` times re-fetching the same page. Dict-keyed by date
    also makes the result naturally deduplicated.
    """
    reports: dict[date, str] = {}
    for page in range(_MAX_LISTING_PAGES):
        resp = client.get(_LISTING_URL, params={"page": page})
        resp.raise_for_status()
        page_reports = _parse_listing_page(resp.text)
        new_dates = [d for d, _ in page_reports if d not in reports]
        if not page_reports or not new_dates:
            break
        for report_date, pdf_url in page_reports:
            reports.setdefault(report_date, pdf_url)
    return sorted(reports.items())


def _parse_listing_page(html: str) -> list[tuple[date, str]]:
    """Parse one archive listing page into (report_date, pdf_url) pairs.

    Each release is a <tr> with a <time datetime="..."> and a release-file
    link (class "usa-tag") — located by structure, not by filename, since
    the PDF filename convention has changed across the archive's history.
    """
    soup = BeautifulSoup(html, "html.parser")
    out: list[tuple[date, str]] = []
    for row in soup.find_all("tr"):
        time_tag = row.find("time", attrs={"datetime": True})
        link_tag = row.find("a", class_="usa-tag", href=True)
        if time_tag is None or link_tag is None:
            continue
        try:
            report_date = datetime.fromisoformat(time_tag["datetime"]).date()
        except ValueError:
            continue
        out.append((report_date, urljoin(_LISTING_BASE, link_tag["href"])))
    return out


def _download(client: httpx.Client, url: str) -> bytes:
    resp = client.get(url)
    resp.raise_for_status()
    return resp.content


def _extract_text(content: bytes) -> str:
    """Extract and concatenate page text from a WMT circular PDF."""
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _parse_stocks_to_use(text: str) -> float | None:
    """Parse world stocks-to-use % from one circular's extracted text.

    Returns None if no table segment with both a Domestic Consumption and an
    Ending Stocks Total row can be found — the caller skips that report.
    """
    segment = _find_summary_segment(text)
    if segment is None:
        return None

    consumption = _section_total(segment, _CONSUMPTION_HEADER_RE)
    stocks = _section_total(segment, _STOCKS_HEADER_RE)
    if consumption is None or stocks is None or consumption == 0:
        return None

    return stocks / consumption * 100


def _find_summary_segment(text: str) -> str | None:
    """Return the text of the summary-table page that has both target sections.

    Scans "Thousand 60-Kilogram Bags"-anchored page segments (there is one
    per summary-table page) and returns the first that contains both a
    "Domestic Consumption" and an "Ending Stocks" section header. Narrative
    pages (e.g. a page-1 "Ending Stocks" prose subsection) carry no such
    anchor and are never considered.
    """
    anchors = [m.start() for m in _TABLE_ANCHOR_RE.finditer(text)]
    for i, start in enumerate(anchors):
        end = anchors[i + 1] if i + 1 < len(anchors) else len(text)
        segment = text[start:end]
        if _CONSUMPTION_HEADER_RE.search(segment) and _STOCKS_HEADER_RE.search(segment):
            return segment
    return None


def _section_total(segment: str, header_re: re.Pattern[str]) -> float | None:
    """Find `header_re`'s section within `segment` and return its Total row's
    last (newest) number, or None if the header or a nearby Total row is
    missing."""
    header_m = header_re.search(segment)
    if not header_m:
        return None
    total_m = _TOTAL_LINE_RE.search(segment, header_m.end())
    if not total_m:
        return None
    if total_m.start() - header_m.end() > _MAX_HEADER_TO_TOTAL_CHARS:
        return None
    numbers = total_m.group(1).split()
    if not numbers:
        return None
    try:
        return float(numbers[-1].replace(",", ""))
    except ValueError:
        return None


def _failed_run(started_at: datetime, error_message: str) -> SourceRun:
    logger.error("USDA Coffee WMT fetch failed: %s", error_message)
    return SourceRun(
        source_id=_SOURCE_ID,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=RunStatus.FAILED,
        records_fetched=0,
        records_stored=0,
        error_message=error_message,
    )
