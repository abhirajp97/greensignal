"""India coffee production estimates — Coffee Board of India's semiannual
"Database on Coffee" PDF circular.

Source:  Coffee Board of India, Market Research & Intelligence Unit
Archive: https://coffeeboard.gov.in/database-coffee.html — a single static HTML page
         listing ~60 PDFs back to Jan 2009, roughly semiannual (Jan/July) from 2018
         onward, more frequent (quarterly-ish, split "Part I"/"Part II") 2009-2017.
         No pagination, unlike usda_coffee_wmt.py's ESMIS archive — one GET lists
         everything.
Auth:    None (free, no API key).

Mirrors the India-specific supply signal the original plan called for and this
build initially dropped without good reason — see
docs/india_origin_signal_plan_v2_full_build.md. Analogous in spirit to
usda_coffee_wmt.py: each report is genuinely time-stamped and carries that
report's own newest marketing-year column, so `fetch()` is vintage-aware (no
look-ahead) rather than USDA PSD's always-latest-revised approach.

Table anchor: every edition (2013-2024 spot-checked) carries a table titled
"Production of Coffee in Major States/Districts (Zones) of India" — the leading
section number drifts (1.6 in 2013/2016, 1.7 in 2022, 1.8 in 2024, same class of
drift usda_coffee_wmt.py already handles) so the parser anchors on the stable
phrase, not the number. pdfplumber's extract_tables() parses this cleanly into
rows (verified directly, not assumed) — no text-position heuristics needed, unlike
usda_coffee_wmt.py's PDF (which has no extractable table grid).

Two data points per edition:
  - District-level Arabica/Robusta/Total (Chikkamagaluru, Kodagu, Hassan, Wayanad,
    Travancore, Nilliampathy, plus Tamil Nadu districts) — the newest ("leftmost")
    marketing-year column in that edition's table.
  - "Grand Total (India)" row — the national aggregate.
Both come from the same table/fetch, so no extra request cost.

Report date: each PDF's cover page states its own publication month/year (e.g.
"January 2013"). Some editions render this with duplicated characters from a bold
font extraction quirk (e.g. "JJuunnee // JJuullyy 2016") — collapse repeated runs
before matching month names rather than requiring an exact string.
"""

import io
import logging
import re
import time
from datetime import UTC, date, datetime

import httpx
import pdfplumber
from bs4 import BeautifulSoup

from core.models.observation import FeatureObservation
from core.models.source_run import RunStatus, SourceRun
from domains.coffee.registry.assets import INDIA_PRODUCTION

_ARCHIVE_URL = "https://coffeeboard.gov.in/database-coffee.html"
_BASE_URL = "https://coffeeboard.gov.in/"

_SOURCE_ID = "coffee:coffee_board_india_supply"
_SOURCE_TAG = "coffee_board:database_pdf"

# FeatureObservation has no metadata/extra field (see core/models/observation.py) —
# region and species are encoded into feature_name itself rather than adding new
# per-district registry assets for what's fundamentally one signal.
_FEATURE_NAME_TEMPLATE = "production_mt:{region_slug}:{species}"

_SECTION_ANCHOR = "Production of Coffee in Major States/Districts"

_MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]

# District row labels drift in spelling across editions/documents — e.g.
# "Chikkamagaluru" (2024) vs "Chikmagalur" (2013), confirmed by inspecting the
# real backfilled data (both slugs appear, splitting one district's series in
# two). Map known variants to one canonical slug so callers get a single
# continuous series per region. Deliberately does NOT merge "andhra_pradesh"
# with "andhra_pradesh_orissa" — older editions genuinely combined Andhra
# Pradesh and Orissa into one row, a structural difference, not a spelling one;
# merging those would silently conflate a two-state figure with a one-state one.
_REGION_ALIASES: dict[str, str] = {
    "chikmagalur": "chikkamagaluru",
    "nilliampathy": "nelliampathies",
    "anamalais_coimbatore": "anaamalais_coimbatore",
    "shevroys_salem": "shevaroy_salem",
    "wyanad": "wayanad",
    "orissa": "odisha",  # official state rename in 2011 — same entity, continuous series
}

_NATIONAL_ROW = "grand total"

# Politeness delay between PDF downloads — ~60 static files on a small government
# server; no session state involved (unlike coffee_board_india_price.py's ASP.NET
# postback chain), but still worth pacing rather than firing all requests at once.
_REQUEST_DELAY_S = 0.3

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────────


def fetch(start: date, end: date) -> tuple[list[FeatureObservation], SourceRun]:
    """Fetch India production estimates for every archived report in [start, end].

    Returns (observations, source_run); source_run is always returned even on
    total failure. One observation per (report, district-or-national, species)
    combination, dated to that report's own publication month — vintage-aware,
    mirrors usda_coffee_wmt.py. A single report's download/parse failure degrades
    the run to PARTIAL rather than failing the whole fetch.
    """
    started_at = datetime.now(UTC)

    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            pdf_urls = _list_pdf_urls(client)
            if not pdf_urls:
                return [], _failed_run(started_at, "No PDFs found in database-coffee.html listing")

            observations: list[FeatureObservation] = []
            failures = 0
            for i, url in enumerate(pdf_urls):
                if i > 0:
                    time.sleep(_REQUEST_DELAY_S)
                try:
                    pdf_bytes = client.get(url).raise_for_status().content
                except httpx.HTTPError as exc:
                    logger.warning("Failed to download %s: %s", url, exc)
                    failures += 1
                    continue

                try:
                    report_date, rows = _parse_report(pdf_bytes)
                except Exception as exc:  # noqa: BLE001 - one bad report shouldn't fail the run
                    logger.warning("Failed to parse %s: %s", url, exc)
                    failures += 1
                    continue

                if report_date is None or not (start <= report_date <= end):
                    continue

                for region, species, value_mt in rows:
                    observations.append(
                        FeatureObservation(
                            asset_id=INDIA_PRODUCTION.asset_id,
                            observed_date=report_date,
                            feature_name=_FEATURE_NAME_TEMPLATE.format(
                                region_slug=_region_slug(region), species=species
                            ),
                            value=value_mt,
                            source=_SOURCE_TAG,
                        )
                    )
    except httpx.HTTPError as exc:
        return [], _failed_run(started_at, f"Request error: {exc}")

    observations.sort(key=lambda o: (o.observed_date, o.feature_name))

    status = RunStatus.PARTIAL if failures else RunStatus.SUCCESS
    error_msg = f"{failures} report(s) failed to download/parse" if failures else None

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


def _list_pdf_urls(client: httpx.Client) -> list[str]:
    """List every Database PDF on the (unpaginated, static) archive page.

    One entry (the Oct 2013 "Part II" edition, as of this writing) is genuinely
    mislinked on the government site itself — folder "Pasupathi/" instead of
    "Database/" — a real typo, not a bug here. It 404s and degrades that single
    report to a download failure (PARTIAL run), which is the right behavior for
    a broken link rather than a parse error worth special-casing.
    """
    resp = client.get(_ARCHIVE_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    hrefs = {a["href"] for a in soup.find_all("a", href=True) if a["href"].lower().endswith(".pdf")}
    return sorted(_BASE_URL + href for href in hrefs)


def _parse_report(pdf_bytes: bytes) -> tuple[date | None, list[tuple[str, str, float]]]:
    """Parse one Database PDF: return (report_date, [(region, species, value_mt), ...]).

    region == "India" for the national Grand Total row; otherwise a district name.
    species is "arabica", "robusta", or "total".
    """
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        report_date = _extract_report_date(pdf.pages[0].extract_text() or "")

        table = None
        for page in pdf.pages:
            text = page.extract_text() or ""
            first_line = text.split("\n")[0] if text else ""
            if _SECTION_ANCHOR in first_line:
                tables = page.extract_tables()
                if tables:
                    table = tables[0]
                break

        if table is None:
            return report_date, []

        return report_date, _parse_production_table(table)


def _parse_production_table(table: list[list[str | None]]) -> list[tuple[str, str, float]]:
    """Extract (region, species, value_mt) from the newest (leftmost) year column.

    Table shape (verified against 2013/2016/2022/2024 editions):
      row 0: [Sl.No, State/District, <year1>, None, None, <year2>, None, None]
      row 1: [None, None, Arabica, Robusta, Total, Arabica, Robusta, Total]
      data rows: [sl_no, region_label, arabica1, robusta1, total1, arabica2, ...]
    Columns 2/3/4 are the newest year (arabica/robusta/total) — that's what a
    point-in-time vintage observation for this report should use.
    """
    rows: list[tuple[str, str, float]] = []
    for row in table[2:]:
        if len(row) < 5:
            continue
        label = (row[1] or "").strip()
        label_norm = re.sub(r"[^a-z]", "", label.lower())
        if not label_norm:
            continue

        is_national = _NATIONAL_ROW.replace(" ", "") in label_norm
        # Skip section headers ("Karnataka", "Kerala", ...) and sub/grand-total
        # rows other than the national Grand Total — those are redundant sums
        # of the district rows we already capture.
        if label_norm in {"subtotal", "totalfortraditionalareas"} or (
            not is_national and row[2] in (None, "", "0") and row[3] in (None, "", "0")
        ):
            continue
        if label_norm in {"karnataka", "kerala", "tamilnadu", "nontraditionalareas"}:
            continue

        # Footnote markers on district names vary by edition ("Kodagu #" in some,
        # "Kodagu *" in others) — strip either, not just one.
        region = "India" if is_national else re.sub(r"\s*[#*]\s*$", "", label).strip()

        for species, col in [("arabica", 2), ("robusta", 3), ("total", 4)]:
            raw = row[col] if col < len(row) else None
            value = _parse_number(raw)
            if value is not None:
                rows.append((region, species, value))

    return rows


def _region_slug(region: str) -> str:
    """Normalize a region label into a feature_name-safe slug (lowercase, underscored),
    then collapse known spelling variants (see _REGION_ALIASES) to one canonical slug.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", region.lower()).strip("_")
    return _REGION_ALIASES.get(slug, slug)


def _parse_number(raw: str | None) -> float | None:
    if raw is None:
        return None
    cleaned = raw.strip().replace(",", "")
    if not cleaned or cleaned in {"-", "--", "---"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_report_date(cover_text: str) -> date | None:
    """Extract (year, month) from the cover page and return its month-end date.

    Some editions duplicate characters from a bold-font PDF extraction quirk
    (e.g. "JJuunnee // JJuullyy 2016") — collapse repeated character runs before
    matching month names. If two months are mentioned (e.g. "June/July"), take
    the later one as the report's effective as-of month.
    """
    year_match = re.search(r"\b(19|20)\d{2}\b", cover_text)
    if not year_match:
        return None
    year = int(year_match.group(0))

    normalized = re.sub(r"(.)\1+", r"\1", cover_text.lower())
    matched_months = [i for i, name in enumerate(_MONTH_NAMES, start=1) if name in normalized]
    if not matched_months:
        return None
    month = max(matched_months)

    import calendar

    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def _failed_run(started_at: datetime, error_message: str) -> SourceRun:
    logger.error("Coffee Board India supply fetch failed: %s", error_message)
    return SourceRun(
        source_id=_SOURCE_ID,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=RunStatus.FAILED,
        records_fetched=0,
        records_stored=0,
        error_message=error_message,
    )
