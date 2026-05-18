"""USDA Production, Supply and Distribution (PSD) — global coffee supply balance.

Phase 0 priority: implement fourth (free bulk CSV, no auth).
Download: https://apps.fas.usda.gov/psdonline/app/index.html#/app/bulkDownload
Commodity code: 0711100 (Coffee, Green). Country code: 0000 (World total).
Attribute 176 = Ending Stocks; Attribute 57 = Domestic Consumption (1000 60-kg bags).

IMPORTANT: values are retroactively revised — log each monthly release as a SourceRun
to build a vintage history of what was known at each point in time.
"""
from pathlib import Path

from core.models.observation import FeatureObservation

_COMMODITY_CODE = "0711100"
_COUNTRY_CODE = "0000"
_ENDING_STOCKS_ATTR = "176"
_CONSUMPTION_ATTR = "57"


def load_from_csv(path: Path) -> list[FeatureObservation]:
    """Parse a USDA PSD bulk CSV and return stocks-to-use observations."""
    ...


def stocks_to_use(ending_stocks: float, consumption: float) -> float:
    """Compute stocks-to-use ratio as a percentage."""
    return (ending_stocks / consumption) * 100 if consumption else 0.0
