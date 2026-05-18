"""SourceRun schema — ingestion job log for tracking freshness and failures."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class RunStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class SourceRun(BaseModel):
    """A single execution of a data ingestion job."""

    source_id: str           # e.g. "coffee:ice_coffee_c"
    started_at: datetime
    completed_at: datetime | None = None
    status: RunStatus
    records_fetched: int
    records_stored: int
    error_message: str | None = None
