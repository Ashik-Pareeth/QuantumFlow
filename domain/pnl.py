from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.00")
FOUR_PLACES = Decimal("0.0000")


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def quantize_quantity(value: Decimal) -> Decimal:
    return value.quantize(FOUR_PLACES)


def quantize_price(value: Decimal) -> Decimal:
    return value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def calculate_trade_value(qty: Decimal, price: Decimal) -> Decimal:
    return qty * price


def calculate_realized_pnl(trade_value: Decimal, cost_basis: Decimal) -> Decimal:
    return quantize_money(trade_value - cost_basis)


def calculate_unrealized_pnl_pct(current_price: Decimal, avg_price: Decimal) -> Decimal:
    if avg_price <= 0:
        return Decimal("0")
    return quantize_money(((current_price - avg_price) / avg_price) * 100)
