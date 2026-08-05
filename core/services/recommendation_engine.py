"""Recommendation engine — converts signal inputs into a Recommendation object."""
from collections.abc import Sequence
from datetime import date

from core.models.recommendation import Action, Recommendation

# Multiplier thresholds for the action label — the formula's own natural neutral
# point (price_position=0.5, climate_risk=0 → multiplier=1.0) sits inside the
# NEUTRAL band, so `build_recommendation()` applies these directly to the raw
# multiplier. `classify_normalized()` below applies the *same* thresholds to a
# rolling-mean-normalized ratio instead (notebook 06's validated methodology,
# docs/GreenSignal_Math_Reference.md §7.3) — kept as a separate explicit
# function rather than folded into `build_recommendation()`, since it needs a
# trailing multiplier history that function has no way to hold (it's a pure,
# single-point-in-time call).
_BUY_THRESHOLD = 1.25
_CAUTION_THRESHOLD = 0.80

_NORMALIZATION_WINDOW = 24
_NORMALIZATION_MIN_PERIODS = 12

_MULTIPLIER_MIN = 0.4
_MULTIPLIER_MAX = 2.3


def build_recommendation(
    asset_id: str,
    recommendation_date: date,
    price_position: float,
    climate_risk_score: float,
    confidence: float = 0.7,
) -> Recommendation:
    """Apply the conditional composite formula and return a Recommendation.

    multiplier = (1.5 - price_position) * (1.0 + 0.65 * climate_risk_score)
    Output range: 0.4x (strong caution) to 2.3x (high conviction buy)

    `confidence` defaults to a generic mid-level value; callers with their own
    calibration/validation status (e.g. a backtest-gated vs. accumulating-
    validation signal) should pass their own.
    """
    raw_multiplier = (1.5 - price_position) * (1.0 + 0.65 * climate_risk_score)
    multiplier = max(_MULTIPLIER_MIN, min(_MULTIPLIER_MAX, raw_multiplier))

    if multiplier >= _BUY_THRESHOLD:
        action = Action.BUY
    elif multiplier <= _CAUTION_THRESHOLD:
        action = Action.CAUTION
    else:
        action = Action.NEUTRAL

    return Recommendation(
        asset_id=asset_id,
        recommendation_date=recommendation_date,
        action=action,
        multiplier=multiplier,
        confidence=confidence,
        headline=_headline(action, multiplier),
        rationale=_rationale(price_position, climate_risk_score),
        signal_inputs={
            "price_position": price_position,
            "climate_risk_score": climate_risk_score,
        },
    )


def classify_normalized(
    current_multiplier: float, trailing_multipliers: Sequence[float]
) -> tuple[float, Action]:
    """Classify a multiplier via notebook 06's validated rolling-24m normalization.

    `normalized = current_multiplier / mean(trailing multipliers)`, then the
    same `_BUY_THRESHOLD`/`_CAUTION_THRESHOLD` apply to that ratio instead of
    the raw multiplier — this is what raised the composite's real-data BUY
    rate from 4.9% (the old annual-refit baseline) to 20.0% and is now the
    validated primary classification method (notebook 06 §4, §12).

    `trailing_multipliers` must be the caller's own prior `raw_multiplier`
    history — up to the 24 most recent months *before* the one being
    classified, never including it (mirrors the notebook's
    `.rolling(24, min_periods=12).mean().shift(1)` — no look-ahead). Raises
    `ValueError` below 12 trailing observations, matching the notebook's own
    `min_periods=12`: there isn't enough history yet to normalize
    meaningfully, and the caller should fall back to `build_recommendation()`'s
    raw-threshold classification instead.
    """
    if len(trailing_multipliers) < _NORMALIZATION_MIN_PERIODS:
        raise ValueError(
            f"need at least {_NORMALIZATION_MIN_PERIODS} trailing multipliers to "
            f"normalize, got {len(trailing_multipliers)}"
        )

    window = list(trailing_multipliers)[-_NORMALIZATION_WINDOW:]
    baseline = sum(window) / len(window)
    normalized = current_multiplier / baseline

    if normalized >= _BUY_THRESHOLD:
        action = Action.BUY
    elif normalized <= _CAUTION_THRESHOLD:
        action = Action.CAUTION
    else:
        action = Action.NEUTRAL

    return normalized, action


def _headline(action: Action, multiplier: float) -> str:
    if action == Action.BUY:
        return f"Buy signal — consider increasing purchase volume ({multiplier:.2f}x normal)"
    if action == Action.CAUTION:
        return f"Caution signal — consider reducing purchase volume ({multiplier:.2f}x normal)"
    return f"Neutral signal — purchase at normal volume ({multiplier:.2f}x normal)"


def _rationale(price_position: float, climate_risk_score: float) -> str:
    if price_position < 0.3:
        price_note = "near the bottom of its recent price range"
    elif price_position > 0.7:
        price_note = "near the top of its recent price range"
    else:
        price_note = "in the middle of its recent price range"

    if climate_risk_score >= 0.6:
        risk_note = "elevated supply/climate risk is amplifying conviction"
    elif climate_risk_score <= 0.3:
        risk_note = "supply/climate risk is low"
    else:
        risk_note = "supply/climate risk is moderate"

    return f"Price is {price_note}, and {risk_note}."
