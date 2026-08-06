"""Tests for recommendation_engine.py's classify_normalized() — the rolling-24m
normalization notebook 06 validated (ratio to trailing 24-month mean, then the
same BUY/CAUTION thresholds applied to that ratio)."""

from datetime import date

import pytest

from core.models.recommendation import Action
from core.services.recommendation_engine import build_recommendation, classify_normalized

_ASSET = "coffee:origin:brazil:arabica"
_DATE = date(2026, 1, 1)


class TestClassifyNormalized:
    def test_flat_trailing_history_normalizes_to_itself(self):
        normalized, action = classify_normalized(1.5, trailing_multipliers=[1.0] * 12)
        assert normalized == pytest.approx(1.5)
        assert action == Action.BUY

    def test_current_equal_to_trailing_mean_is_neutral(self):
        normalized, action = classify_normalized(1.0, trailing_multipliers=[1.0] * 24)
        assert normalized == pytest.approx(1.0)
        assert action == Action.NEUTRAL

    def test_caution_below_threshold(self):
        # trailing mean = 1.0, current = 0.7 -> normalized 0.7, below 0.80 CAUTION
        normalized, action = classify_normalized(0.7, trailing_multipliers=[1.0] * 12)
        assert normalized == pytest.approx(0.7)
        assert action == Action.CAUTION

    def test_uses_only_the_most_recent_24_of_a_longer_history(self):
        # 6 old values of 3.0 (would blow out the mean if included) + 24 recent 1.0s.
        trailing = [3.0] * 6 + [1.0] * 24
        normalized, _ = classify_normalized(1.0, trailing_multipliers=trailing)
        assert normalized == pytest.approx(1.0)

    def test_fewer_than_12_trailing_raises(self):
        with pytest.raises(ValueError, match="12"):
            classify_normalized(1.5, trailing_multipliers=[1.0] * 11)

    def test_exactly_12_trailing_does_not_raise(self):
        classify_normalized(1.5, trailing_multipliers=[1.0] * 12)  # no raise

    def test_uneven_trailing_history_matches_hand_computed_baseline(self):
        trailing = [0.8, 1.0, 1.2, 0.9, 1.1] * 3  # 15 values, mean = 1.0
        normalized, action = classify_normalized(1.3, trailing_multipliers=trailing)
        assert normalized == pytest.approx(1.3, rel=1e-6)
        assert action == Action.BUY


class TestClassifyNormalizedAgainstBuildRecommendation:
    def test_neutral_1_0_baseline_matches_raw_thresholding(self):
        """Against a genuinely neutral trailing baseline (mean=1.0), dividing by
        it is a no-op — normalized classification should match build_recommendation's
        raw-threshold classification of the same current multiplier."""
        rec = build_recommendation(_ASSET, _DATE, price_position=0.2, climate_risk_score=0.6)
        normalized, action = classify_normalized(rec.multiplier, trailing_multipliers=[1.0] * 12)
        assert action == rec.action
        assert normalized == pytest.approx(rec.multiplier)
