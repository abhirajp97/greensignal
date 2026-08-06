"""Tests for risk_scorer.py — assembling RiskSignal objects from feature inputs."""

from datetime import date

import pytest

from core.models.risk_signal import RiskLevel
from domains.coffee.models.risk_scorer import score_climate_risk, score_supply_risk

_ASSET = "coffee:origin:brazil:arabica"
_DATE = date(2026, 1, 1)


class TestScoreSupplyRisk:
    def test_tight_buffer_is_critical(self):
        signal = score_supply_risk(_ASSET, _DATE, stu_pct=11.6)
        assert signal.level == RiskLevel.CRITICAL
        assert signal.score > 0.75
        assert "tight" in signal.rationale.lower() or "thin" in signal.rationale.lower()

    def test_ample_buffer_is_low(self):
        signal = score_supply_risk(_ASSET, _DATE, stu_pct=35.0)
        assert signal.level == RiskLevel.LOW
        assert signal.score == pytest.approx(0.0)

    def test_carries_asset_and_date(self):
        signal = score_supply_risk(_ASSET, _DATE, stu_pct=20.0)
        assert signal.asset_id == _ASSET
        assert signal.signal_date == _DATE
        assert signal.risk_type == "supply_tightness"

    def test_score_within_bounds(self):
        for pct in [0.0, 5.0, 20.0, 50.0, 100.0]:
            signal = score_supply_risk(_ASSET, _DATE, stu_pct=pct)
            assert 0.0 <= signal.score <= 1.0


class TestScoreClimateRisk:
    def test_averages_the_two_inputs(self):
        signal = score_climate_risk(_ASSET, _DATE, enso_risk=0.8, drought_risk=0.4)
        assert signal.score == pytest.approx(0.6)

    def test_both_high_is_critical(self):
        signal = score_climate_risk(_ASSET, _DATE, enso_risk=0.9, drought_risk=0.9)
        assert signal.level == RiskLevel.CRITICAL

    def test_both_low_is_low(self):
        signal = score_climate_risk(_ASSET, _DATE, enso_risk=0.1, drought_risk=0.1)
        assert signal.level == RiskLevel.LOW

    def test_source_is_origin_agnostic(self):
        signal = score_climate_risk(_ASSET, _DATE, enso_risk=0.5, drought_risk=0.5)
        assert "Minas Gerais" not in signal.source
        assert "Kodagu" not in signal.source

    def test_carries_asset_and_date(self):
        signal = score_climate_risk(_ASSET, _DATE, enso_risk=0.5, drought_risk=0.5)
        assert signal.asset_id == _ASSET
        assert signal.signal_date == _DATE
        assert signal.risk_type == "climate_risk"
