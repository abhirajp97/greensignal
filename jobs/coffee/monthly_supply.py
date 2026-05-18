"""Monthly job — load USDA PSD bulk CSV and store stocks-to-use observations.

Run after each WASDE release. Log a SourceRun to track vintage snapshots,
since USDA values are retroactively revised.
"""
from pathlib import Path

from core.utils.logging import get_logger

log = get_logger(__name__)


def run(csv_path: Path) -> None:
    """Parse PSD CSV, compute STU, and upsert into feature_observations."""
    ...
