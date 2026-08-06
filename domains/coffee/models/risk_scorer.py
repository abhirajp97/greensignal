"""Risk scorer — assembles per-origin RiskSignal objects from feature inputs."""

from datetime import date

from core.models.risk_signal import RiskLevel, RiskSignal
from domains.coffee.sources.usda_psd import stu_risk_score

# Score-to-level thresholds — a plain quartile split of the 0-1 risk scale,
# consistent across both risk types below. Not separately calibrated per
# risk type; revisit if a specific risk_type's distribution turns out to
# cluster oddly against these bounds.
_LOW_MAX = 0.25
_MODERATE_MAX = 0.50
_HIGH_MAX = 0.75


def _level_for(score: float) -> RiskLevel:
    if score < _LOW_MAX:
        return RiskLevel.LOW
    if score < _MODERATE_MAX:
        return RiskLevel.MODERATE
    if score < _HIGH_MAX:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


def score_supply_risk(asset_id: str, signal_date: date, stu_pct: float) -> RiskSignal:
    """Build a supply-tightness RiskSignal from stocks-to-use percentage."""
    score = stu_risk_score(stu_pct)
    level = _level_for(score)

    if score >= _HIGH_MAX:
        rationale = (
            f"The world's coffee buffer is stretched thin ({stu_pct:.1f}% stocks-to-use) — "
            "historically tight"
        )
    elif score <= _LOW_MAX:
        rationale = f"The world's coffee buffer is comfortable ({stu_pct:.1f}% stocks-to-use)"
    else:
        rationale = f"The world's coffee buffer is moderately tight ({stu_pct:.1f}% stocks-to-use)"

    return RiskSignal(
        asset_id=asset_id,
        signal_date=signal_date,
        risk_type="supply_tightness",
        level=level,
        score=score,
        rationale=rationale,
        source="USDA Coffee: World Markets and Trade",
    )


def score_climate_risk(
    asset_id: str,
    signal_date: date,
    enso_risk: float,
    drought_risk: float,
) -> RiskSignal:
    """Build a climate RiskSignal from ENSO and CHIRPS drought inputs.

    Combined as a simple average — this is a display-layer RiskSignal, not
    the composite formula's `climate_risk_score` (which weights ENSO/drought/
    supply/positioning together for the multiplier); the two inputs here
    represent the same underlying "climate risk" concept from two sources,
    not signals with different real-data-validated weights.

    Origin-agnostic by design (no region name in `source` below) — CHIRPS
    extraction is per-origin (Minas Gerais for Brazil, Kodagu for India,
    etc.), and `drought_risk` is already whichever region's score the caller
    computed; this function doesn't know or need to know which one.
    """
    score = (enso_risk + drought_risk) / 2.0
    level = _level_for(score)

    dominant = (
        "El Niño conditions" if enso_risk >= drought_risk else "dry flowering-season rainfall"
    )
    if score >= _HIGH_MAX:
        rationale = (
            f"Climate risk is elevated, driven mainly by {dominant} — "
            "a threat to next year's crop"
        )
    elif score <= _LOW_MAX:
        rationale = "Climate conditions are currently easing supply risk"
    else:
        rationale = f"Climate risk is moderate, with {dominant} the larger contributor"

    return RiskSignal(
        asset_id=asset_id,
        signal_date=signal_date,
        risk_type="climate_risk",
        level=level,
        score=score,
        rationale=rationale,
        source="NOAA CPC ONI + CHIRPS regional rainfall",
    )
