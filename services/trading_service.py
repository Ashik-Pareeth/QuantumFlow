from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import status
from decimal import Decimal

from db.models import TradeSide
from domain.liquidation import exceeds_position_limit
from domain.pnl import (
    FOUR_PLACES,
    calculate_realized_pnl,
    calculate_trade_value,
    quantize_price,
    quantize_quantity,
)
from domain.pricing import calculate_invested_value
from services.feature_engineering import generate_features
from services.regime_detection import detect_current_regime
from exceptions.custom_errors import (
    InsufficientDataError,
    QuantumFlowException,
    RiskGateBlockedError,
    InsufficientPositionError,
)
from repositories import (
    candle_repository,
    position_repository,
    trade_repository,
    wallet_repository,
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
    latest_candle = candle_repository.get_latest_for_symbol(db, symbol)
    if not latest_candle:
        raise QuantumFlowException(
            message=f"No pricing data available for {symbol}", status_code=404
        )

    execution_price = latest_candle.close
    trade_value = calculate_trade_value(qty, execution_price)

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
        wallet = wallet_repository.get_by_user_id(db, user_id, for_update=True)
        if not wallet:
            raise QuantumFlowException(message="Wallet not found.", status_code=404)

        position = position_repository.get_by_user_and_symbol(
            db, user_id, symbol, for_update=True
        )

        realized_pnl = Decimal("0.00")

        if side == TradeSide.BUY:
            if wallet.cash_balance < trade_value:
                raise QuantumFlowException(
                    message="Insufficient funds.", status_code=400
                )

            all_positions = position_repository.list_for_user(db, user_id)

            owned_symbols = [p.symbol for p in all_positions]
            latest_prices = candle_repository.get_latest_prices_by_symbols(
                db, owned_symbols
            )

            invested_value = calculate_invested_value(all_positions, latest_prices)
            estimated_portfolio = wallet.cash_balance + invested_value

            current_exposure = (
                (position.qty * execution_price) if position else Decimal("0.00")
            )

            if exceeds_position_limit(
                current_exposure=current_exposure,
                trade_value=trade_value,
                estimated_portfolio_value=estimated_portfolio,
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

                position.avg_price = quantize_price(raw_avg_price)
                position.qty = quantize_quantity(new_total_qty)
            else:
                position_repository.create(
                    db,
                    user_id=user_id,
                    symbol=symbol,
                    qty=quantize_quantity(qty),
                    avg_price=quantize_price(execution_price),
                )

        elif side == TradeSide.SELL:
            if not position or position.qty < qty:
                raise InsufficientPositionError(symbol=symbol)

            if position.qty == qty:
                cost_basis = position.qty * position.avg_price
            else:
                cost_basis = qty * position.avg_price

            realized_pnl = calculate_realized_pnl(trade_value, cost_basis)

            wallet.cash_balance += trade_value
            position.qty -= qty

            if position.qty == Decimal("0.0000"):
                position_repository.delete(db, position)

        trade_repository.create(
            db,
            user_id=user_id,
            symbol=symbol,
            side=side,
            qty=qty.quantize(FOUR_PLACES),
            price=quantize_price(execution_price),
            pnl=realized_pnl,
        )

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
