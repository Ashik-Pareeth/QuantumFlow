from uuid import UUID
from decimal import Decimal
from sqlalchemy.orm import Session

from domain.pnl import calculate_unrealized_pnl_pct, quantize_money
from domain.pricing import calculate_invested_value
from exceptions.custom_errors import QuantumFlowException
from repositories import (
    candle_repository,
    position_repository,
    trade_repository,
    wallet_repository,
)


def get_user_portfolio_summary(user_id: UUID, db: Session) -> dict:
    """Fetches cash balance, open positions, and calculates live portfolio value."""

    wallet = wallet_repository.get_by_user_id(db, user_id)
    if not wallet:
        raise QuantumFlowException(message="User wallet not found.", status_code=404)

    positions = position_repository.list_for_user(db, user_id)

    owned_symbols = [p.symbol for p in positions]
    latest_prices = candle_repository.get_latest_prices_by_symbols(db, owned_symbols)

    formatted_positions = []
    total_invested_value = Decimal("0.00")

    for p in positions:
        current_price = latest_prices.get(p.symbol, p.avg_price)
        current_value = p.qty * current_price
        total_invested_value += current_value

        pnl_pct = calculate_unrealized_pnl_pct(current_price, p.avg_price)

        formatted_positions.append(
            {
                "symbol": p.symbol,
                "shares": str(p.qty),
                "average_cost": str(p.avg_price),
                "current_price": str(current_price),
                "current_value": str(quantize_money(current_value)),
                "unrealized_pnl_pct": str(pnl_pct),
            }
        )

    total_portfolio_value = wallet.cash_balance + total_invested_value

    return {
        "cash_balance": str(wallet.cash_balance),
        "total_portfolio_value": str(quantize_money(total_portfolio_value)),
        "open_positions": formatted_positions,
    }


def get_user_trade_history(user_id: UUID, limit: int, db: Session) -> list[dict]:
    """Fetches the immutable ledger of trades for the user."""

    trades = trade_repository.list_for_user(db, user_id, limit)

    return [
        {
            "trade_id": str(t.id),
            "symbol": t.symbol,
            "side": t.side.name,
            "qty": str(t.qty),
            "execution_price": str(t.price),
            "realized_pnl": str(t.pnl),
            "timestamp": t.created_at.isoformat(),
        }
        for t in trades
    ]


def get_total_portfolio_value(user_id: UUID, db: Session) -> Decimal:
    """Calculates the real-time USD value of a user's entire portfolio."""

    # 1. Get raw cash
    wallet = wallet_repository.get_by_user_id(db, user_id)
    if not wallet:
        raise QuantumFlowException("Wallet not found", status_code=404)

    # 2. Get active positions
    positions = position_repository.list_for_user(db, user_id)
    if not positions:
        return wallet.cash_balance

    # 3. Fetch latest market prices in a single optimized query
    owned_symbols = [p.symbol for p in positions]
    latest_prices = candle_repository.get_latest_prices_by_symbols(db, owned_symbols)

    # 4. Calculate total invested value
    invested_value = calculate_invested_value(positions, latest_prices)

    return wallet.cash_balance + invested_value
