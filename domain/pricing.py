from decimal import Decimal


def calculate_invested_value(positions, latest_prices: dict[str, Decimal]) -> Decimal:
    return sum(
        (position.qty * latest_prices.get(position.symbol, position.avg_price))
        for position in positions
    )
