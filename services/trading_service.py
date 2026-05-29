import uuid
from uuid import UUID
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from datetime import datetime, timezone, timedelta

from db.models import TradeSide
from domain.liquidation import exceeds_position_limit
from domain.pnl import (
    calculate_realized_pnl,
    calculate_trade_value,
    quantize_price,
    quantize_quantity,
)
from services.feature_engineering import generate_features
from services.market_data import fetch_and_store_candles
from services.regime_detection import detect_current_regime
from services.portfolio_service import get_total_portfolio_value
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
    side: TradeSide,
    force_execution: bool,
    db: Session,
    qty: Decimal = None,
    notional_value: Decimal = None,
    idempotency_key: str = None,
) -> dict:

    symbol = symbol.upper()

    # --- DEFENSE LAYER 1: IDEMPOTENCY (Clean Repository Call) ---
    if idempotency_key:
        existing_trade = trade_repository.get_by_idempotency_key(db, idempotency_key)
        if existing_trade:
            return {
                "message": "Trade already executed.",
                "trade_id": str(existing_trade.id),
                "symbol": symbol,
            }

    # 1. PRICING FETCH & ALGEBRAIC SOLVER
    latest_candle = candle_repository.get_latest_for_symbol(db, symbol)

    needs_hydration = False
    if not latest_candle:
        needs_hydration = True
    else:
        if datetime.now(timezone.utc) - latest_candle.time > timedelta(minutes=120):
            needs_hydration = True

    if needs_hydration:
        try:
            fetch_and_store_candles(symbol, db)
            latest_candle = candle_repository.get_latest_for_symbol(db, symbol)
            if not latest_candle:
                raise InsufficientDataError()
        except Exception as e:
            raise QuantumFlowException(
                f"Failed to fetch market data for {symbol}. Try again later."
            ) from e

    execution_price = Decimal(str(latest_candle.close))

    if qty is not None:
        qty = quantize_quantity(qty)
        trade_value = calculate_trade_value(qty, execution_price)
    else:
        trade_value = quantize_price(notional_value)
        qty = quantize_quantity(trade_value / execution_price)

    if qty <= Decimal("0"):
        raise QuantumFlowException("Trade amount is too small.", status_code=400)

    # --- DEFENSE LAYER 2: PRE-TRANSACTION RISK CHECKS ---
    current_state = "MANUAL_OVERRIDE" if force_execution else "ANALYSIS_UNAVAILABLE"
    if side == TradeSide.BUY:
        if not force_execution:
            try:
                # Check ML Regime Risk Gate
                df = generate_features(symbol, db, limit=100)
                if df is None and df.empty:
                    current_state, readable_state, is_dangerous = detect_current_regime(symbol, df)

                    if is_dangerous and not force_execution:
                        raise RiskGateBlockedError(
                            reason=f"Regime is {readable_state}.", status_code=409
                        )

        # Check Portfolio Limits (Delegated cleanly)
        estimated_portfolio = get_total_portfolio_value(user_id, db)

        # Read-only fetch before the lock
        current_position = position_repository.get_by_user_and_symbol(
            db, user_id, symbol
        )
        current_exposure = (
            (current_position.qty * execution_price)
            if current_position
            else Decimal("0.00")
        )

        if exceeds_position_limit(current_exposure, trade_value, estimated_portfolio):
            raise QuantumFlowException(
                "Position limit exceeded (>20% of portfolio).", status_code=400
            )

    # 2. VIRTUAL ECONOMY EXECUTION
    try:
        with db.begin_nested():

            # Pessimistic Locking
            wallet = wallet_repository.get_by_user_id(
                db, user_id, for_update=True, nowait=True
            )
            position = position_repository.get_by_user_and_symbol(
                db, user_id, symbol, for_update=True, nowait=True
            )

            realized_pnl = Decimal("0.00")

            if side == TradeSide.BUY:
                if wallet.cash_balance < trade_value:
                    raise QuantumFlowException("Insufficient funds.", status_code=400)

                wallet.cash_balance -= trade_value

                if position:
                    total_historical_cost = position.qty * position.avg_price
                    new_total_qty = position.qty + qty
                    position.avg_price = quantize_price(
                        (total_historical_cost + trade_value) / new_total_qty
                    )
                    position.qty = new_total_qty
                else:
                    position_repository.create(
                        db,
                        user_id=user_id,
                        symbol=symbol,
                        qty=qty,
                        avg_price=execution_price,
                    )

            elif side == TradeSide.SELL:
                if not position or position.qty < qty:
                    raise InsufficientPositionError(symbol=symbol)

                cost_basis = (
                    (position.qty * position.avg_price)
                    if position.qty == qty
                    else (qty * position.avg_price)
                )
                realized_pnl = calculate_realized_pnl(trade_value, cost_basis)

                wallet.cash_balance += trade_value
                position.qty -= qty

                if position.qty == Decimal("0.0000"):
                    position_repository.delete(db, position)

            # Record the physical trade
            trade = trade_repository.create(
                db,
                user_id=user_id,
                symbol=symbol,
                side=side,
                qty=qty,
                price=execution_price,
                pnl=realized_pnl,
                idempotency_key=idempotency_key or str(uuid.uuid4()),
            )

        db.commit()

        return {
            "message": f"{side.name} order executed successfully.",
            "symbol": symbol,
            "qty": str(qty),
            "execution_price": str(execution_price),
            "trade_value": str(trade_value),
            "realized_pnl": str(realized_pnl),
            "remaining_balance": str(wallet.cash_balance),
            "market_regime_id": current_state,
            "trade_id": str(trade.id),
        }

    except OperationalError:
        db.rollback()
        raise QuantumFlowException(
            "Order processing. Please do not double-click.", status_code=409
        )
    except Exception as e:
        db.rollback()
        raise e
