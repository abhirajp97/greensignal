"""Tests for coffee_board_india_supply.py — India production estimates source."""

from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pytest

from core.models.source_run import RunStatus
from domains.coffee.sources.coffee_board_india_supply import (
    _extract_report_date,
    _parse_number,
    _parse_production_table,
    _region_slug,
    fetch,
)

_CLIENT_PATCH = "domains.coffee.sources.coffee_board_india_supply.httpx.Client"
_PDFPLUMBER_PATCH = "domains.coffee.sources.coffee_board_india_supply.pdfplumber.open"

# Real table shape, verified directly against the July 2024 edition via pdfplumber.
_REAL_TABLE = [
    ["Sl.\nNo.", "State/District", "2023-2024", None, None, "2022-2023", None, None],
    [None, None, "Arabica", "Robusta", "Total", "Arabica", "Robusta", "Total"],
    ["I.", "Karnataka", "", "", "", "", "", ""],
    ["1", "Chikkamagaluru", "37,875", "47,280", "85,155", "37,150", "45,300", "82,450"],
    ["2", "Kodagu #", "19,220", "113,400", "132,620", "19,120", "109,600", "128,720"],
    ["3", "Hassan", "15,850", "20,950", "36,800", "15,750", "21,100", "36,850"],
    ["", "Sub total", "72,945", "181,630", "254,575", "72,020", "176,000", "248,020"],
    ["II.", "Kerala", "", "", "", "", "", ""],
    ["1", "Wayanad", "0", "61,950", "61,950", "0", "60,800", "60,800"],
    ["", "Sub total", "2,000", "71,750", "73,750", "1975", "70,450", "72,425"],
    [
        "",
        "Total for Traditional Areas",
        "88,795",
        "258,870",
        "347,665",
        "87,245",
        "251,900",
        "339,145",
    ],
    ["IV.", "Non-Traditional Areas", "", "", "", "", "", ""],
    ["1.", "Andhra Pradesh", "12,170", "40", "12,210", "12,225", "40", "12,265"],
    ["", "Sub Total", "12,635", "40", "12,675", "12,690", "40", "12,730"],
    ["", "North Eastern Region", "70", "90", "160", "65", "60", "125"],
    ["", "Grand Total (India)", "101,500", "259,000", "360,500", "100,000", "252,000", "352,000"],
]


# ── _region_slug ─────────────────────────────────────────────────────────────


class TestRegionSlug:
    def test_plain_slugification(self):
        assert _region_slug("Kodagu") == "kodagu"
        assert _region_slug("Hassan") == "hassan"

    def test_known_spelling_variants_collapse_to_one_slug(self):
        """Real drift found in the live backfill: 'Chikkamagaluru' (2024 editions)
        vs 'Chikmagalur' (2013 editions) — must not split one district's series."""
        assert _region_slug("Chikkamagaluru") == _region_slug("Chikmagalur")

    def test_other_known_aliases(self):
        assert _region_slug("Nilliampathy") == _region_slug("Nelliampathies")
        assert _region_slug("Wyanad") == _region_slug("Wayanad")
        assert _region_slug("Orissa") == _region_slug("Odisha")

    def test_andhra_pradesh_orissa_not_merged_with_andhra_pradesh(self):
        """Older editions genuinely combine two states into one row — a
        structural difference, not a spelling one. Merging would silently
        conflate a two-state figure with a one-state figure."""
        assert _region_slug("Andhra Pradesh") != _region_slug("Andhra Pradesh & Orissa")


# ── _parse_number ────────────────────────────────────────────────────────────


class TestParseNumber:
    def test_comma_formatted(self):
        assert _parse_number("19,220") == pytest.approx(19220.0)

    def test_zero(self):
        assert _parse_number("0") == pytest.approx(0.0)

    def test_dash_variants_are_missing(self):
        assert _parse_number("-") is None
        assert _parse_number("--") is None
        assert _parse_number("---") is None

    def test_none_and_empty(self):
        assert _parse_number(None) is None
        assert _parse_number("") is None
        assert _parse_number("   ") is None


# ── _extract_report_date ─────────────────────────────────────────────────────


class TestExtractReportDate:
    def test_plain_month_year(self):
        assert _extract_report_date("Database on Coffee\nJanuary 2013\n") == date(2013, 1, 31)

    def test_duplicated_characters_quirk(self):
        # Real observed extraction artifact from a bold-font cover page.
        text = "DDaattaabbaassee oonn ccooffffeeee\nJJuunnee // JJuullyy 2016\n"
        assert _extract_report_date(text) == date(2016, 7, 31)

    def test_no_year_returns_none(self):
        assert _extract_report_date("Database on Coffee\nJanuary\n") is None

    def test_no_month_returns_none(self):
        assert _extract_report_date("Database on Coffee\n2013\n") is None


# ── _parse_production_table ──────────────────────────────────────────────────


class TestParseProductionTable:
    def test_extracts_district_rows_from_newest_column(self):
        rows = _parse_production_table(_REAL_TABLE)
        kodagu = {species: v for r, species, v in rows if r == "Kodagu"}
        assert kodagu == {"arabica": 19220.0, "robusta": 113400.0, "total": 132620.0}

    def test_strips_footnote_markers(self):
        rows = _parse_production_table(_REAL_TABLE)
        regions = {r for r, _, _ in rows}
        assert "Kodagu" in regions
        assert "Kodagu #" not in regions

    def test_extracts_national_grand_total(self):
        rows = _parse_production_table(_REAL_TABLE)
        india = {species: v for r, species, v in rows if r == "India"}
        assert india == {"arabica": 101500.0, "robusta": 259000.0, "total": 360500.0}

    def test_skips_section_headers_and_subtotals(self):
        rows = _parse_production_table(_REAL_TABLE)
        regions = {r for r, _, _ in rows}
        assert "Karnataka" not in regions
        assert "Sub total" not in regions
        assert "Total for Traditional Areas" not in regions

    def test_uses_newest_year_not_prior_year(self):
        rows = _parse_production_table(_REAL_TABLE)
        chikkamagaluru_total = next(
            v for r, species, v in rows if r == "Chikkamagaluru" and species == "total"
        )
        assert chikkamagaluru_total == pytest.approx(85155.0)  # 2023-2024, not 82,450 (2022-2023)


# ── fetch() end-to-end ────────────────────────────────────────────────────────


def _fake_pdf(cover_text: str, anchor_text: str, table: list) -> MagicMock:
    cover_page = MagicMock()
    cover_page.extract_text.return_value = cover_text

    anchor_page = MagicMock()
    anchor_page.extract_text.return_value = anchor_text
    anchor_page.extract_tables.return_value = [table]

    pdf = MagicMock()
    pdf.pages = [cover_page, anchor_page]
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    return pdf


def _listing_html(pdf_hrefs: list[str]) -> str:
    links = "".join(f'<a href="{href}">Database</a>' for href in pdf_hrefs)
    return f"<html><body>{links}</body></html>"


def _mock_client(listing_html: str, pdf_bytes_by_url: dict[str, bytes]):
    client = MagicMock()

    def _get(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock(return_value=resp)
        if url.endswith(".html") or "database-coffee" in url:
            resp.text = listing_html
        elif url in pdf_bytes_by_url:
            resp.content = pdf_bytes_by_url[url]
        else:
            resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock(status_code=404, text="not found")
            )
        return resp

    client.get.side_effect = _get
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=client)


_ANCHOR_TEXT = "1.8. Production of Coffee in Major States/Districts (Zones) of India\n(In MT)"


class TestFetch:
    def test_success_single_report(self):
        client_factory = _mock_client(
            _listing_html(["Database/DATABASE3_JULY2024.pdf"]),
            {"https://coffeeboard.gov.in/Database/DATABASE3_JULY2024.pdf": b"%PDF-fake"},
        )
        with (
            patch(_CLIENT_PATCH, client_factory),
            patch(
                _PDFPLUMBER_PATCH,
                return_value=_fake_pdf("July 2024", _ANCHOR_TEXT, _REAL_TABLE),
            ),
        ):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.status == RunStatus.SUCCESS
        assert run.error_message is None
        assert len(obs) == 21  # 7 regions (incl. India) x 3 species, per the trimmed test fixture
        assert all(o.observed_date == date(2024, 7, 31) for o in obs)

        kodagu_total = next(o for o in obs if o.feature_name == "production_mt:kodagu:total")
        assert kodagu_total.value == pytest.approx(132620.0)
        india_arabica = next(o for o in obs if o.feature_name == "production_mt:india:arabica")
        assert india_arabica.value == pytest.approx(101500.0)

    def test_date_range_filters_reports(self):
        client_factory = _mock_client(
            _listing_html(["Database/DATABASE3_JULY2024.pdf"]),
            {"https://coffeeboard.gov.in/Database/DATABASE3_JULY2024.pdf": b"%PDF-fake"},
        )
        with (
            patch(_CLIENT_PATCH, client_factory),
            patch(
                _PDFPLUMBER_PATCH,
                return_value=_fake_pdf("July 2024", _ANCHOR_TEXT, _REAL_TABLE),
            ),
        ):
            obs, run = fetch(date(2020, 1, 1), date(2020, 12, 31))

        assert run.status == RunStatus.SUCCESS
        assert obs == []

    def test_partial_when_one_report_fails_to_download(self):
        client_factory = _mock_client(
            _listing_html(["Database/good.pdf", "Database/missing.pdf"]),
            {"https://coffeeboard.gov.in/Database/good.pdf": b"%PDF-fake"},
        )
        with (
            patch(_CLIENT_PATCH, client_factory),
            patch(
                _PDFPLUMBER_PATCH,
                return_value=_fake_pdf("July 2024", _ANCHOR_TEXT, _REAL_TABLE),
            ),
        ):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.status == RunStatus.PARTIAL
        assert "1 report" in run.error_message
        assert len(obs) == 21

    def test_partial_when_one_report_fails_to_parse(self):
        client_factory = _mock_client(
            _listing_html(["Database/a.pdf", "Database/b.pdf"]),
            {
                "https://coffeeboard.gov.in/Database/a.pdf": b"%PDF-fake-a",
                "https://coffeeboard.gov.in/Database/b.pdf": b"%PDF-fake-b",
            },
        )
        good_pdf = _fake_pdf("July 2024", _ANCHOR_TEXT, _REAL_TABLE)
        with (
            patch(_CLIENT_PATCH, client_factory),
            patch(_PDFPLUMBER_PATCH, side_effect=[good_pdf, RuntimeError("corrupt pdf")]),
        ):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.status == RunStatus.PARTIAL
        assert len(obs) == 21

    def test_failed_when_listing_unreachable(self):
        client = MagicMock()
        client.get.side_effect = httpx.RequestError("connection refused")
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)

        with patch(_CLIENT_PATCH, MagicMock(return_value=client)):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.status == RunStatus.FAILED
        assert obs == []

    def test_failed_when_no_pdfs_listed(self):
        client_factory = _mock_client(_listing_html([]), {})
        with patch(_CLIENT_PATCH, client_factory):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.status == RunStatus.FAILED
        assert obs == []
