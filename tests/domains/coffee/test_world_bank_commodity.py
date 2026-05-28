"""Tests for world_bank_commodity.py — World Bank Pink Sheet price source."""

import io
from datetime import date
from unittest.mock import MagicMock, patch

import openpyxl

from core.models.source_run import RunStatus
from domains.coffee.sources.world_bank_commodity import (
    _parse_wb_date,
    fetch,
)

_PATCH = "domains.coffee.sources.world_bank_commodity.httpx.Client"

# Minimal HTML that contains the expected Excel URL pattern
_WB_PAGE_HTML = (
    '<a href="https://thedocs.worldbank.org/en/doc/abc123-0050012026'
    '/related/CMO-Historical-Data-Monthly.xlsx">Download</a>'
)
_EXCEL_URL = (
    "https://thedocs.worldbank.org/en/doc/abc123-0050012026"
    "/related/CMO-Historical-Data-Monthly.xlsx"
)

# ── Fixture builders ──────────────────────────────────────────────────────────

def _make_excel_bytes(rows: list[tuple]) -> bytes:
    """Build a minimal Pink Sheet Excel in memory with the expected structure.

    rows: list of (date_str, arabica_usd_kg, robusta_usd_kg)
          e.g. [("2024M01", 4.50, 2.10), ...]
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Monthly Prices"

    # Row 1-3: title/subtitle (blank for our purposes)
    ws.append(["World Bank Commodity Price Data (The Pink Sheet)"])
    ws.append(["monthly prices in nominal US dollars"])
    ws.append([""])
    ws.append(["Updated on May 2026"])

    # Row 5 (index 4): human-readable column names
    # col A = date, col M (13) = Coffee, Arabica, col N (14) = Coffee, Robusta
    header_row = [""] * 14
    header_row[12] = "Coffee, Arabica"
    header_row[13] = "Coffee, Robusta"
    ws.append(header_row)

    # Row 6 (index 5): units
    unit_row = [""] * 14
    unit_row[12] = "($/kg)"
    unit_row[13] = "($/kg)"
    ws.append(unit_row)

    # Row 7 (index 6): machine codes
    code_row = [""] * 14
    code_row[12] = "COFFEE_ARABIC"
    code_row[13] = "COFFEE_ROBUS"
    ws.append(code_row)

    # Rows 8+ (index 7+): data
    for date_str, arabica, robusta in rows:
        data_row = [""] * 14
        data_row[0] = date_str
        data_row[12] = arabica
        data_row[13] = robusta
        ws.append(data_row)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _mock_client(page_html: str, excel_bytes: bytes, page_status: int = 200,
                 excel_status: int = 200):
    """Build a mock httpx.Client that returns page HTML then Excel bytes."""
    page_resp = MagicMock()
    page_resp.text = page_html
    page_resp.raise_for_status = MagicMock()
    if page_status >= 400:
        import httpx
        page_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock(
                status_code=page_status, text="error"
            )
        )

    excel_resp = MagicMock()
    excel_resp.content = excel_bytes
    excel_resp.raise_for_status = MagicMock()
    if excel_status >= 400:
        import httpx
        excel_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock(
                status_code=excel_status, text="error"
            )
        )

    mock_client = MagicMock()
    mock_client.get.side_effect = [page_resp, excel_resp]
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=mock_client)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestParsWbDate:
    def test_january(self):
        assert _parse_wb_date("1960M01") == date(1960, 1, 31)

    def test_february_leap(self):
        assert _parse_wb_date("2024M02") == date(2024, 2, 29)

    def test_february_non_leap(self):
        assert _parse_wb_date("2023M02") == date(2023, 2, 28)

    def test_april(self):
        assert _parse_wb_date("2026M04") == date(2026, 4, 30)

    def test_december(self):
        assert _parse_wb_date("2024M12") == date(2024, 12, 31)


class TestFetchSuccess:
    def test_returns_two_observations_per_month(self):
        excel = _make_excel_bytes([("2024M01", 4.50, 2.10), ("2024M02", 4.60, 2.15)])
        with patch(_PATCH, _mock_client(_WB_PAGE_HTML, excel)):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.status == RunStatus.SUCCESS
        assert run.records_fetched == 4  # 2 months × 2 series
        assert run.records_stored == 0
        assert run.error_message is None
        assert len(obs) == 4

    def test_arabica_value_conversion(self):
        """4.50 $/kg → 4.50 × 45.3592 ≈ 204.12 USc/lb."""
        excel = _make_excel_bytes([("2024M01", 4.50, 2.10)])
        with patch(_PATCH, _mock_client(_WB_PAGE_HTML, excel)):
            obs, _ = fetch(date(2024, 1, 1), date(2024, 12, 31))

        arabica_obs = [o for o in obs if "arabica" in o.asset_id]
        assert len(arabica_obs) == 1
        assert arabica_obs[0].unit == "USc/lb"
        assert abs(arabica_obs[0].value - 4.50 * (100 / 2.20462)) < 0.01

    def test_robusta_asset_id_distinct_from_arabica(self):
        excel = _make_excel_bytes([("2024M01", 4.50, 2.10)])
        with patch(_PATCH, _mock_client(_WB_PAGE_HTML, excel)):
            obs, _ = fetch(date(2024, 1, 1), date(2024, 12, 31))

        asset_ids = {o.asset_id for o in obs}
        assert "coffee:benchmark:wb:arabica" in asset_ids
        assert "coffee:benchmark:wb:robusta" in asset_ids

    def test_date_range_filter(self):
        excel = _make_excel_bytes([
            ("2023M12", 4.00, 1.90),
            ("2024M01", 4.50, 2.10),
            ("2025M01", 5.00, 2.50),
        ])
        with patch(_PATCH, _mock_client(_WB_PAGE_HTML, excel)):
            obs, _ = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert all(o.observed_date.year == 2024 for o in obs)
        assert len(obs) == 2  # only Jan 2024

    def test_nan_values_skipped_silently(self):
        """NaN = data not yet published — should not count as parse error."""
        excel = _make_excel_bytes([("2024M01", 4.50, None)])
        with patch(_PATCH, _mock_client(_WB_PAGE_HTML, excel)):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.status == RunStatus.SUCCESS
        assert len(obs) == 1  # only arabica; robusta NaN skipped

    def test_observed_date_is_month_end(self):
        excel = _make_excel_bytes([("2024M02", 4.50, 2.10)])
        with patch(_PATCH, _mock_client(_WB_PAGE_HTML, excel)):
            obs, _ = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert all(o.observed_date == date(2024, 2, 29) for o in obs)

    def test_raw_field_contains_wb_code_and_usd_kg(self):
        excel = _make_excel_bytes([("2024M01", 4.50, 2.10)])
        with patch(_PATCH, _mock_client(_WB_PAGE_HTML, excel)):
            obs, _ = fetch(date(2024, 1, 1), date(2024, 12, 31))

        arabica = next(o for o in obs if "arabica" in o.asset_id)
        assert arabica.raw["wb_code"] == "COFFEE_ARABIC"
        assert arabica.raw["usd_kg"] == 4.50
        assert arabica.raw["date_str"] == "2024M01"


class TestFetchErrors:
    def test_page_url_not_found_returns_failed_run(self):
        """If the WB page HTML doesn't contain the expected Excel URL pattern."""
        excel = _make_excel_bytes([("2024M01", 4.50, 2.10)])
        with patch(_PATCH, _mock_client("<html>no link here</html>", excel)):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.status == RunStatus.FAILED
        assert obs == []
        assert "Could not locate" in (run.error_message or "")

    def test_http_error_on_page_fetch_returns_failed_run(self):
        import httpx
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.text = "Forbidden"
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403", request=MagicMock(), response=MagicMock(status_code=403, text="Forbidden")
        )
        mock_client.get.return_value = mock_resp

        with patch(_PATCH, MagicMock(return_value=mock_client)):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.status == RunStatus.FAILED
        assert obs == []
        assert "403" in (run.error_message or "")

    def test_request_error_returns_failed_run(self):
        import httpx
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.RequestError("connection refused")

        with patch(_PATCH, MagicMock(return_value=mock_client)):
            obs, run = fetch(date(2024, 1, 1), date(2024, 12, 31))

        assert run.status == RunStatus.FAILED
        assert obs == []
        assert "connection refused" in (run.error_message or "")
