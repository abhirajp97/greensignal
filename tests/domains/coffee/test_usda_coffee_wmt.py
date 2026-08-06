"""Tests for usda_coffee_wmt.py — USDA Coffee: World Markets and Trade source."""

from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pytest

from core.models.source_run import RunStatus
from domains.coffee.sources.usda_coffee_wmt import (
    _CONSUMPTION_HEADER_RE,
    _STOCKS_HEADER_RE,
    _discover_reports,
    _find_summary_segment,
    _parse_listing_page,
    _parse_stocks_to_use,
    _section_total,
    fetch,
    stu_wmt_stress_score,
    stu_wmt_zscore,
)

_CLIENT_PATCH = "domains.coffee.sources.usda_coffee_wmt.httpx.Client"
_PDFPLUMBER_PATCH = "domains.coffee.sources.usda_coffee_wmt.pdfplumber.open"

# ── Real-format text fixtures ───────────────────────────────────────────────
# Trimmed but structurally faithful excerpts of actual extracted PDF text,
# captured from live reports during development (Dec 2025 split-table format
# and Dec 2010 combined-table format). World "Total" values are the real
# published figures for those reports.

_SPLIT_FORMAT_SEGMENT = """Thousand 60-Kilogram Bags
Jun Dec
2021/22 2022/23 2023/24 2024/25 2025/26 2025/26
Domestic Consumption none
European Union 41,897 44,497 39,613 41,211 40,100 41,870
United States 26,708 24,623 23,545 26,220 25,550 26,550
Other 12,184 12,717 12,290 12,696 12,733 12,804
Total 167,883 168,754 163,968 171,556 169,363 173,852
Ending Stocks none
European Union 14,000 9,313 8,626 8,170 8,500 7,800
United States 6,378 5,700 5,700 5,700 5,700 5,700
Other 1,316 1,288 1,145 1,131 1,391 1,055
Total 31,940 26,934 23,121 21,307 22,819 20,148
Coffee marketing year for producer countries begins either in October
(Colombia), April (Indonesia) or July (Brazil), as examples.
"""

_COMBINED_FORMAT_TEXT = """United States Department of Agriculture
Ending Stocks
World green coffee bean ending stocks are reduced 4.9 million.
Table 01A Coffee Production, Consumption and Ending Stocks
Thousand 60-Kilogram Bags
Jun Dec
2006/07 2007/08 2008/09 2009/10 2010/11 2010/11
Production none
Brazil 46,700 39,100 53,300 44,800 55,300 54,500
Total 131,818 121,984 133,623 126,916 139,696 139,084
Domestic Consumption none
EU-27 44,325 45,845 41,805 51,730 46,275 45,130
Total 123,900 127,309 124,112 135,598 131,498 131,025
Ending Stocks none
EU-27 14,460 14,375 17,925 12,430 17,225 14,500
Total 35,108 30,163 36,968 25,838 36,303 31,343
Notes:
Coffee marketing year for producer countries begins either in October (Colombia).
"""

_NARRATIVE_ONLY_TEXT = """Ending Stocks
World green coffee bean ending stocks are reduced 4.9 million.
For further information, please contact someone at USDA.
"""

# ── _parse_stocks_to_use / _find_summary_segment / _section_total ──────────


class TestParseStocksToUse:
    def test_split_format_2025(self):
        # 20,148 / 173,852 * 100
        stu = _parse_stocks_to_use(_SPLIT_FORMAT_SEGMENT)
        assert stu == pytest.approx(11.589, abs=1e-2)

    def test_combined_format_2010(self):
        # 31,343 / 131,025 * 100 -- and must NOT grab the Production total
        # (131,818) or the page-1 narrative "Ending Stocks" mention.
        stu = _parse_stocks_to_use(_COMBINED_FORMAT_TEXT)
        assert stu == pytest.approx(23.921, abs=1e-2)

    def test_narrative_only_returns_none(self):
        # "Ending Stocks" appears as prose, no "Thousand 60-Kilogram Bags"
        # anchor and no Domestic Consumption section at all.
        assert _parse_stocks_to_use(_NARRATIVE_ONLY_TEXT) is None

    def test_missing_consumption_section_returns_none(self):
        text = "Thousand 60-Kilogram Bags\nEnding Stocks none\nBrazil 100\nTotal 500\n"
        assert _parse_stocks_to_use(text) is None

    def test_zero_consumption_returns_none(self):
        text = (
            "Thousand 60-Kilogram Bags\n"
            "Domestic Consumption none\nTotal 0\n"
            "Ending Stocks none\nTotal 500\n"
        )
        assert _parse_stocks_to_use(text) is None


class TestFindSummarySegment:
    def test_skips_page_without_both_headers(self):
        text = (
            "Thousand 60-Kilogram Bags\nProduction none\nTotal 100\n"
            "Thousand 60-Kilogram Bags\n"
            "Domestic Consumption none\nTotal 200\n"
            "Ending Stocks none\nTotal 50\n"
        )
        seg = _find_summary_segment(text)
        assert seg is not None
        assert "Domestic Consumption" in seg
        assert "Ending Stocks" in seg

    def test_no_anchor_returns_none(self):
        assert _find_summary_segment("Domestic Consumption\nEnding Stocks\n") is None


class TestSectionTotal:
    def test_extracts_last_number(self):
        segment = "Domestic Consumption none\nBrazil 10\nTotal 100 110 120 130\n"
        assert _section_total(segment, _CONSUMPTION_HEADER_RE) == pytest.approx(130.0)

    def test_missing_header_returns_none(self):
        segment = "Ending Stocks none\nTotal 100\n"
        assert _section_total(segment, _CONSUMPTION_HEADER_RE) is None

    def test_total_too_far_away_returns_none(self):
        far_filler = "x " * 2000
        segment = f"Domestic Consumption none\n{far_filler}\nTotal 100\n"
        assert _section_total(segment, _CONSUMPTION_HEADER_RE) is None

    def test_no_total_line_returns_none(self):
        segment = "Domestic Consumption none\nBrazil 10\nNo total here\n"
        assert _section_total(segment, _STOCKS_HEADER_RE) is None


# ── _parse_listing_page ─────────────────────────────────────────────────────


class TestParseListingPage:
    _HTML = """
    <table><tbody>
    <tr>
      <td><time datetime="2024-12-18T12:00:00Z">Dec 18 2024</time></td>
      <td><a class="usa-tag usa-tag--big" href="/sites/default/release-files/abc/def/coffee.pdf">
        pdf</a></td>
    </tr>
    <tr>
      <td><time datetime="2010-06-18T12:00:00Z">Jun 18 2010</time></td>
      <td><a class="usa-tag" href="/sites/default/release-files/xyz/123/tropprod-06-18-2010.pdf">
        pdf</a></td>
    </tr>
    <tr>
      <td>no time or link here — must be skipped</td>
    </tr>
    </tbody></table>
    """

    def test_extracts_date_and_absolute_url(self):
        rows = _parse_listing_page(self._HTML)
        assert (
            date(2024, 12, 18),
            "https://esmis.nal.usda.gov/sites/default/release-files/abc/def/coffee.pdf",
        ) in rows
        assert (
            date(2010, 6, 18),
            "https://esmis.nal.usda.gov/sites/default/release-files/xyz/123/tropprod-06-18-2010.pdf",
        ) in rows

    def test_skips_malformed_rows(self):
        rows = _parse_listing_page(self._HTML)
        assert len(rows) == 2

    def test_empty_page_returns_empty_list(self):
        assert _parse_listing_page("<table><tbody></tbody></table>") == []


# ── _discover_reports pagination ────────────────────────────────────────────


def _listing_html(pairs: list[tuple[str, str]]) -> str:
    rows = "".join(
        f'<tr><td><time datetime="{d}T12:00:00Z"></time></td>'
        f'<td><a class="usa-tag" href="{url}">pdf</a></td></tr>'
        for d, url in pairs
    )
    return f"<table><tbody>{rows}</tbody></table>"


def _mock_get(responder):
    """Build a MagicMock httpx.Client whose .get() delegates to `responder(url, **kwargs)`."""
    client = MagicMock()

    def _get(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        text, status = responder(url, kwargs)
        if status >= 400:
            resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "error", request=MagicMock(), response=MagicMock(status_code=status, text="err")
            )
        resp.text = text
        resp.content = text.encode() if isinstance(text, str) else text
        return resp

    client.get.side_effect = _get
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=client)


class TestDiscoverReports:
    def test_stops_on_empty_page(self):
        pages = {
            0: _listing_html([("2024-12-18", "/a/coffee.pdf")]),
            1: "<table><tbody></tbody></table>",
        }

        def responder(url, kwargs):
            page = kwargs.get("params", {}).get("page", 0)
            return pages.get(page, "<table><tbody></tbody></table>"), 200

        client = _mock_get(responder)()
        reports = _discover_reports(client)
        assert reports == [(date(2024, 12, 18), "https://esmis.nal.usda.gov/a/coffee.pdf")]
        assert client.get.call_count == 2  # page 0, then empty page 1 stops it

    def test_stops_when_page_repeats_no_new_dates(self):
        # Simulates the real ESMIS behavior: past the real archive depth the
        # pager returns page 0's content again instead of an empty page.
        page0_html = _listing_html([("2024-12-18", "/a/coffee.pdf")])

        def responder(url, kwargs):
            return page0_html, 200  # every page returns the same content

        client = _mock_get(responder)()
        reports = _discover_reports(client)
        assert reports == [(date(2024, 12, 18), "https://esmis.nal.usda.gov/a/coffee.pdf")]
        assert client.get.call_count == 2  # page 0 (new), page 1 (no new dates) stops it


# ── fetch() end-to-end ───────────────────────────────────────────────────────


def _fake_pdf_open(text: str):
    """Return a context-manager mock standing in for pdfplumber.open(...)."""
    page = MagicMock()
    page.extract_text.return_value = text
    pdf = MagicMock()
    pdf.pages = [page]
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    return pdf


class TestFetch:
    def test_success_single_report(self):
        listing_html = _listing_html([("2024-12-18", "/a/coffee.pdf")])

        def responder(url, kwargs):
            if "publication" in url:
                page = kwargs.get("params", {}).get("page", 0)
                return (listing_html if page == 0 else "<table><tbody></tbody></table>"), 200
            return "pdf-bytes", 200

        client_factory = _mock_get(responder)

        with (
            patch(_CLIENT_PATCH, client_factory),
            patch(_PDFPLUMBER_PATCH, return_value=_fake_pdf_open(_SPLIT_FORMAT_SEGMENT)),
        ):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.status == RunStatus.SUCCESS
        assert run.records_fetched == 1
        assert len(obs) == 1
        assert obs[0].observed_date == date(2024, 12, 18)
        assert obs[0].value == pytest.approx(11.589, abs=1e-2)
        assert obs[0].feature_name == "stocks_to_use_pct"

    def test_partial_when_one_report_fails_to_parse(self):
        listing_html = _listing_html(
            [("2024-12-18", "/a/coffee.pdf"), ("2024-06-20", "/b/coffee.pdf")]
        )

        def responder(url, kwargs):
            if "publication" in url:
                page = kwargs.get("params", {}).get("page", 0)
                return (listing_html if page == 0 else "<table><tbody></tbody></table>"), 200
            return "pdf-bytes", 200

        client_factory = _mock_get(responder)

        # First PDF opened parses fine, second raises during extraction.
        good_pdf = _fake_pdf_open(_SPLIT_FORMAT_SEGMENT)
        with (
            patch(_CLIENT_PATCH, client_factory),
            patch(_PDFPLUMBER_PATCH, side_effect=[good_pdf, RuntimeError("corrupt pdf")]),
        ):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.status == RunStatus.PARTIAL
        assert run.records_fetched == 1
        assert "PDF text extraction failed" in run.error_message

    def test_partial_when_download_fails(self):
        listing_html = _listing_html(
            [("2024-12-18", "/a/coffee.pdf"), ("2024-06-20", "/b/coffee.pdf")]
        )

        def responder(url, kwargs):
            if "publication" in url:
                page = kwargs.get("params", {}).get("page", 0)
                return (listing_html if page == 0 else "<table><tbody></tbody></table>"), 200
            if url.endswith("/a/coffee.pdf"):
                return "not found", 404
            return "pdf-bytes", 200

        client_factory = _mock_get(responder)

        with (
            patch(_CLIENT_PATCH, client_factory),
            patch(_PDFPLUMBER_PATCH, return_value=_fake_pdf_open(_SPLIT_FORMAT_SEGMENT)),
        ):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.status == RunStatus.PARTIAL
        assert run.records_fetched == 1
        assert "download failed" in run.error_message

    def test_failed_when_listing_request_error(self):
        client = MagicMock()
        client.get.side_effect = httpx.RequestError("connection reset")
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)

        with patch(_CLIENT_PATCH, MagicMock(return_value=client)):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.status == RunStatus.FAILED
        assert "Request error" in run.error_message
        assert obs == []

    def test_date_range_filters_reports(self):
        listing_html = _listing_html(
            [("2024-12-18", "/a/coffee.pdf"), ("2010-06-18", "/b/coffee.pdf")]
        )

        def responder(url, kwargs):
            if "publication" in url:
                page = kwargs.get("params", {}).get("page", 0)
                return (listing_html if page == 0 else "<table><tbody></tbody></table>"), 200
            return "pdf-bytes", 200

        client_factory = _mock_get(responder)

        with (
            patch(_CLIENT_PATCH, client_factory),
            patch(_PDFPLUMBER_PATCH, return_value=_fake_pdf_open(_SPLIT_FORMAT_SEGMENT)),
        ):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.records_fetched == 1
        assert obs[0].observed_date == date(2024, 12, 18)

    def test_failed_when_listing_page_unreachable(self):
        def responder(url, kwargs):
            return "error", 500

        client_factory = _mock_get(responder)
        with patch(_CLIENT_PATCH, client_factory):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.status == RunStatus.FAILED
        assert obs == []

    def test_failed_when_no_reports_discovered(self):
        def responder(url, kwargs):
            return "<table><tbody></tbody></table>", 200

        client_factory = _mock_get(responder)
        with patch(_CLIENT_PATCH, client_factory):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.status == RunStatus.FAILED
        assert obs == []

    def test_failed_when_all_reports_unparseable(self):
        listing_html = _listing_html([("2024-12-18", "/a/coffee.pdf")])

        def responder(url, kwargs):
            if "publication" in url:
                page = kwargs.get("params", {}).get("page", 0)
                return (listing_html if page == 0 else "<table><tbody></tbody></table>"), 200
            return "pdf-bytes", 200

        client_factory = _mock_get(responder)
        with (
            patch(_CLIENT_PATCH, client_factory),
            patch(_PDFPLUMBER_PATCH, return_value=_fake_pdf_open(_NARRATIVE_ONLY_TEXT)),
        ):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.status == RunStatus.FAILED
        assert obs == []


class TestStuWmtZscore:
    def test_matches_notebook_04_cached_values(self):
        # The 6 true-vintage stu_wmt % readings preceding the 2013-06-21
        # report, and that report's own value, from
        # notebooks/coffee_backtests/data/stu_wmt_vintage.csv — cross-checked
        # against that notebook's own rolling_zscore(window=6)/
        # stu_stress_score output (z=+0.7338, stress=0.3166).
        trailing = [
            19.698112080742327,
            23.921389047891623,
            19.698112080742327,
            17.91416084569123,
            19.195105428063343,
            19.73290515162018,
        ]
        z = stu_wmt_zscore(21.516935114369296, trailing)
        assert z == pytest.approx(0.7338, abs=1e-3)
        assert stu_wmt_stress_score(z) == pytest.approx(0.3166, abs=1e-3)

    def test_raises_below_window(self):
        with pytest.raises(ValueError, match="need at least 6"):
            stu_wmt_zscore(20.0, [19.0, 21.0, 20.0])

    def test_zero_stdev_returns_zero(self):
        assert stu_wmt_zscore(20.0, [20.0] * 6) == 0.0


class TestStuWmtStressScore:
    def test_clamps_to_0_1(self):
        assert stu_wmt_stress_score(10.0) == 0.0
        assert stu_wmt_stress_score(-10.0) == 1.0

    def test_neutral_at_zero(self):
        assert stu_wmt_stress_score(0.0) == pytest.approx(0.5)
