"""Recommendation engine — converts signal inputs into a Recommendation object."""
from datetime import date

from core.models.recommendation import Action, Recommendation

# Multiplier thresholds for the action label — the formula's own natural neutral
# point (price_position=0.5, climate_risk=0 → multiplier=1.0) sits inside the
# NEUTRAL band, so these apply directly to the raw multiplier rather than a
# rolling-mean-normalized ratio (see docs/GreenSignal_Math_Reference.md §7.3).
_BUY_THRESHOLD = 1.25
_CAUTION_THRESHOLD = 0.80

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
