"""Tests for usda_psd.py — USDA PSD world coffee stocks-to-use source."""

import io
import zipfile
from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pytest

from core.models.source_run import RunStatus
from domains.coffee.sources.usda_psd import (
    fetch,
    load_from_csv,
    stocks_to_use,
    stu_risk_score,
)

_PATCH = "domains.coffee.sources.usda_psd.httpx.Client"

# ── CSV fixture ────────────────────────────────────────────────────────────────
# Two countries, two complete marketing years, plus noise rows that must be ignored:
#  - attribute 57 (Imports) — not consumption, ignore
#  - a non-coffee commodity row — ignore
#  - MY 2022 with ending stocks but no consumption — skip silently
#
# 2020: ending = 10 + 5 = 15 ; consumption = 20 + 5 = 25 -> STU 60%
# 2021: ending =  8 + 4 = 12 ; consumption = 18 + 6 = 24 -> STU 50%

_HEADER = "Commodity_Code,Country_Code,Market_Year,Attribute_ID,Value\n"
_ROWS = (
    "711100,BR,2020,176,10\n"
    "711100,VN,2020,176,5\n"
    "711100,BR,2020,125,20\n"
    "711100,VN,2020,125,5\n"
    "711100,BR,2020,57,99\n"     # Imports — must be ignored
    "711100,BR,2021,176,8\n"
    "711100,VN,2021,176,4\n"
    "711100,BR,2021,125,18\n"
    "711100,VN,2021,125,6\n"
    "999999,BR,2020,176,1000\n"  # other commodity — must be ignored
    "711100,BR,2022,176,7\n"     # 2022 has stocks but no consumption — skip
)
_CSV = _HEADER + _ROWS


def _zip_bytes(csv_text: str, name: str = "psd_coffee.csv") -> bytes:
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
            "error", request=MagicMock(),
            response=MagicMock(status_code=status, text="error"),
        )
    client = MagicMock()
    client.get.return_value = resp
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=client)


# ── stocks_to_use ──────────────────────────────────────────────────────────────


class TestStocksToUse:
    def test_basic_ratio(self):
        assert stocks_to_use(15, 25) == pytest.approx(60.0)

    def test_zero_consumption_is_zero(self):
        assert stocks_to_use(10, 0) == 0.0


# ── stu_risk_score ─────────────────────────────────────────────────────────────


class TestStuRiskScore:
    def test_tight_buffer_is_max_risk(self):
        assert stu_risk_score(12.0) == pytest.approx(1.0)

    def test_tighter_clamped_at_one(self):
        assert stu_risk_score(5.0) == pytest.approx(1.0)

    def test_ample_buffer_is_min_risk(self):
        assert stu_risk_score(35.0) == pytest.approx(0.0)

    def test_more_ample_clamped_at_zero(self):
        assert stu_risk_score(50.0) == pytest.approx(0.0)

    def test_midpoint(self):
        assert stu_risk_score(23.5) == pytest.approx(0.5)

    def test_always_in_unit_interval(self):
        for stu in [0.0, 11.6, 20.0, 30.0, 60.0]:
            assert 0.0 <= stu_risk_score(stu) <= 1.0


# ── fetch — success path ───────────────────────────────────────────────────────


class TestFetchSuccess:
    def test_world_aggregation_and_count(self):
        with patch(_PATCH, _mock_client(_zip_bytes(_CSV))):
            obs, run = fetch(date(2010, 1, 1), date(2025, 12, 31))
        assert run.status == RunStatus.SUCCESS
        assert run.records_stored == 0
        # 2020 and 2021 complete; 2022 incomplete (no consumption) → skipped
        assert len(obs) == 2

    def test_stu_values_summed_across_countries(self):
        with patch(_PATCH, _mock_client(_zip_bytes(_CSV))):
            obs, _ = fetch(date(2010, 1, 1), date(2025, 12, 31))
        by_year = {o.observed_date.year: o.value for o in obs}
        assert by_year[2020] == pytest.approx(60.0)   # 15/25
        assert by_year[2021] == pytest.approx(50.0)    # 12/24

    def test_date_anchor_and_metadata(self):
        with patch(_PATCH, _mock_client(_zip_bytes(_CSV))):
            obs, _ = fetch(date(2010, 1, 1), date(2025, 12, 31))
        o = obs[0]
        assert o.observed_date == date(2020, 12, 31)
        assert o.feature_name == "stocks_to_use_pct"
        assert o.asset_id == "coffee:supply:world_stu"
        assert o.source == "usda:psd_coffee"

    def test_incomplete_year_skipped(self):
        with patch(_PATCH, _mock_client(_zip_bytes(_CSV))):
            obs, _ = fetch(date(2010, 1, 1), date(2025, 12, 31))
        assert 2022 not in {o.observed_date.year for o in obs}

    def test_date_range_filter(self):
        with patch(_PATCH, _mock_client(_zip_bytes(_CSV))):
            obs, _ = fetch(date(2021, 1, 1), date(2021, 12, 31))
        assert [o.observed_date.year for o in obs] == [2021]

    def test_csv_member_located_dynamically(self):
        zb = _zip_bytes(_CSV, name="psd_coffee_2026.csv")
        with patch(_PATCH, _mock_client(zb)):
            obs, run = fetch(date(2010, 1, 1), date(2025, 12, 31))
        assert run.status == RunStatus.SUCCESS
        assert len(obs) == 2


# ── load_from_csv ──────────────────────────────────────────────────────────────


class TestLoadFromCsv:
    def test_reads_local_file(self, tmp_path):
        p = tmp_path / "psd.csv"
        p.write_text(_CSV)
        obs = load_from_csv(p)
        assert len(obs) == 2
        assert {o.observed_date.year for o in obs} == {2020, 2021}

    def test_structural_error_raises(self, tmp_path):
        p = tmp_path / "bad.csv"
        p.write_text("Commodity_Code,Market_Year,Attribute_ID,Value\n711100,2020,999,5\n")
        with pytest.raises(ValueError):
            load_from_csv(p)


# ── fetch — error paths ────────────────────────────────────────────────────────


class TestFetchErrors:
    def test_http_error_returns_failed_run(self):
        with patch(_PATCH, _mock_client(b"", status=403)):
            obs, run = fetch(date(2010, 1, 1), date(2025, 12, 31))
        assert run.status == RunStatus.FAILED
        assert obs == []
        assert "403" in (run.error_message or "")

    def test_request_error_returns_failed_run(self):
        client = MagicMock()
        client.get.side_effect = httpx.RequestError("timeout")
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        with patch(_PATCH, MagicMock(return_value=client)):
            obs, run = fetch(date(2010, 1, 1), date(2025, 12, 31))
        assert run.status == RunStatus.FAILED
        assert obs == []
        assert "timeout" in (run.error_message or "")

    def test_bad_zip_returns_failed_run(self):
        with patch(_PATCH, _mock_client(b"not a zip")):
            obs, run = fetch(date(2010, 1, 1), date(2025, 12, 31))
        assert run.status == RunStatus.FAILED
        assert obs == []

    def test_missing_attribute_returns_failed_run(self):
        """A coffee file with no stocks/consumption rows is a structural failure."""
        only_imports = _HEADER + "711100,BR,2020,57,99\n"
        with patch(_PATCH, _mock_client(_zip_bytes(only_imports))):
            obs, run = fetch(date(2010, 1, 1), date(2025, 12, 31))
        assert run.status == RunStatus.FAILED
        assert obs == []
