from decimal import Decimal
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
import uuid

from exceptions.custom_errors import (
    InsufficientDataError,
    InsufficientPositionError,
    QuantumFlowException,
    RiskGateBlockedError,
)
from repositories import (
    candle_repository,
    position_repository,
    trade_repository,
    wallet_repository,
)
from services.ml_service import detect_current_regime
from api.schemas.trading import TradeSide
from services.portfolio_service import get_total_portfolio_value
from services.feature_engineering import generate_features
from db.models.trading import Trade
from domain.pnl import (
    quantize_price,
    quantize_quantity,
    calculate_trade_value,
    calculate_realized_pnl,
)
from domain.liquidation import exceeds_position_limit


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

    # --- DEFENSE LAYER 1: IDEMPOTENCY ---
    if idempotency_key:
        existing_trade = (
            db.query(Trade).filter(Trade.idempotency_key == idempotency_key).first()
        )
        if existing_trade:
            return {
                "message": "Trade already executed.",
                "trade_id": str(existing_trade.id),
            }

    # 1. PRICING FETCH & ALGEBRAIC SOLVER
    latest_candle = candle_repository.get_latest_for_symbol(db, symbol)
    if not latest_candle:
        raise QuantumFlowException(
            message=f"No pricing data available for {symbol}", status_code=404
        )

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
    # We do the heavy lifting BEFORE locking the database rows!
    current_state = None
    if side == TradeSide.BUY:
        # Check ML Regime
        df = generate_features(symbol, db, limit=100)
        if df is None or df.empty:
            raise InsufficientDataError()

        current_state, readable_state, is_dangerous = detect_current_regime(symbol, df)
        if is_dangerous and not force_execution:
            raise RiskGateBlockedError(
                reason=f"Regime is {readable_state}.", status_code=409
            )

        # Check Portfolio Limits (Delegated to the correct service)
        estimated_portfolio = get_total_portfolio_value(user_id, db)
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

    # 2. VIRTUAL ECONOMY EXECUTION (Now incredibly fast and lightweight)
    try:
        with db.begin_nested():

            # The Lock is now held for less than a millisecond.
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
            "message": "Trade executed.",
            "trade_id": str(trade.id),
        }  # ... plus other payload info

    except OperationalError:
        db.rollback()
        raise QuantumFlowException(
            "Order processing. Please do not double-click.", status_code=409
        )
    except Exception as e:
        db.rollback()
        raise e
