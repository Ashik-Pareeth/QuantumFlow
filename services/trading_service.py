from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import status
from decimal import Decimal, ROUND_HALF_UP

from db.models import Candle, Position, Trade, TradeSide, Wallet
from services.feature_engineering import generate_features
from services.regime_detection import detect_current_regime
from exceptions.custom_errors import (
    InsufficientDataError,
    QuantumFlowException,
    RiskGateBlockedError,
    InsufficientPositionError,
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
    trade_value = qty * execution_price

    current_state = None
    if side == TradeSide.BUY:
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

        position = (
            db.query(Position)
            .filter(Position.user_id == user_id, Position.symbol == symbol)
            .with_for_update()
            .first()
        )

        realized_pnl = Decimal("0.00")

        # Decimal quantization context (matches Database Numeric(10, 4))
        FOUR_PLACES = Decimal("0.0000")
        TWO_PLACES = Decimal("0.00")

        if side == TradeSide.BUY:
            if wallet.cash_balance < trade_value:
                raise QuantumFlowException(
                    message="Insufficient funds.", status_code=400
                )

            # Fix #1: Mark-to-Market Portfolio Calculation
            all_positions = db.query(Position).filter(Position.user_id == user_id).all()

            # Fetch latest prices for all owned symbols in one bulk query
            owned_symbols = [p.symbol for p in all_positions]
            # (In production,
            #  this should ideally be an indexed TimescaleDB continuous aggregate)
            latest_prices = {
                c.symbol: c.close
                for c in db.query(Candle)
                .filter(Candle.symbol.in_(owned_symbols))
                .distinct(Candle.symbol)  # PostgreSQL specific for latest row per group
                .order_by(Candle.symbol, Candle.time.desc())
                .all()
            }

            # Use current market price if available, fallback to avg_cost if missing
            invested_value = sum(
                (p.qty * latest_prices.get(p.symbol, p.avg_price))
                for p in all_positions
            )
            estimated_portfolio = wallet.cash_balance + invested_value

            # Exposure is based on the execution price we are getting RIGHT NOW
            current_exposure = (
                (position.qty * execution_price) if position else Decimal("0.00")
            )

            if (current_exposure + trade_value) > (
                estimated_portfolio * Decimal("0.20")
            ):
                raise QuantumFlowException(
                    message="Position limit exceeded."
                    " Total exposure cannot exceed 20% of your portfolio.",
                    status_code=400,
                )

            # Deduct Cash & Upsert Position
            wallet.cash_balance -= trade_value
            if position:
                total_historical_cost = position.qty * position.avg_price
                new_total_qty = position.qty + qty
                raw_avg_price = (total_historical_cost + trade_value) / new_total_qty

                # Fix #2: Quantize to prevent Postgres DataError
                position.avg_price = raw_avg_price.quantize(
                    FOUR_PLACES, rounding=ROUND_HALF_UP
                )
                position.qty = new_total_qty.quantize(FOUR_PLACES)
            else:
                new_position = Position(
                    user_id=user_id,
                    symbol=symbol,
                    qty=qty.quantize(FOUR_PLACES),
                    avg_price=execution_price.quantize(FOUR_PLACES),
                )
                db.add(new_position)

        elif side == TradeSide.SELL:
            if not position or position.qty < qty:
                raise InsufficientPositionError(symbol=symbol)

            # Fix #3: Full-Close Precision Drift
            if position.qty == qty:
                # If closing 100%,
                # cost basis is exactly whatever historical value was left
                cost_basis = position.qty * position.avg_price
            else:
                cost_basis = qty * position.avg_price

            realized_pnl = (trade_value - cost_basis).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )

            wallet.cash_balance += trade_value
            position.qty -= qty

            if position.qty == Decimal("0.0000"):
                db.delete(position)

        # Log the Immutable Trade
        new_trade = Trade(
            user_id=user_id,
            symbol=symbol,
            side=side,
            qty=qty.quantize(FOUR_PLACES),
            price=execution_price.quantize(FOUR_PLACES),
            pnl=realized_pnl,
        )
        db.add(new_trade)

        db.commit()

        # Fix #4: Return native Decimals / Strings, let FastAPI handle serialization
        return {
            "message": f"{side.name} order executed successfully.",
            "symbol": symbol,
            "qty": str(qty),
            "execution_price": str(execution_price),
            "trade_value": str(trade_value),
            "realized_pnl": str(realized_pnl),
            "remaining_balance": str(wallet.cash_balance),
            "market_regime_id": current_state,
        }

    except Exception as e:
        db.rollback()
        raise e
