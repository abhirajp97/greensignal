"""Generic repository helpers — thin wrappers over Supabase table operations."""
from supabase import Client


def upsert(client: Client, table: str, rows: list[dict]) -> int:
    """Upsert rows into table and return count stored."""
    ...


def fetch_range(client: Client, table: str, start: str, end: str) -> list[dict]:
    """Fetch rows where observed_date is within [start, end] (ISO strings)."""
    ...


def latest(client: Client, table: str, asset_id: str) -> dict | None:
    """Return the most recent row for asset_id, or None."""
    ...
