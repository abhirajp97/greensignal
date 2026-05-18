"""Risk scorer — assembles per-origin RiskSignal objects from feature inputs."""
from datetime import date

from core.models.risk_signal import RiskSignal


def score_supply_risk(asset_id: str, signal_date: date, stu_pct: float) -> RiskSignal:
    """Build a supply-tightness RiskSignal from stocks-to-use percentage."""
    ...


def score_climate_risk(
    asset_id: str,
    signal_date: date,
    enso_risk: float,
    drought_risk: float,
) -> RiskSignal:
    """Build a climate RiskSignal from ENSO and CHIRPS drought inputs."""
    ...
