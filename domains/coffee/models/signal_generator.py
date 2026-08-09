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


def generate_india_signal(
    asset_id: str,
    signal_date: date,
    price_position: float,
    climate_risk: float,
    confidence: float = 0.7,
) -> Recommendation:
    """Generate a Buy / Neutral / Caution recommendation for an India origin.

    Reuses the composite formula's *shape*, not generate_signal()'s Brazil-coupled
    four-input climate_risk_score() — India has one climate input (Kodagu rainfall,
    see domains/coffee/sources/chirps_india.py), so there's nothing to weight-combine.
    `climate_risk` is that source's own drought_risk_score() output, fed straight in.

    multiplier = (1.5 - price_position) * (1.0 + 0.65 * climate_risk)
    Additive to this module — generate_signal() (Brazil) is untouched.

    `confidence` should reflect validation status (lower under "accumulating
    validation" if the notebook 09 backtest gate hasn't passed on adequate
    history yet) — see docs/india_origin_signal_plan_v2_full_build.md §6.2.
    """
    return build_recommendation(asset_id, signal_date, price_position, climate_risk, confidence)
