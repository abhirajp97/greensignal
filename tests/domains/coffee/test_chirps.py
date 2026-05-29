"""Tests for chirps.py — CHIRPS rainfall source (Minas Gerais via GEE)."""

from datetime import date
from unittest.mock import patch

import ee
import pytest

from core.models.source_run import RunStatus
from domains.coffee.sources.chirps import (
    _month_end,
    drought_risk_score,
    fetch,
    is_flowering_month,
    load_from_netcdf,
)

_QUERY = "domains.coffee.sources.chirps._query_monthly_precip"

# month_start, area-mean precip mm (None = no coverage, must be skipped)
_ROWS = [
    (date(2020, 1, 1), 250.0),
    (date(2020, 2, 1), 180.0),
    (date(2020, 3, 1), None),
    (date(2020, 4, 1), 90.0),
]


# ── drought_risk_score ─────────────────────────────────────────────────────────


class TestDroughtRiskScore:
    def test_normal_rain_is_zero_risk(self):
        assert drought_risk_score(0.0, True) == pytest.approx(0.0)

    def test_above_normal_is_zero_risk(self):
        assert drought_risk_score(40.0, True) == pytest.approx(0.0)

    def test_full_deficit_flowering_is_max(self):
        assert drought_risk_score(-60.0, True) == pytest.approx(1.0)

    def test_severe_deficit_clamped(self):
        assert drought_risk_score(-120.0, True) == pytest.approx(1.0)

    def test_half_deficit_flowering(self):
        assert drought_risk_score(-30.0, True) == pytest.approx(0.5)

    def test_off_season_halved(self):
        assert drought_risk_score(-60.0, False) == pytest.approx(0.5)
        assert drought_risk_score(-30.0, False) == pytest.approx(0.25)

    def test_always_in_unit_interval(self):
        for anom in [-200, -60, -10, 0, 50, 300]:
            for flowering in (True, False):
                assert 0.0 <= drought_risk_score(anom, flowering) <= 1.0


class TestFloweringMonth:
    def test_flowering_months(self):
        assert all(is_flowering_month(m) for m in (9, 10, 11))

    def test_non_flowering_months(self):
        assert not any(is_flowering_month(m) for m in (1, 5, 8, 12))


# ── _month_end ─────────────────────────────────────────────────────────────────


class TestMonthEnd:
    def test_january(self):
        assert _month_end(date(2020, 1, 1)) == date(2020, 1, 31)

    def test_february_leap(self):
        assert _month_end(date(2020, 2, 10)) == date(2020, 2, 29)

    def test_february_non_leap(self):
        assert _month_end(date(2021, 2, 1)) == date(2021, 2, 28)


# ── fetch — success path ───────────────────────────────────────────────────────


class TestFetchSuccess:
    def test_count_and_status(self):
        with patch(_QUERY, return_value=_ROWS):
            obs, run = fetch(date(2020, 1, 1), date(2020, 12, 31))
        assert run.status == RunStatus.SUCCESS
        assert run.records_stored == 0
        assert run.error_message is None
        # 4 rows, March is None → skipped → 3 observations
        assert len(obs) == 3
        assert run.records_fetched == 3

    def test_month_end_anchoring(self):
        with patch(_QUERY, return_value=_ROWS):
            obs, _ = fetch(date(2020, 1, 1), date(2020, 12, 31))
        dates = [o.observed_date for o in obs]
        assert date(2020, 1, 31) in dates
        assert date(2020, 2, 29) in dates  # leap year
        assert date(2020, 4, 30) in dates

    def test_none_month_skipped(self):
        with patch(_QUERY, return_value=_ROWS):
            obs, _ = fetch(date(2020, 1, 1), date(2020, 12, 31))
        assert date(2020, 3, 31) not in {o.observed_date for o in obs}

    def test_values_and_metadata(self):
        with patch(_QUERY, return_value=_ROWS):
            obs, _ = fetch(date(2020, 1, 1), date(2020, 12, 31))
        jan = next(o for o in obs if o.observed_date == date(2020, 1, 31))
        assert jan.value == pytest.approx(250.0)
        for o in obs:
            assert o.feature_name == "precip_mm"
            assert o.asset_id == "climate:chirps:minas_gerais"
            assert o.source == "gee:chirps_pentad"

    def test_date_range_filter(self):
        with patch(_QUERY, return_value=_ROWS):
            obs, _ = fetch(date(2020, 2, 1), date(2020, 2, 29))
        assert [o.observed_date for o in obs] == [date(2020, 2, 29)]

    def test_observations_sorted(self):
        shuffled = [_ROWS[3], _ROWS[0], _ROWS[1]]
        with patch(_QUERY, return_value=shuffled):
            obs, _ = fetch(date(2020, 1, 1), date(2020, 12, 31))
        dates = [o.observed_date for o in obs]
        assert dates == sorted(dates)


# ── fetch — error path ─────────────────────────────────────────────────────────


class TestFetchErrors:
    def test_ee_exception_returns_failed_run(self):
        with patch(_QUERY, side_effect=ee.EEException("not initialized")):
            obs, run = fetch(date(2020, 1, 1), date(2020, 12, 31))
        assert run.status == RunStatus.FAILED
        assert obs == []
        assert "Earth Engine" in (run.error_message or "")


# ── load_from_netcdf fallback ──────────────────────────────────────────────────


class TestLoadFromNetcdf:
    def test_raises_clear_error_without_xarray(self):
        """xarray is not a hard dependency — the fallback must fail loudly."""
        import importlib.util

        if importlib.util.find_spec("xarray") is not None:
            pytest.skip("xarray installed — ImportError guard not exercised")
        with pytest.raises(ImportError, match="xarray"):
            load_from_netcdf("/tmp/does_not_matter.nc")
