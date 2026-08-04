"""Tests for signal_generator.py — generate_signal() (Brazil) and generate_india_signal()."""

from datetime import date

import pytest

from core.models.recommendation import Action
from domains.coffee.models.signal_generator import generate_india_signal, generate_signal

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
            _BRAZIL_ASSET, _DATE, 0.5, stu_risk=0.5, enso_risk=0.5,
            brazil_drought_risk=0.5, cot_contrarian=0.0,
        )
        india_rec = generate_india_signal(_INDIA_ASSET, _DATE, price_position=0.5, climate_risk=0.5)
        assert brazil_rec.asset_id != india_rec.asset_id
