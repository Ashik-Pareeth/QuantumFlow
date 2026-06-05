from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from api.dependencies import get_current_active_user
from api.schemas.trading import LegacyTradeRequest, SellTradeRequest, TradeRequest
from core.rate_limiter import limiter
from db.database import get_db
from db.models import TradeSide
from db.models.user import User
from services.trading_service import execute_trade_order

router = APIRouter()


@router.post("/buy", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def place_buy_order(
    request: Request,
    payload: TradeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Executes a BUY order against the user's paper wallet."""
    return execute_trade_order(
        user_id=UUID(str(current_user.id)),
        symbol=payload.symbol.upper(),
        qty=payload.qty,
        side=TradeSide.BUY,
        force_execution=payload.force_execution,
        db=db,
    )


@router.post("/sell", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def place_sell_order(
    request: Request,
    payload: SellTradeRequest,
    db: Session = Depends(get_db),
):
    """Executes a SELL order and calculates realized PnL."""
    return execute_trade_order(
        user_id=payload.user_id,
        symbol=payload.symbol.upper(),
        qty=payload.qty,
        side=TradeSide.SELL,
        force_execution=payload.force_execution,
        db=db,
    )


@router.post("/", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def place_legacy_order(
    request: Request,
    payload: LegacyTradeRequest,
    db: Session = Depends(get_db),
):
    """Compatibility endpoint for the original single-order route."""
    return execute_trade_order(
        user_id=payload.user_id,
        symbol=payload.symbol.upper(),
        qty=payload.qty,
        side=payload.side,
        force_execution=payload.force_execution,
        db=db,
    )
