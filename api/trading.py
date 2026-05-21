from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from api.schemas import TradeRequest
from db.database import get_db
from api.deps import get_current_user
from db.models import TradeSide
from db.models.user import User
from services.trading_service import execute_trade_order

router = APIRouter()


@router.post("/buy", status_code=status.HTTP_201_CREATED)
def place_buy_order(
    request: TradeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Executes a BUY order against the user's paper wallet."""
    return execute_trade_order(
        user_id=current_user.id,
        symbol=request.symbol.upper(),
        qty=request.qty,
        side=TradeSide.BUY,
        force_execution=request.force_execution,
        db=db,
    )


@router.post("/sell", status_code=status.HTTP_201_CREATED)
def place_sell_order(request: TradeRequest, db: Session = Depends(get_db)):
    """Executes a SELL order and calculates realized PnL."""
    return execute_trade_order(
        user_id=request.user_id,
        symbol=request.symbol.upper(),
        qty=request.qty,
        side=TradeSide.SELL,
        force_execution=request.force_execution,
        db=db,
    )
