from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from db.database import get_db
from api.schemas import TradeRequest
from services.trading_service import execute_trade_order

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
def place_trade(request: TradeRequest, db: Session = Depends(get_db)):
    """
    RESTful endpoint to place a buy or sell order.
    Business logic is fully delegated to the Service Layer.
    """
    result = execute_trade_order(
        user_id=request.user_id,
        symbol=request.symbol.upper(),
        qty=request.qty,
        side=request.side,
        force_execution=request.force_execution,
        db=db,
    )

    return result
