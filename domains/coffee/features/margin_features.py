"""Margin feature engineering — roaster margin calculator and forward-buying scenarios."""


def roaster_margin(
    retail_bag_price: float,
    green_cost_per_lb: float,
    yield_ratio: float = 0.85,
    batch_size_kg: float = 1.0,
) -> float:
    """Compute gross margin per kg of roasted coffee sold.

    yield_ratio: roasted weight / green weight (default 0.85 = 15% roast loss).
    """
    ...


def forward_buy_saving(
    monthly_volume_kg: float,
    current_price_per_lb: float,
    forecast_price_per_lb: float,
    months_forward: int,
) -> float:
    """Estimate saving from buying `months_forward` of supply at current vs forecast price."""
    ...
