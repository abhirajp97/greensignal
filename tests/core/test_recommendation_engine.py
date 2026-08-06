"""Tests for recommendation_engine.py — the shared composite formula."""

from datetime import date

import pytest

from core.models.recommendation import Action
from core.services.recommendation_engine import (
    build_recommendation,
    build_recommendation_from_multiplier,
)

_ASSET = "coffee:origin:brazil:arabica"
_DATE = date(2026, 1, 1)


class TestMultiplierFormula:
    def test_neutral_point(self):
        """pos=0.5, risk=0 -> multiplier=1.0, the formula's natural neutral point."""
        rec = build_recommendation(_ASSET, _DATE, price_position=0.5, climate_risk_score=0.0)
        assert rec.multiplier == pytest.approx(1.0)

    def test_low_price_high_risk_is_strong_buy(self):
        rec = build_recommendation(_ASSET, _DATE, price_position=0.0, climate_risk_score=1.0)
        # (1.5 - 0) * (1 + 0.65) = 2.475 -> clamped to 2.3
        assert rec.multiplier == pytest.approx(2.3)
        assert rec.action == Action.BUY

    def test_high_price_low_risk_is_reduced_exposure(self):
        rec = build_recommendation(_ASSET, _DATE, price_position=1.0, climate_risk_score=0.0)
        assert rec.multiplier == pytest.approx(0.5)
        assert rec.action == Action.CAUTION

    def test_multiplier_clamped_to_range(self):
        rec = build_recommendation(_ASSET, _DATE, price_position=0.0, climate_risk_score=1.0)
        assert 0.4 <= rec.multiplier <= 2.3


class TestActionThresholds:
    def test_buy_at_or_above_threshold(self):
        rec = build_recommendation(_ASSET, _DATE, price_position=0.2, climate_risk_score=0.6)
        assert rec.multiplier >= 1.25
        assert rec.action == Action.BUY

    def test_caution_at_or_below_threshold(self):
        rec = build_recommendation(_ASSET, _DATE, price_position=0.9, climate_risk_score=0.0)
        assert rec.multiplier <= 0.80
        assert rec.action == Action.CAUTION

    def test_neutral_in_between(self):
        rec = build_recommendation(_ASSET, _DATE, price_position=0.5, climate_risk_score=0.0)
        assert rec.action == Action.NEUTRAL


class TestRecommendationShape:
    def test_carries_asset_and_date(self):
        rec = build_recommendation(_ASSET, _DATE, price_position=0.5, climate_risk_score=0.5)
        assert rec.asset_id == _ASSET
        assert rec.recommendation_date == _DATE

    def test_default_confidence(self):
        rec = build_recommendation(_ASSET, _DATE, price_position=0.5, climate_risk_score=0.5)
        assert rec.confidence == pytest.approx(0.7)

    def test_confidence_override(self):
        rec = build_recommendation(
            _ASSET, _DATE, price_position=0.5, climate_risk_score=0.5, confidence=0.3
        )
        assert rec.confidence == pytest.approx(0.3)

    def test_signal_inputs_recorded(self):
        rec = build_recommendation(_ASSET, _DATE, price_position=0.2, climate_risk_score=0.8)
        assert rec.signal_inputs == {"price_position": 0.2, "climate_risk_score": 0.8}

    def test_headline_and_rationale_are_nonempty_strings(self):
        rec = build_recommendation(_ASSET, _DATE, price_position=0.2, climate_risk_score=0.8)
        assert isinstance(rec.headline, str) and rec.headline
        assert isinstance(rec.rationale, str) and rec.rationale


class TestBuildRecommendationFromMultiplier:
    def test_classifies_using_the_same_thresholds(self):
        buy = build_recommendation_from_multiplier(
            _ASSET, _DATE, 1.3, signal_inputs={}, rationale="r"
        )
        neutral = build_recommendation_from_multiplier(
            _ASSET, _DATE, 1.0, signal_inputs={}, rationale="r"
        )
        caution = build_recommendation_from_multiplier(
            _ASSET, _DATE, 0.7, signal_inputs={}, rationale="r"
        )
        assert buy.action == Action.BUY
        assert neutral.action == Action.NEUTRAL
        assert caution.action == Action.CAUTION

    def test_clamps_to_multiplier_range(self):
        rec = build_recommendation_from_multiplier(
            _ASSET, _DATE, 5.0, signal_inputs={}, rationale="r"
        )
        assert rec.multiplier == pytest.approx(2.3)

        rec2 = build_recommendation_from_multiplier(
            _ASSET, _DATE, -1.0, signal_inputs={}, rationale="r"
        )
        assert rec2.multiplier == pytest.approx(0.4)

    def test_uses_caller_supplied_rationale_and_signal_inputs(self):
        rec = build_recommendation_from_multiplier(
            _ASSET,
            _DATE,
            1.0,
            signal_inputs={"foo": 0.5},
            rationale="custom rationale text",
        )
        assert rec.rationale == "custom rationale text"
        assert rec.signal_inputs == {"foo": 0.5}

    def test_default_confidence(self):
        rec = build_recommendation_from_multiplier(
            _ASSET, _DATE, 1.0, signal_inputs={}, rationale="r"
        )
        assert rec.confidence == pytest.approx(0.5)
