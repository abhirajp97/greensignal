"""Daily job — fetch ICE KC=F close and store as MarketObservations."""
from datetime import date

from core.utils.logging import get_logger

log = get_logger(__name__)


def run(as_of: date | None = None) -> None:
    """Fetch yesterday's ICE close and upsert into market_observations."""
    ...
