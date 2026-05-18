"""Scenario schema — what-if calculation inputs and outputs for margin modelling."""
from pydantic import BaseModel


class ScenarioInput(BaseModel):
    """Buyer inputs for a forward-buying margin scenario."""

    asset_id: str
    monthly_volume_kg: float
    current_price_per_lb: float
    retail_bag_price: float
    batch_size_kg: float
    months_forward: int        # how many months of supply to model


class ScenarioOutput(BaseModel):
    """Computed margin outcomes across price-change scenarios."""

    current_margin: float
    margin_at_plus_10pct: float
    margin_at_plus_20pct: float
    margin_at_plus_30pct: float
    forward_buy_saving: float   # saving vs spot if price rises as forecast
    forward_buy_cost: float     # total cost to lock in `months_forward` of supply
