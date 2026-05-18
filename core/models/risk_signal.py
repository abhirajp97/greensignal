"""RiskSignal schema — standard structure for risk outputs across all domains."""
from datetime import date
from enum import Enum

from pydantic import BaseModel


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class RiskSignal(BaseModel):
    """A named risk flag for an asset, derived from one or more data sources."""

    asset_id: str
    signal_date: date
    risk_type: str       # e.g. "supply_tightness", "drought", "speculative_crowding"
    level: RiskLevel
    score: float         # 0.0–1.0 normalised
    rationale: str       # plain-language explanation
    source: str
