"""Recommendation engine — converts signal inputs into a Recommendation object."""
from datetime import date

from core.models.recommendation import Recommendation


def build_recommendation(
    asset_id: str,
    recommendation_date: date,
    price_position: float,
    climate_risk_score: float,
) -> Recommendation:
    """Apply the conditional composite formula and return a Recommendation.

    multiplier = (1.5 - price_position) * (1.0 + 0.65 * climate_risk_score)
    Output range: 0.4x (strong caution) to 2.3x (high conviction buy)
    """
    ...
