"""Canonical Asset schema — represents anything a buyer can procure or monitor."""
from typing import Any

from pydantic import BaseModel, Field


class Asset(BaseModel):
    """A procurable commodity origin or benchmark."""

    asset_id: str        # e.g. "coffee:origin:brazil:arabica"
    domain: str          # "coffee" | "cacao"
    asset_type: str      # "origin" | "benchmark"
    name: str
    unit: str            # "lb" | "metric_ton"
    metadata: dict[str, Any] = Field(default_factory=dict)
