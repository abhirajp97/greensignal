"""Tests for signal_generator.py — generate_signal() (Brazil) and generate_india_signal()."""

from datetime import date

import pytest

from core.models.recommendation import Action
from domains.coffee.models.signal_generator import (
    INDIA_V3_WEIGHTS,
    generate_india_signal,
    generate_india_signal_v3,
    generate_signal,
)

_BRAZIL_ASSET = "coffee:origin:brazil:arabica"
_INDIA_ASSET = "coffee:origin:india:arabica"
_DATE = date(2026, 1, 1)


class TestGenerateSignalBrazil:
    def test_returns_recommendation_for_neutral_inputs(self):
        rec = generate_signal(
            _BRAZIL_ASSET,
            _DATE,
            price_position=0.5,
            stu_risk=0.5,
            enso_risk=0.5,
            brazil_drought_risk=0.5,
            cot_contrarian=0.0,
        )
        assert rec.asset_id == _BRAZIL_ASSET
        assert rec.action in (Action.BUY, Action.NEUTRAL, Action.CAUTION)

    def test_low_price_high_risk_inputs_favor_buy(self):
        rec = generate_signal(
            _BRAZIL_ASSET,
            _DATE,
            price_position=0.0,
            stu_risk=1.0,
            enso_risk=1.0,
            brazil_drought_risk=1.0,
            cot_contrarian=1.0,
        )
        assert rec.action == Action.BUY


class TestGenerateIndiaSignal:
    def test_reuses_the_same_formula_shape(self):
        """generate_india_signal(pos, risk) == build_recommendation(pos, risk) directly."""
        rec = generate_india_signal(_INDIA_ASSET, _DATE, price_position=0.5, climate_risk=0.0)
        assert rec.multiplier == pytest.approx(1.0)
        assert rec.action == Action.NEUTRAL

    def test_asset_id_is_india_specific(self):
        rec = generate_india_signal(_INDIA_ASSET, _DATE, price_position=0.5, climate_risk=0.5)
        assert rec.asset_id == _INDIA_ASSET

    def test_confidence_defaults_and_overrides(self):
        default_rec = generate_india_signal(
            _INDIA_ASSET, _DATE, price_position=0.5, climate_risk=0.5
        )
        assert default_rec.confidence == pytest.approx(0.7)

        low_conf_rec = generate_india_signal(
            _INDIA_ASSET, _DATE, price_position=0.5, climate_risk=0.5, confidence=0.3
        )
        assert low_conf_rec.confidence == pytest.approx(0.3)

    def test_does_not_affect_brazil_generate_signal(self):
        """Additive change — generate_signal()'s own behavior is untouched."""
        brazil_rec = generate_signal(
            _BRAZIL_ASSET,
            _DATE,
            0.5,
            stu_risk=0.5,
            enso_risk=0.5,
            brazil_drought_risk=0.5,
            cot_contrarian=0.0,
        )
        india_rec = generate_india_signal(_INDIA_ASSET, _DATE, price_position=0.5, climate_risk=0.5)
        assert brazil_rec.asset_id != india_rec.asset_id


class TestGenerateIndiaSignalV3:
    def test_weights_sum_to_one(self):
        assert sum(INDIA_V3_WEIGHTS.values()) == pytest.approx(1.0)

    def test_neutral_point(self):
        """score=0.5 (weights sum to 1, all inputs 0.5) -> multiplier=1.0, NEUTRAL."""
        rec = generate_india_signal_v3(
            _INDIA_ASSET, _DATE, price_position=0.5, stu_stress=0.5, l3_risk=0.5
        )
        assert rec.multiplier == pytest.approx(1.0)
        assert rec.action == Action.NEUTRAL

    def test_price_position_is_momentum_not_contrarian(self):
        """Unlike generate_signal()/generate_india_signal(), HIGH price_position
        should push toward BUY here, not CAUTION — the opposite sign."""
        high_pos = generate_india_signal_v3(
            _INDIA_ASSET, _DATE, price_position=1.0, stu_stress=0.5, l3_risk=0.5
        )
        low_pos = generate_india_signal_v3(
            _INDIA_ASSET, _DATE, price_position=0.0, stu_stress=0.5, l3_risk=0.5
        )
        assert high_pos.multiplier > low_pos.multiplier

    def test_high_inputs_favor_buy(self):
        rec = generate_india_signal_v3(
            _INDIA_ASSET, _DATE, price_position=1.0, stu_stress=1.0, l3_risk=1.0
        )
        assert rec.multiplier == pytest.approx(2.0)
        assert rec.action == Action.BUY

    def test_low_inputs_favor_caution(self):
        rec = generate_india_signal_v3(
            _INDIA_ASSET, _DATE, price_position=0.0, stu_stress=0.0, l3_risk=0.0
        )
        assert rec.multiplier == pytest.approx(0.4)  # clamped from 0.0
        assert rec.action == Action.CAUTION

    def test_signal_inputs_recorded(self):
        rec = generate_india_signal_v3(
            _INDIA_ASSET, _DATE, price_position=0.2, stu_stress=0.3, l3_risk=0.8
        )
        assert rec.signal_inputs["price_position"] == pytest.approx(0.2)
        assert rec.signal_inputs["stu_stress"] == pytest.approx(0.3)
        assert rec.signal_inputs["l3_risk"] == pytest.approx(0.8)
        expected_score = 0.361 * 0.2 + 0.148 * 0.3 + 0.491 * 0.8
        assert rec.signal_inputs["india_composite_score"] == pytest.approx(expected_score)

    def test_default_confidence_is_lower_than_v2(self):
        rec = generate_india_signal_v3(
            _INDIA_ASSET, _DATE, price_position=0.5, stu_stress=0.5, l3_risk=0.5
        )
        assert rec.confidence == pytest.approx(0.4)

    def test_confidence_override(self):
        rec = generate_india_signal_v3(
            _INDIA_ASSET, _DATE, price_position=0.5, stu_stress=0.5, l3_risk=0.5, confidence=0.6
        )
        assert rec.confidence == pytest.approx(0.6)

    def test_does_not_affect_v2_or_brazil(self):
        v2_rec = generate_india_signal(_INDIA_ASSET, _DATE, price_position=0.5, climate_risk=0.0)
        brazil_rec = generate_signal(
            _BRAZIL_ASSET,
            _DATE,
            0.5,
            stu_risk=0.0,
            enso_risk=0.0,
            brazil_drought_risk=0.0,
            cot_contrarian=0.0,
        )
        v3_rec = generate_india_signal_v3(
            _INDIA_ASSET, _DATE, price_position=0.5, stu_stress=0.5, l3_risk=0.5
        )
        assert v2_rec.multiplier == pytest.approx(1.0)
        assert brazil_rec.multiplier == pytest.approx(1.0)
        assert v3_rec.multiplier == pytest.approx(1.0)
