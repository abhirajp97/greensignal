"""Recommendation schema — action + confidence + rationale for a buyer."""
from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class Action(str, Enum):
    BUY = "buy"
    NEUTRAL = "neutral"
    CAUTION = "caution"


class Recommendation(BaseModel):
    """A purchasing recommendation for an asset at a point in time."""

    asset_id: str
    recommendation_date: date
    action: Action
    multiplier: float         # buying volume multiplier, e.g. 1.5 = buy 50% more
    confidence: float         # 0.0–1.0
    headline: str             # one-sentence plain-language summary for roasters
    rationale: str            # longer explanation, still jargon-free
    signal_inputs: dict[str, float] = Field(default_factory=dict)
