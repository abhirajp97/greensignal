"""Climate feature engineering — ENSO lag, CHIRPS drought, COT contrarian composite."""
import pandas as pd


def enso_lagged(oni: pd.Series, lag_months: int = 24) -> pd.Series:
    """Shift ONI series by lag_months to align climate signal with price impact.

    Best predictive lag validated at 24 months (r=−0.30, p<0.001 in Phase 0).
    """
    ...


WEIGHTS = {
    "stu_risk": 0.201,
    "enso_risk": 0.142,
    "brazil_drought_risk": 0.625,
    "cot_contrarian": 0.031,
}
"""Real-data r-proportional weights (notebook 06 §12), superseding the Phase 0
fixed split (0.38/0.24/0.22/0.16). Derived on the true-vintage L2a frame
(notebook 04 §16, notebook 06 §11) after that rebuild showed the Phase-0
stu_risk weight was too high relative to its own real-data |r| against
forward returns — L3 (brazil_drought_risk) is the strongest real contributor
by a wide margin. Walk-forward cost improvement with these weights: +4.45%
(2017-2024, PASS vs the 3.0% gate). Exposed as a named constant, not just
inline literals, so downstream callers that need to explain/decompose the
score read the actual formula weights from one place."""


def climate_risk_score(
    stu_risk: float,
    enso_risk: float,
    brazil_drought_risk: float,
    cot_contrarian: float,
) -> float:
    """Compute the weighted climate risk score used in the composite formula."""
    return (
        WEIGHTS["stu_risk"] * stu_risk
        + WEIGHTS["enso_risk"] * enso_risk
        + WEIGHTS["brazil_drought_risk"] * brazil_drought_risk
        + WEIGHTS["cot_contrarian"] * cot_contrarian
    )
