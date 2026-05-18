"""Monthly job — fetch ENSO ONI, COT positions, and CHIRPS rainfall.

ENSO and COT: fetch from remote URLs (no auth beyond CFTC annual CSVs).
CHIRPS: requires GEE approval — skipped until earthengine-api is configured.
"""
from datetime import date

from core.utils.logging import get_logger

log = get_logger(__name__)


def run(as_of: date | None = None) -> None:
    """Fetch and store ENSO ONI and COT observations for the current month."""
    ...
