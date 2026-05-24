from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from core.rate_limiter import limiter
from db.database import get_db
from services.portfolio_service import (
    get_user_portfolio_summary,
    get_user_trade_history,
)

router = APIRouter()


@router.get("/")
@limiter.limit("120/minute")
def get_portfolio(
    request: Request,
    user_id: UUID = Query(..., description="Temporary auth bypass for Phase 4"),
    db: Session = Depends(get_db),
):
    """Retrieves the user's cash balance, net worth, and open positions."""
    return get_user_portfolio_summary(user_id=user_id, db=db)


@router.get("/history")
@limiter.limit("60/minute")
def get_trade_history(
    request: Request,
    user_id: UUID = Query(..., description="Temporary auth bypass for Phase 4"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Retrieves the user's historical trade ledger and realized PnL."""
    return get_user_trade_history(user_id=user_id, limit=limit, db=db)
