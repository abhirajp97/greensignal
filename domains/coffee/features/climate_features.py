"""Climate feature engineering — ENSO lag, CHIRPS drought, COT contrarian composite."""
import pandas as pd


def enso_lagged(oni: pd.Series, lag_months: int = 24) -> pd.Series:
    """Shift ONI series by lag_months to align climate signal with price impact.

    Best predictive lag validated at 24 months (r=−0.30, p<0.001 in Phase 0).
    """
    ...


def climate_risk_score(
    stu_risk: float,
    enso_risk: float,
    brazil_drought_risk: float,
    cot_contrarian: float,
) -> float:
    """Compute the weighted climate risk score used in the composite formula.

    Weights from Phase 0 (synthetic data — revalidate on real data):
        0.38 × stu_risk
        0.24 × enso_risk
        0.22 × brazil_drought_risk
        0.16 × cot_contrarian_signal
    """
    return (
        0.38 * stu_risk
        + 0.24 * enso_risk
        + 0.22 * brazil_drought_risk
        + 0.16 * cot_contrarian
    )
