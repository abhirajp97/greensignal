"""Composite signal generator — the core Phase 0 formula implemented end-to-end."""
from datetime import date

from core.models.recommendation import Recommendation
from core.services.recommendation_engine import build_recommendation
from domains.coffee.features.climate_features import climate_risk_score


def generate_signal(
    asset_id: str,
    signal_date: date,
    price_position: float,
    stu_risk: float,
    enso_risk: float,
    brazil_drought_risk: float,
    cot_contrarian: float,
) -> Recommendation:
    """Generate a Buy / Neutral / Caution recommendation using the composite formula.

    multiplier = (1.5 - price_position) * (1.0 + 0.65 * climate_risk_score)
    Range: 0.4x (strong caution) → 2.3x (high conviction buy)
    """
    c_risk = climate_risk_score(stu_risk, enso_risk, brazil_drought_risk, cot_contrarian)
    return build_recommendation(asset_id, signal_date, price_position, c_risk)
