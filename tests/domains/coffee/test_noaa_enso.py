"""Tests for noaa_enso.py — NOAA ONI ENSO climate signal source."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from core.models.source_run import RunStatus
from domains.coffee.sources.noaa_enso import (
    _season_to_date,
    enso_risk_score,
    fetch,
)

_PATCH = "domains.coffee.sources.noaa_enso.httpx.Client"

# ── Minimal ONI fixture ───────────────────────────────────────────────────────

_ONI_HEADER = "SEAS YR   TOTAL  ANOM\n"

# A handful of seasons covering year-boundary and normal cases
_ONI_ROWS = (
    " DJF 2023  27.10   0.12\n"   # normal season, El-Nino-neutral
    " JFM 2023  27.52   0.41\n"   # normal
    " NDJ 2023  27.80  -0.85\n"   # NDJ → date is 2024-01-31 (year boundary!)
    " DJF 2024  26.30  -1.10\n"   # La Niña
    " JJA 2024  27.00  -99.9\n"   # NOAA missing sentinel — must be skipped
    " SON 2024  26.90  -0.70\n"   # La Niña
)

_ONI_TEXT = _ONI_HEADER + _ONI_ROWS


def _mock_client(text: str, status: int = 200):
    resp = MagicMock()
    resp.text = text
    resp.raise_for_status = MagicMock()
    if status >= 400:
        import httpx
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error",
            request=MagicMock(),
            response=MagicMock(status_code=status, text="error"),
        )
    mock_client = MagicMock()
    mock_client.get.return_value = resp
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=mock_client)


# ── _season_to_date ───────────────────────────────────────────────────────────


class TestSeasonToDate:
    def test_djf_normal_year(self):
        assert _season_to_date("DJF", 1950) == date(1950, 2, 28)

    def test_djf_leap_year(self):
        assert _season_to_date("DJF", 2000) == date(2000, 2, 29)

    def test_djf_2024_is_leap(self):
        assert _season_to_date("DJF", 2024) == date(2024, 2, 29)

    def test_jfm(self):
        assert _season_to_date("JFM", 2023) == date(2023, 3, 31)

    def test_ond(self):
        assert _season_to_date("OND", 2023) == date(2023, 12, 31)

    def test_ndj_year_boundary(self):
        """NDJ 2023 ends in January 2024, not 2023."""
        assert _season_to_date("NDJ", 2023) == date(2024, 1, 31)

    def test_ndj_1999_crosses_millennium(self):
        assert _season_to_date("NDJ", 1999) == date(2000, 1, 31)

    def test_son(self):
        assert _season_to_date("SON", 2022) == date(2022, 11, 30)


# ── enso_risk_score ───────────────────────────────────────────────────────────


class TestEnsoRiskScore:
    def test_strong_el_nino_is_max_risk(self):
        # El Niño (positive ONI) is the dominant global supply-risk phase
        assert enso_risk_score(1.5) == pytest.approx(1.0)

    def test_stronger_el_nino_clamped_at_one(self):
        assert enso_risk_score(3.0) == pytest.approx(1.0)

    def test_neutral_is_half(self):
        assert enso_risk_score(0.0) == pytest.approx(0.5)

    def test_strong_la_nina_is_min_risk(self):
        # La Niña (negative ONI) is net beneficial for the dominant producers
        assert enso_risk_score(-1.5) == pytest.approx(0.0)

    def test_stronger_la_nina_clamped_at_zero(self):
        assert enso_risk_score(-3.0) == pytest.approx(0.0)

    def test_moderate_el_nino(self):
        # oni = +0.85 → 0.5 + 0.85/3 = 0.5 + 0.283 = 0.783
        expected = 0.5 + 0.85 / 3.0
        assert enso_risk_score(0.85) == pytest.approx(expected, abs=1e-6)

    def test_output_always_in_unit_interval(self):
        for oni in [-5.0, -1.0, 0.0, 1.0, 5.0]:
            score = enso_risk_score(oni)
            assert 0.0 <= score <= 1.0


# ── fetch — success path ──────────────────────────────────────────────────────


class TestFetchSuccess:
    def test_returns_correct_count(self):
        # 5 parseable rows in the fixture; JJA 2024 (sentinel -99.9) skipped
        with patch(_PATCH, _mock_client(_ONI_TEXT)):
            obs, run = fetch(date(2023, 1, 1), date(2024, 12, 31))
        assert run.status == RunStatus.SUCCESS
        assert run.records_fetched == 5
        assert run.records_stored == 0
        assert run.error_message is None
        assert len(obs) == 5

    def test_ndj_date_is_in_next_year(self):
        """NDJ 2023 must land on 2024-01-31, not 2023-01-31."""
        with patch(_PATCH, _mock_client(_ONI_TEXT)):
            obs, _ = fetch(date(2023, 1, 1), date(2024, 12, 31))
        ndj_obs = [o for o in obs if o.observed_date == date(2024, 1, 31)]
        assert len(ndj_obs) == 1
        assert ndj_obs[0].value == pytest.approx(-0.85)

    def test_missing_sentinel_skipped_silently(self):
        """JJA 2024 with ONI=-99.9 must not appear in results."""
        with patch(_PATCH, _mock_client(_ONI_TEXT)):
            obs, run = fetch(date(2023, 1, 1), date(2024, 12, 31))
        dates = [o.observed_date for o in obs]
        assert date(2024, 8, 31) not in dates  # JJA end = Aug 31
        assert run.status == RunStatus.SUCCESS  # sentinel is not a parse error

    def test_date_range_filter(self):
        """Only observations whose date falls within [start, end] are returned."""
        with patch(_PATCH, _mock_client(_ONI_TEXT)):
            obs, _ = fetch(date(2024, 1, 1), date(2024, 12, 31))
        assert all(o.observed_date >= date(2024, 1, 1) for o in obs)
        assert all(o.observed_date <= date(2024, 12, 31) for o in obs)

    def test_feature_name_and_unit(self):
        with patch(_PATCH, _mock_client(_ONI_TEXT)):
            obs, _ = fetch(date(2023, 1, 1), date(2024, 12, 31))
        for o in obs:
            assert o.feature_name == "oni_anom"
            assert o.asset_id == "climate:enso:oni"

    def test_source_tag(self):
        with patch(_PATCH, _mock_client(_ONI_TEXT)):
            obs, _ = fetch(date(2023, 1, 1), date(2024, 12, 31))
        assert all(o.source == "noaa:oni" for o in obs)

    def test_oni_values_preserved(self):
        with patch(_PATCH, _mock_client(_ONI_TEXT)):
            obs, _ = fetch(date(2023, 1, 1), date(2023, 12, 31))
        djf = next(o for o in obs if o.observed_date == date(2023, 2, 28))
        assert djf.value == pytest.approx(0.12)

    def test_header_line_not_parsed(self):
        """The SEAS/YR header row must not appear as an observation."""
        with patch(_PATCH, _mock_client(_ONI_TEXT)):
            obs, _ = fetch(date(1900, 1, 1), date(2099, 12, 31))
        # If the header were parsed it would produce a garbled entry;
        # all dates should be real calendar dates
        for o in obs:
            assert 1950 <= o.observed_date.year <= 2050


# ── fetch — error paths ───────────────────────────────────────────────────────


class TestFetchErrors:
    def test_http_error_returns_failed_run(self):
        import httpx
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403",
            request=MagicMock(),
            response=MagicMock(status_code=403, text="Forbidden"),
        )
        mock_client.get.return_value = mock_resp
        with patch(_PATCH, MagicMock(return_value=mock_client)):
            obs, run = fetch(date(2023, 1, 1), date(2024, 12, 31))
        assert run.status == RunStatus.FAILED
        assert obs == []
        assert "403" in (run.error_message or "")

    def test_request_error_returns_failed_run(self):
        import httpx
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.RequestError("timeout")
        with patch(_PATCH, MagicMock(return_value=mock_client)):
            obs, run = fetch(date(2023, 1, 1), date(2024, 12, 31))
        assert run.status == RunStatus.FAILED
        assert obs == []
        assert "timeout" in (run.error_message or "")

    def test_partial_run_on_bad_rows(self):
        """A file with some malformed rows should return PARTIAL, not FAILED."""
        bad_text = (
            "SEAS YR   TOTAL  ANOM\n"
            " DJF 2023  27.10   0.12\n"
            " JFM 2023  BADVAL  BADVAL\n"   # malformed — triggers parse error
            " MAM 2023  27.20   0.25\n"
        )
        with patch(_PATCH, _mock_client(bad_text)):
            obs, run = fetch(date(2023, 1, 1), date(2023, 12, 31))
        assert run.status == RunStatus.PARTIAL
        assert len(obs) == 2   # DJF and MAM parsed; JFM skipped
        assert run.records_fetched == 2
