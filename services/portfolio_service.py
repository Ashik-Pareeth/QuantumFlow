from uuid import UUID
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import desc

from db.models import Wallet, Position, Trade, Candle
from exceptions.custom_errors import QuantumFlowException


def get_user_portfolio_summary(user_id: UUID, db: Session) -> dict:
    """Fetches cash balance, open positions, and calculates live portfolio value."""

    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    if not wallet:
        raise QuantumFlowException(message="User wallet not found.", status_code=404)

    positions = db.query(Position).filter(Position.user_id == user_id).all()

    # 1. Fetch latest prices for Mark-to-Market calculation
    owned_symbols = [p.symbol for p in positions]
    latest_prices = {}

    if owned_symbols:
        latest_candles = (
            db.query(Candle)
            .filter(Candle.symbol.in_(owned_symbols))
            .distinct(Candle.symbol)
            .order_by(Candle.symbol, Candle.time.desc())
            .all()
        )
        latest_prices = {c.symbol: c.close for c in latest_candles}

    # 2. Format positions and calculate total invested value
    formatted_positions = []
    total_invested_value = Decimal("0.00")

    for p in positions:
        current_price = latest_prices.get(p.symbol, p.avg_price)
        current_value = p.qty * current_price
        total_invested_value += current_value

        # Calculate unrealized PnL percentage for the frontend UI
        pnl_pct = (
            ((current_price - p.avg_price) / p.avg_price) * 100
            if p.avg_price > 0
            else Decimal("0")
        )

        formatted_positions.append(
            {
                "symbol": p.symbol,
                "shares": str(p.qty),
                "average_cost": str(p.avg_price),
                "current_price": str(current_price),
                "current_value": str(current_value.quantize(Decimal("0.00"))),
                "unrealized_pnl_pct": str(pnl_pct.quantize(Decimal("0.00"))),
            }
        )

    total_portfolio_value = wallet.cash_balance + total_invested_value

    return {
        "cash_balance": str(wallet.cash_balance),
        "total_portfolio_value": str(total_portfolio_value.quantize(Decimal("0.00"))),
        "open_positions": formatted_positions,
    }


def get_user_trade_history(user_id: UUID, limit: int, db: Session) -> list[dict]:
    """Fetches the immutable ledger of trades for the user."""

    trades = (
        db.query(Trade)
        .filter(Trade.user_id == user_id)
        .order_by(desc(Trade.created_at))
        .limit(limit)
        .all()
    )

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
