"""Tests for climate_features.py — the composite's WEIGHTS and climate_risk_score()."""

import pytest

from domains.coffee.features.climate_features import WEIGHTS, climate_risk_score


class TestWeights:
    def test_weights_sum_to_one(self):
        # WEIGHTS values are deliberately rounded to 3 decimals (matching the
        # notebook's reported precision) — sum is 0.999, not exactly 1.0.
        assert sum(WEIGHTS.values()) == pytest.approx(1.0, abs=0.002)

    def test_all_weights_non_negative(self):
        assert all(w >= 0 for w in WEIGHTS.values())


class TestClimateRiskScore:
    def test_all_inputs_zero_gives_zero(self):
        assert climate_risk_score(0.0, 0.0, 0.0, 0.0) == pytest.approx(0.0)

    def test_all_inputs_one_gives_one(self):
        assert climate_risk_score(1.0, 1.0, 1.0, 1.0) == pytest.approx(1.0, abs=0.002)

    def test_uses_named_weights_not_hardcoded_literals(self):
        score = climate_risk_score(
            stu_risk=0.5, enso_risk=0.3, brazil_drought_risk=0.9, cot_contrarian=0.1
        )
        expected = (
            WEIGHTS["stu_risk"] * 0.5
            + WEIGHTS["enso_risk"] * 0.3
            + WEIGHTS["brazil_drought_risk"] * 0.9
            + WEIGHTS["cot_contrarian"] * 0.1
        )
        assert score == pytest.approx(expected)

    def test_brazil_drought_risk_is_the_dominant_weight(self):
        """Real-data finding (notebook 06 §12) — L3 dominates the real-data weights,
        a reversal from Phase 0's stu_risk-heaviest split."""
        assert WEIGHTS["brazil_drought_risk"] == max(WEIGHTS.values())
