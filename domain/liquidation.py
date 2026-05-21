from decimal import Decimal


def exceeds_position_limit(
    *,
    current_exposure: Decimal,
    trade_value: Decimal,
    estimated_portfolio_value: Decimal,
    max_exposure_ratio: Decimal = Decimal("0.20"),
) -> bool:
    return (current_exposure + trade_value) > (
        estimated_portfolio_value * max_exposure_ratio
    )
