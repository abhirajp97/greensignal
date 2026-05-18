"""Coffee routes — signal, origins, forecast, risk endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/origins")
def list_origins() -> list[dict]:
    """List all tracked coffee origins."""
    ...


@router.get("/origins/{asset_id}/signal")
def get_signal(asset_id: str) -> dict:
    """Return the current Buy / Neutral / Caution signal for an origin."""
    ...


@router.get("/origins/{asset_id}/price")
def get_price(asset_id: str) -> dict:
    """Return current price and 52-week range for an origin."""
    ...


@router.get("/origins/{asset_id}/risk")
def get_risk(asset_id: str) -> dict:
    """Return active risk signals (supply, climate) for an origin."""
    ...


@router.get("/origins/{asset_id}/forecast")
def get_forecast(asset_id: str) -> dict:
    """Return the 90-day price forecast with confidence band for an origin."""
    ...
