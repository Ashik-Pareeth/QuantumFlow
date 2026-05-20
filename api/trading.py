from decimal import Decimal

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from api.schemas import BuyTradeRequest
from db.database import get_db
from db.models import (
    Candle,
    Position,
    Trade,
    TradeSide,
    Wallet,
)
from exceptions.custom_errors import (
    InsufficientDataError,
    QuantumFlowException,
    RiskGateBlockedError,
)
from services.feature_engineering import generate_features
from services.regime_detection import detect_current_regime

router = APIRouter()


@router.post("/buy")
def execute_buy(
    request: BuyTradeRequest,
    db: Session = Depends(get_db),
):
    """Executes a trade backed by the HMM Risk Gate."""

    symbol = request.symbol.upper()

    latest_candle = (
        db.query(Candle)
        .filter(Candle.symbol == symbol)
        .order_by(Candle.time.desc())
        .first()
    )

    if not latest_candle:
        raise QuantumFlowException(
            message=f"No pricing data available for {symbol}",
            status_code=404,
        )

    execution_price = latest_candle.close

    total_cost = request.qty * execution_price

    df = generate_features(symbol, db, limit=100)

    if df is None or df.empty:
        raise InsufficientDataError()

    current_state, readable_state, is_dangerous = detect_current_regime(symbol, df)

    if is_dangerous and not request.force_execution:
        raise RiskGateBlockedError(
            reason=(
                f"Market regime is currently {readable_state}. "
                "To proceed anyway, confirm the risk."
            ),
            status_code=status.HTTP_409_CONFLICT,
        )

    try:
        wallet = (
            db.query(Wallet)
            .filter(Wallet.user_id == request.user_id)
            .with_for_update()
            .first()
        )

        if not wallet:
            raise QuantumFlowException(
                message="Wallet not found.",
                status_code=404,
            )

        if wallet.cash_balance < total_cost:
            raise QuantumFlowException(
                message="Insufficient funds.",
                status_code=400,
            )

        positions = db.query(Position).filter(Position.user_id == request.user_id).all()

        invested_value = sum((p.qty * p.avg_price) for p in positions)

        estimated_portfolio_value = wallet.cash_balance + invested_value

        if total_cost > (estimated_portfolio_value * Decimal("0.20")):
            raise QuantumFlowException(
                message=(
                    "Position limit exceeded. "
                    "You cannot invest more than 20% "
                    "of your portfolio in a single asset."
                ),
                status_code=400,
            )

        wallet.cash_balance -= total_cost

        new_trade = Trade(
            user_id=request.user_id,
            symbol=symbol,
            side=TradeSide.BUY,
            qty=request.qty,
            price=execution_price,
            pnl=Decimal("0.00"),
        )

        db.add(new_trade)

        position = (
            db.query(Position)
            .filter(
                Position.user_id == request.user_id,
                Position.symbol == symbol,
            )
            .first()
        )

        if position:
            total_historical_cost = position.qty * position.avg_price

            new_total_cost = total_historical_cost + total_cost

            new_total_qty = position.qty + request.qty

            position.avg_price = new_total_cost / new_total_qty

            position.qty = new_total_qty

        else:
            position = Position(
                user_id=request.user_id,
                symbol=symbol,
                qty=request.qty,
                avg_price=execution_price,
            )

            db.add(position)

        db.commit()

        return {
            "message": "BUY order executed successfully.",
            "symbol": symbol,
            "qty": request.qty,
            "execution_price": execution_price,
            "total_cost": total_cost,
            "remaining_balance": wallet.cash_balance,
            "new_avg_price": position.avg_price,
            "market_regime_id": current_state,
        }

    except Exception as e:
        db.rollback()
        raise e
