from decimal import Decimal
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import status

from db.models import Candle, Position, Trade, TradeSide, Wallet
from services.feature_engineering import generate_features
from services.regime_detection import detect_current_regime
from exceptions.custom_errors import (
    InsufficientDataError,
    QuantumFlowException,
    RiskGateBlockedError,
)


def execute_trade_order(
    user_id: UUID,
    symbol: str,
    qty: Decimal,
    side: TradeSide,
    force_execution: bool,
    db: Session,
) -> dict:
    """Core business logic for executing a trade. Independent of HTTP."""

    # 1. RISK GATE & PRICING
    latest_candle = (
        db.query(Candle)
        .filter(Candle.symbol == symbol)
        .order_by(Candle.time.desc())
        .first()
    )
    if not latest_candle:
        raise QuantumFlowException(
            message=f"No pricing data available for {symbol}", status_code=404
        )

    execution_price = latest_candle.close
    total_cost = qty * execution_price

    df = generate_features(symbol, db, limit=100)
    if df is None or df.empty:
        raise InsufficientDataError()

    current_state, readable_state, is_dangerous = detect_current_regime(symbol, df)

    if is_dangerous and not force_execution:
        raise RiskGateBlockedError(
            reason=f"Market regime is currently {readable_state}."
            " To proceed anyway, confirm the risk.",
            status_code=status.HTTP_409_CONFLICT,
        )

    # 2. VIRTUAL ECONOMY EXECUTION
    try:
        wallet = (
            db.query(Wallet).filter(Wallet.user_id == user_id).with_for_update().first()
        )
        if not wallet:
            raise QuantumFlowException(message="Wallet not found.", status_code=404)

        if side == TradeSide.BUY:
            if wallet.cash_balance < total_cost:
                raise QuantumFlowException(
                    message="Insufficient funds.", status_code=400
                )

            # 20% Position Limit
            positions = db.query(Position).filter(Position.user_id == user_id).all()
            invested_value = sum((p.qty * p.avg_price) for p in positions)
            estimated_portfolio = wallet.cash_balance + invested_value

            if total_cost > (estimated_portfolio * Decimal("0.20")):
                raise QuantumFlowException(
                    message="Position limit exceeded."
                    " Cannot invest more than 20% of portfolio in one asset.",
                    status_code=400,
                )

            # Deduct Cash & Upsert Position
            wallet.cash_balance -= total_cost
            position = (
                db.query(Position)
                .filter(Position.user_id == user_id, Position.symbol == symbol)
                .first()
            )

            if position:
                total_historical_cost = position.qty * position.avg_price
                new_total_cost = total_historical_cost + total_cost
                new_total_qty = position.qty + qty
                position.avg_price = new_total_cost / new_total_qty
                position.qty = new_total_qty
            else:
                position = Position(
                    user_id=user_id, symbol=symbol, qty=qty, avg_price=execution_price
                )
                db.add(position)

        elif side == TradeSide.SELL:
            # TODO: We will build the SELL logic and Realized PnL here next!
            pass

        # Log the Immutable Trade
        new_trade = Trade(
            user_id=user_id,
            symbol=symbol,
            side=side,
            qty=qty,
            price=execution_price,
            pnl=Decimal("0.00"),
        )
        db.add(new_trade)
        db.commit()

        return {
            "message": f"{side.name} order executed successfully.",
            "symbol": symbol,
            "qty": qty,
            "execution_price": execution_price,
            "total_cost": total_cost,
            "remaining_balance": wallet.cash_balance,
            "market_regime_id": current_state,
        }

    except Exception as e:
        db.rollback()
        raise e
