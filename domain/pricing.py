from decimal import Decimal


def calculate_invested_value(positions, latest_prices: dict[str, float]) -> Decimal:
    total = Decimal("0.00")
    for position in positions:
        sym = str(position.symbol)
        price = Decimal(str(latest_prices.get(sym, float(str(position.avg_price)))))
        total += Decimal(str(position.qty)) * price
    return total

