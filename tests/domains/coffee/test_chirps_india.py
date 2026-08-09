"""Tests for chirps_india.py — CHIRPS rainfall source (Kodagu via GEE)."""

from datetime import date
from unittest.mock import patch

import ee
import pytest

from core.models.source_run import RunStatus
from domains.coffee.sources.chirps_india import (
    _NO_DATA_SENTINEL,
    _month_end,
    _precip_or_none,
    drought_risk_score,
    fetch,
    is_flowering_month,
    load_from_netcdf,
)

_QUERY = "domains.coffee.sources.chirps_india._query_monthly_precip"

# month_start, area-mean precip mm (None = no coverage, must be skipped)
_ROWS = [
    (date(2020, 1, 1), 20.0),
    (date(2020, 2, 1), 150.0),
    (date(2020, 3, 1), None),
    (date(2020, 6, 1), 700.0),
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
    def test_robusta_flowering_months(self):
        """Robusta blossom-shower window is late Feb-mid Mar, not Brazil's Sep-Nov."""
        assert all(is_flowering_month(m, "robusta") for m in (2, 3))

    def test_robusta_non_flowering_months(self):
        assert not any(
            is_flowering_month(m, "robusta") for m in (1, 4, 5, 8, 9, 10, 11, 12)
        )

    def test_arabica_flowering_months(self):
        """Arabica needs rain by mid-April, ~1-2 months later than Robusta."""
        assert all(is_flowering_month(m, "arabica") for m in (4, 5))

    def test_arabica_non_flowering_months(self):
        assert not any(
            is_flowering_month(m, "arabica") for m in (1, 2, 3, 8, 9, 10, 11, 12)
        )

    def test_species_windows_differ(self):
        """The whole point of the split — Robusta and Arabica must not share a window."""
        assert is_flowering_month(3, "robusta") and not is_flowering_month(3, "arabica")
        assert is_flowering_month(5, "arabica") and not is_flowering_month(5, "robusta")

    def test_unknown_species_raises(self):
        with pytest.raises(KeyError):
            is_flowering_month(3, "liberica")


# ── _month_end ─────────────────────────────────────────────────────────────────


class TestMonthEnd:
    def test_january(self):
        assert _month_end(date(2020, 1, 1)) == date(2020, 1, 31)

    def test_february_leap(self):
        assert _month_end(date(2020, 2, 10)) == date(2020, 2, 29)

    def test_february_non_leap(self):
        assert _month_end(date(2021, 2, 1)) == date(2021, 2, 28)


# ── _precip_or_none ────────────────────────────────────────────────────────────
# GEE's Dictionary.get(key, default) still raises if default is None ("unless it
# is null"), so a real sentinel is used to flag months with no CHIRPS coverage yet
# (e.g. not-yet-published months when fetching up to today) — found live while
# building the India origin backtest (fetch(..., date.today()) errored where a
# fixed 2010-2024 backtest window like chirps.py's Brazil one never triggered it).


class TestPrecipOrNone:
    def test_real_value_passes_through(self):
        assert _precip_or_none(250.0) == pytest.approx(250.0)

    def test_none_stays_none(self):
        assert _precip_or_none(None) is None

    def test_sentinel_becomes_none(self):
        assert _precip_or_none(_NO_DATA_SENTINEL) is None

    def test_zero_is_not_treated_as_sentinel(self):
        """A real dry month (0mm) must not be mistaken for missing coverage."""
        assert _precip_or_none(0.0) == pytest.approx(0.0)


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
        assert date(2020, 6, 30) in dates

    def test_none_month_skipped(self):
        with patch(_QUERY, return_value=_ROWS):
            obs, _ = fetch(date(2020, 1, 1), date(2020, 12, 31))
        assert date(2020, 3, 31) not in {o.observed_date for o in obs}

    def test_values_and_metadata(self):
        with patch(_QUERY, return_value=_ROWS):
            obs, _ = fetch(date(2020, 1, 1), date(2020, 12, 31))
        jun = next(o for o in obs if o.observed_date == date(2020, 6, 30))
        assert jun.value == pytest.approx(700.0)  # SW monsoon month — high rainfall
        for o in obs:
            assert o.feature_name == "precip_mm"
            assert o.asset_id == "climate:chirps:kodagu"
            assert o.source == "gee:chirps_pentad_india"

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

    def test_unknown_district_returns_failed_run(self):
        obs, run = fetch(date(2020, 1, 1), date(2020, 12, 31), district="Not A Real District")
        assert run.status == RunStatus.FAILED
        assert obs == []
        assert "Not A Real District" in (run.error_message or "")


# ── fetch — multi-district ────────────────────────────────────────────────────


class TestFetchMultiDistrict:
    def test_defaults_to_kodagu(self):
        with patch(_QUERY, return_value=_ROWS) as mock_query:
            obs, _ = fetch(date(2020, 1, 1), date(2020, 12, 31))
        mock_query.assert_called_once_with(date(2020, 1, 1), date(2020, 12, 31), "Kodagu")
        assert all(o.asset_id == "climate:chirps:kodagu" for o in obs)

    def test_chikmagalur_uses_its_own_asset(self):
        with patch(_QUERY, return_value=_ROWS) as mock_query:
            obs, run = fetch(date(2020, 1, 1), date(2020, 12, 31), district="Chikmagalur")
        mock_query.assert_called_once_with(date(2020, 1, 1), date(2020, 12, 31), "Chikmagalur")
        assert run.status == RunStatus.SUCCESS
        assert all(o.asset_id == "climate:chirps:chikmagalur" for o in obs)

    def test_hassan_uses_its_own_asset(self):
        with patch(_QUERY, return_value=_ROWS):
            obs, run = fetch(date(2020, 1, 1), date(2020, 12, 31), district="Hassan")
        assert run.status == RunStatus.SUCCESS
        assert all(o.asset_id == "climate:chirps:hassan" for o in obs)


# ── load_from_netcdf fallback ──────────────────────────────────────────────────


class TestLoadFromNetcdf:
    def test_raises_clear_error_without_xarray(self):
        """xarray is not a hard dependency — the fallback must fail loudly."""
        import importlib.util

        if importlib.util.find_spec("xarray") is not None:
            pytest.skip("xarray installed — ImportError guard not exercised")
        with pytest.raises(ImportError, match="xarray"):
            load_from_netcdf("/tmp/does_not_matter.nc")

    def test_unknown_district_raises_before_touching_xarray(self):
        with pytest.raises(ValueError, match="Not A Real District"):
            load_from_netcdf("/tmp/does_not_matter.nc", district="Not A Real District")
