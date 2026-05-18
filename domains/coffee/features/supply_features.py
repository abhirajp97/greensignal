"""Supply feature engineering — stocks-to-use regime classification."""


# Supply regime thresholds from Phase 0 analysis (USDA PSD historical data)
_REGIME_CRITICAL = 20.0   # < 20% → avg +30% YoY price rise historically
_REGIME_TIGHT = 25.0
_REGIME_BALANCED = 30.0


def stu_risk_score(stocks_to_use_pct: float) -> float:
    """Convert stocks-to-use % to 0–1 supply risk score.

    < 20% → critical (score ~1.0), > 30% → ample (score ~0.0).
    As of 2024–25, global coffee STU is ~13% — lowest on record.
    """
    ...


def supply_regime(stocks_to_use_pct: float) -> str:
    """Return human-readable supply regime label."""
    if stocks_to_use_pct < _REGIME_CRITICAL:
        return "critical"
    if stocks_to_use_pct < _REGIME_TIGHT:
        return "tight"
    if stocks_to_use_pct < _REGIME_BALANCED:
        return "balanced"
    return "ample"
