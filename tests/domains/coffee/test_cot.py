"""Tests for cot.py — CFTC disaggregated Commitments of Traders source."""

import io
import zipfile
from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pandas as pd
import pytest

from core.models.source_run import RunStatus
from domains.coffee.sources.cot import (
    _cot_index,
    cot_contrarian_signal,
    fetch,
)

_PATCH = "domains.coffee.sources.cot.httpx.Client"

# ── CSV fixture ────────────────────────────────────────────────────────────────

_HEADER = (
    "Market_and_Exchange_Names,Report_Date_as_YYYY-MM-DD,"
    "M_Money_Positions_Long_All,M_Money_Positions_Short_All\n"
)

# Two KC rows + one unrelated market (must be filtered out) + one malformed KC row
_ROWS = (
    "COFFEE C - ICE FUTURES U.S.,2023-01-03,50000,20000\n"   # net +30000
    "COFFEE C - ICE FUTURES U.S.,2023-01-10,18000,40000\n"   # net -22000
    "SUGAR NO. 11 - ICE FUTURES U.S.,2023-01-03,99999,11111\n"  # other market — skip
    "COFFEE C - ICE FUTURES U.S.,2023-01-17,33000,33000\n"   # net 0
)

_CSV = _HEADER + _ROWS


def _zip_bytes(csv_text: str, name: str = "f_year.txt") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name, csv_text)
    return buf.getvalue()


def _mock_client(content: bytes, status: int = 200):
    resp = MagicMock()
    resp.content = content
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error",
            request=MagicMock(),
            response=MagicMock(status_code=status, text="error"),
        )
    client = MagicMock()
    client.get.return_value = resp
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=client)


# ── _cot_index ───────────────────────────────────────────────────────────────


class TestCotIndex:
    def test_min_maps_to_zero(self):
        s = pd.Series([10.0, 20.0, 30.0, 0.0])
        idx = _cot_index(s, window=4)
        assert idx.iloc[3] == pytest.approx(0.0)

    def test_max_maps_to_hundred(self):
        s = pd.Series([10.0, 20.0, 30.0, 40.0])
        idx = _cot_index(s, window=4)
        assert idx.iloc[3] == pytest.approx(100.0)

    def test_midpoint(self):
        s = pd.Series([0.0, 100.0, 50.0])
        idx = _cot_index(s, window=3)
        assert idx.iloc[2] == pytest.approx(50.0)

    def test_flat_window_is_neutral(self):
        """When max == min the index is undefined → set to 50 (neutral)."""
        s = pd.Series([5.0, 5.0, 5.0])
        idx = _cot_index(s, window=3)
        assert idx.iloc[2] == pytest.approx(50.0)

    def test_output_in_unit_range(self):
        s = pd.Series([-30000.0, 10000.0, 50000.0, -22000.0, 0.0])
        idx = _cot_index(s, window=156)
        assert ((idx >= 0.0) & (idx <= 100.0)).all()


# ── cot_contrarian_signal ──────────────────────────────────────────────────────


class TestContrarianSignal:
    def test_low_index_is_buy(self):
        assert cot_contrarian_signal(10.0) == 1.0

    def test_high_index_is_caution(self):
        assert cot_contrarian_signal(90.0) == -1.0

    def test_mid_index_is_neutral(self):
        assert cot_contrarian_signal(50.0) == 0.0

    def test_boundaries(self):
        assert cot_contrarian_signal(25.0) == 0.0   # not < 25
        assert cot_contrarian_signal(75.0) == 0.0   # not > 75
        assert cot_contrarian_signal(24.99) == 1.0
        assert cot_contrarian_signal(75.01) == -1.0


# ── fetch — success path ───────────────────────────────────────────────────────


class TestFetchSuccess:
    def test_returns_only_kc_rows(self):
        with patch(_PATCH, _mock_client(_zip_bytes(_CSV))):
            obs, run = fetch(date(2023, 1, 1), date(2023, 12, 31))
        assert run.status == RunStatus.SUCCESS
        assert run.records_fetched == 3   # 3 KC rows; SUGAR filtered out
        assert run.records_stored == 0
        assert run.error_message is None
        assert len(obs) == 3

    def test_net_position_is_long_minus_short(self):
        with patch(_PATCH, _mock_client(_zip_bytes(_CSV))):
            obs, _ = fetch(date(2023, 1, 1), date(2023, 12, 31))
        by_date = {o.observed_date: o.value for o in obs}
        assert by_date[date(2023, 1, 3)] == pytest.approx(30000.0)
        assert by_date[date(2023, 1, 10)] == pytest.approx(-22000.0)
        assert by_date[date(2023, 1, 17)] == pytest.approx(0.0)

    def test_feature_name_and_asset(self):
        with patch(_PATCH, _mock_client(_zip_bytes(_CSV))):
            obs, _ = fetch(date(2023, 1, 1), date(2023, 12, 31))
        for o in obs:
            assert o.feature_name == "managed_money_net"
            assert o.asset_id == "coffee:cot:kc"
            assert o.source == "cftc:disaggregated"

    def test_observations_sorted_by_date(self):
        with patch(_PATCH, _mock_client(_zip_bytes(_CSV))):
            obs, _ = fetch(date(2023, 1, 1), date(2023, 12, 31))
        dates = [o.observed_date for o in obs]
        assert dates == sorted(dates)

    def test_date_range_filter(self):
        """Rows outside [start, end] are excluded."""
        with patch(_PATCH, _mock_client(_zip_bytes(_CSV))):
            obs, _ = fetch(date(2023, 1, 5), date(2023, 1, 12))
        dates = [o.observed_date for o in obs]
        assert dates == [date(2023, 1, 10)]

    def test_pre_2013_date_column_name(self):
        """Pre-2013 vintages name the column Report_Date_as_MM_DD_YYYY (ISO values)."""
        old_header = (
            "Market_and_Exchange_Names,Report_Date_as_MM_DD_YYYY,"
            "M_Money_Positions_Long_All,M_Money_Positions_Short_All\n"
        )
        old_csv = old_header + "COFFEE C - ICE FUTURES U.S.,2011-06-07,40000,10000\n"
        with patch(_PATCH, _mock_client(_zip_bytes(old_csv))):
            obs, run = fetch(date(2011, 1, 1), date(2011, 12, 31))
        assert run.status == RunStatus.SUCCESS
        assert len(obs) == 1
        assert obs[0].observed_date == date(2011, 6, 7)
        assert obs[0].value == pytest.approx(30000.0)

    def test_txt_member_located_dynamically(self):
        """Archive member name other than f_year.txt is still found."""
        zb = _zip_bytes(_CSV, name="annual_2023.txt")
        with patch(_PATCH, _mock_client(zb)):
            obs, run = fetch(date(2023, 1, 1), date(2023, 12, 31))
        assert run.status == RunStatus.SUCCESS
        assert len(obs) == 3


# ── fetch — multi-year + partial ───────────────────────────────────────────────


class TestFetchMultiYear:
    def test_one_failing_year_yields_partial(self):
        """Range spans 2 years; first year 404s, second succeeds → PARTIAL."""
        ok_resp = MagicMock()
        ok_resp.content = _zip_bytes(_CSV)
        ok_resp.raise_for_status = MagicMock()

        bad_resp = MagicMock()
        bad_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(),
            response=MagicMock(status_code=404, text="not found"),
        )
        client = MagicMock()
        client.get.side_effect = [bad_resp, ok_resp]
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)

        # CSV dates are 2023; request 2022-2023 so the 2023 rows survive the filter
        with patch(_PATCH, MagicMock(return_value=client)):
            obs, run = fetch(date(2022, 1, 1), date(2023, 12, 31))
        assert run.status == RunStatus.PARTIAL
        assert len(obs) == 3
        assert "2022" in (run.error_message or "")

    def test_partial_on_malformed_position_value(self):
        bad_csv = _HEADER + (
            "COFFEE C - ICE FUTURES U.S.,2023-01-03,50000,20000\n"
            "COFFEE C - ICE FUTURES U.S.,2023-01-10,NOTANUMBER,40000\n"
        )
        with patch(_PATCH, _mock_client(_zip_bytes(bad_csv))):
            obs, run = fetch(date(2023, 1, 1), date(2023, 12, 31))
        assert run.status == RunStatus.PARTIAL
        assert len(obs) == 1
        assert run.records_fetched == 1


# ── fetch — error paths ────────────────────────────────────────────────────────


class TestFetchErrors:
    def test_http_error_returns_failed_run(self):
        with patch(_PATCH, _mock_client(b"", status=403)):
            obs, run = fetch(date(2023, 1, 1), date(2023, 12, 31))
        assert run.status == RunStatus.FAILED
        assert obs == []
        assert "403" in (run.error_message or "")

    def test_request_error_returns_failed_run(self):
        client = MagicMock()
        client.get.side_effect = httpx.RequestError("timeout")
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        with patch(_PATCH, MagicMock(return_value=client)):
            obs, run = fetch(date(2023, 1, 1), date(2023, 12, 31))
        assert run.status == RunStatus.FAILED
        assert obs == []
        assert "timeout" in (run.error_message or "")

    def test_bad_zip_returns_failed_run(self):
        with patch(_PATCH, _mock_client(b"this is not a zip")):
            obs, run = fetch(date(2023, 1, 1), date(2023, 12, 31))
        assert run.status == RunStatus.FAILED
        assert obs == []
