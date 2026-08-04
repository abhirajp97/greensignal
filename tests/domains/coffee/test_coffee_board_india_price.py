"""Tests for coffee_board_india_price.py — India daily raw coffee price source."""

from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pytest

from core.models.source_run import RunStatus
from domains.coffee.sources.coffee_board_india_price import (
    _discover_year_month_grid,
    _hidden_fields,
    _list_days,
    _parse_raw_price_table,
    _postback_target,
    fetch,
)

_CLIENT_PATCH = "domains.coffee.sources.coffee_board_india_price.httpx.Client"

# Real report text, verified directly via pdfplumber against a live daily PDF
# (June 1, 2026 edition — see docs/india_origin_signal_plan_v2_full_build.md).
_REAL_REPORT_TEXT = """COFFEE BOARD: BENGALURU
Daily Coffee Market Report, Monday, June 01, 2026
Futures Prices 29.05.2026
ICTA Auction Prices ₹/Kg as on 28.05.2026/ 2025-26
Grade MNEB AA PB A AB B C BBB AAA
Raw Coffee Price (Karnataka) as on 29.05.2026 in ₹/50 Kg
Ar.Pmt Ar.Chy Rob.Pmt Rob.Chy
22300 - 23000 12750 - 14250 17500 - 18300 9300 - 10100
Export update: From 1st January 2026 to 29th May 2026 (in Metric Tonnes)
"""


# ── _hidden_fields / _postback_target ────────────────────────────────────────


class TestHiddenFields:
    def test_extracts_viewstate_fields(self):
        html = (
            '<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="abc123" />'
            '<input type="hidden" name="__EVENTVALIDATION" value="xyz" />'
        )
        fields = _hidden_fields(html)
        assert fields == {"__VIEWSTATE": "abc123", "__EVENTVALIDATION": "xyz"}

    def test_no_hidden_fields_returns_empty_dict(self):
        assert _hidden_fields("<html><body>no fields here</body></html>") == {}


class TestPostbackTarget:
    def test_extracts_control_name(self):
        href = "javascript:__doPostBack('GridView1$ctl07$LinkButton2026','')"
        assert _postback_target(href) == "GridView1$ctl07$LinkButton2026"

    def test_non_postback_href_returns_none(self):
        assert _postback_target("https://example.com") is None


# ── _parse_raw_price_table ────────────────────────────────────────────────────


class TestParseRawPriceTable:
    def test_extracts_all_four_series(self):
        rows = _parse_raw_price_table_from_text(_REAL_REPORT_TEXT)
        assert len(rows) == 4
        by_grade = {grade: (low, high) for _, _, grade, low, high in rows}
        assert by_grade["arabica_parchment"] == (22300.0, 23000.0)
        assert by_grade["arabica_cherry"] == (12750.0, 14250.0)
        assert by_grade["robusta_parchment"] == (17500.0, 18300.0)
        assert by_grade["robusta_cherry"] == (9300.0, 10100.0)

    def test_uses_the_tables_own_as_on_date_not_report_date(self):
        """The report is nominally dated June 1, but this table's own 'as on'
        date (May 29) is what gets used — a real, observed lag between the
        report's nominal date and the sub-table's actual as-of date."""
        rows = _parse_raw_price_table_from_text(_REAL_REPORT_TEXT)
        assert all(observed_date == date(2026, 5, 29) for observed_date, *_ in rows)

    def test_assigns_correct_asset_per_species(self):
        rows = _parse_raw_price_table_from_text(_REAL_REPORT_TEXT)
        by_grade = {grade: asset_id for _, asset_id, grade, _, _ in rows}
        assert by_grade["arabica_parchment"] == "coffee:origin:india:arabica"
        assert by_grade["arabica_cherry"] == "coffee:origin:india:arabica"
        assert by_grade["robusta_parchment"] == "coffee:origin:india:robusta"
        assert by_grade["robusta_cherry"] == "coffee:origin:india:robusta"

    def test_missing_table_returns_empty_list(self):
        assert _parse_raw_price_table_from_text("no relevant table here") == []

    def test_out_of_range_values_are_dropped(self):
        text = _REAL_REPORT_TEXT.replace("22300 - 23000", "99999999 - 99999999")
        rows = _parse_raw_price_table_from_text(text)
        grades = {grade for _, _, grade, _, _ in rows}
        assert "arabica_parchment" not in grades
        assert len(rows) == 3


def _parse_raw_price_table_from_text(text: str):
    """Exercise _parse_raw_price_table via a mocked pdfplumber.open, since the
    real function takes PDF bytes, not text."""
    page = MagicMock()
    page.extract_text.return_value = text
    pdf = MagicMock()
    pdf.pages = [page]
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    with patch("domains.coffee.sources.coffee_board_india_price.pdfplumber.open", return_value=pdf):
        return _parse_raw_price_table(b"%PDF-fake")


# ── ASP.NET flow helpers ──────────────────────────────────────────────────────

_HIDDEN = '<input type="hidden" name="__VIEWSTATE" value="vs" />'

_MARKET_INFO_HTML = f"<html><body>{_HIDDEN}</body></html>"

_ARCHIVES_GRID_HTML = f"""<html><body>{_HIDDEN}
<table id="GridView1">
<tr><th>2026</th><th>2025</th></tr>
<tr><td><a href="javascript:__doPostBack('GridView1$ctl02$LinkButtonJan2026','')">Jan</a></td>
    <td><a href="javascript:__doPostBack('GridView1$ctl02$LinkButtonJan2025','')">Jan</a></td></tr>
<tr><td><a href="javascript:__doPostBack('GridView1$ctl03$LinkButtonFeb2026','')">Feb</a></td>
    <td></td></tr>
</table>
</body></html>"""

def _day_link(ctl: str, label: str) -> str:
    return f"<a href=\"javascript:__doPostBack('{ctl}','')\">{label}</a>"


_DAY1_LINK = _day_link("DataList1$ctl00$LinkButton1", "2026,Jan,01")
_DAY2_LINK = _day_link("DataList1$ctl01$LinkButton1", "2026,Jan,02")
_MONTH_DAYS_HTML = f"""<html><body>{_HIDDEN}
<table id="DataList1">
<tr><td>{_DAY1_LINK}</td></tr>
<tr><td>{_DAY2_LINK}</td></tr>
</table>
</body></html>"""

_MONTH_NO_DAYS_HTML = f"<html><body>{_HIDDEN}</body></html>"  # no archived days at all


def _mock_client(day_pdf: bytes = b"%PDF-fake"):
    client = MagicMock()

    def _get(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock(return_value=resp)
        resp.text = _MARKET_INFO_HTML
        return resp

    def _post(url, data=None, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock(return_value=resp)
        target = (data or {}).get("__EVENTTARGET", "")
        if target == "lbnarchives":
            resp.text = _ARCHIVES_GRID_HTML
        elif "LinkButtonJan2026" in target:
            resp.text = _MONTH_DAYS_HTML
        elif "LinkButtonFeb2026" in target:
            resp.text = _MONTH_NO_DAYS_HTML
        elif target.startswith("DataList1"):
            resp.content = day_pdf
        else:
            resp.text = "<html></html>"
        return resp

    client.get.side_effect = _get
    client.post.side_effect = _post
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=client)


class TestDiscoverYearMonthGrid:
    def test_maps_years_and_months_to_controls(self):
        client = _mock_client()()
        grid = _discover_year_month_grid(client)
        assert grid[2026][0] == "GridView1$ctl02$LinkButtonJan2026"  # January
        assert grid[2026][1] == "GridView1$ctl03$LinkButtonFeb2026"  # February
        assert grid[2025][0] == "GridView1$ctl02$LinkButtonJan2025"

    def test_missing_grid_raises(self):
        client = MagicMock()
        resp = MagicMock()
        resp.raise_for_status = MagicMock(return_value=resp)
        resp.text = "<html><body>no grid here</body></html>"
        client.get.return_value = resp
        client.post.return_value = resp
        with pytest.raises(httpx.HTTPError):
            _discover_year_month_grid(client)


class TestListDays:
    def test_lists_day_controls(self):
        client = _mock_client()()
        days, fields = _list_days(client, "GridView1$ctl02$LinkButtonJan2026")
        assert days == [
            ("2026,Jan,01", "DataList1$ctl00$LinkButton1"),
            ("2026,Jan,02", "DataList1$ctl01$LinkButton1"),
        ]
        assert "__VIEWSTATE" in fields

    def test_no_days_returns_empty_list(self):
        client = _mock_client()()
        days, _fields = _list_days(client, "GridView1$ctl03$LinkButtonFeb2026")
        assert days == []


# ── fetch() end-to-end ────────────────────────────────────────────────────────


class TestFetch:
    def test_success(self):
        pdf_bytes = b"%PDF-fake-content"
        client_factory = _mock_client(day_pdf=pdf_bytes)
        with (
            patch(_CLIENT_PATCH, client_factory),
            patch(
                "domains.coffee.sources.coffee_board_india_price.time.sleep",
            ),
            patch(
                "domains.coffee.sources.coffee_board_india_price._parse_raw_price_table",
                return_value=[
                    (
                        date(2026, 1, 1),
                        "coffee:origin:india:arabica",
                        "arabica_parchment",
                        100.0,
                        200.0,
                    ),
                ],
            ),
        ):
            obs, run = fetch(date(2026, 1, 1), date(2026, 1, 31))

        assert run.status == RunStatus.SUCCESS
        assert len(obs) == 2  # 2 archived days x 1 mocked series each
        assert obs[0].value == pytest.approx(150.0)  # midpoint of 100-200
        assert obs[0].raw == {"grade": "arabica_parchment", "range_low": 100.0, "range_high": 200.0}

    def test_partial_when_a_day_fails_to_parse(self):
        client_factory = _mock_client()
        with (
            patch(_CLIENT_PATCH, client_factory),
            patch("domains.coffee.sources.coffee_board_india_price.time.sleep"),
            patch(
                "domains.coffee.sources.coffee_board_india_price._parse_raw_price_table",
                side_effect=[RuntimeError("corrupt"), []],
            ),
        ):
            obs, run = fetch(date(2026, 1, 1), date(2026, 1, 31))

        assert run.status == RunStatus.PARTIAL
        assert "1 day" in run.error_message

    def test_year_outside_grid_range_fails(self):
        client_factory = _mock_client()
        with (
            patch(_CLIENT_PATCH, client_factory),
            patch("domains.coffee.sources.coffee_board_india_price.time.sleep"),
        ):
            obs, run = fetch(date(2030, 1, 1), date(2030, 1, 31))

        assert run.status == RunStatus.FAILED
        assert obs == []
