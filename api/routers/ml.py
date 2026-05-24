from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from core.rate_limiter import limiter
from db.database import get_db
from services.ml_service import generate_live_signal, train_models_for_symbol

router = APIRouter()


@router.post("/train/{symbol}")
@limiter.limit("2/minute")
def train_model(
    request: Request,
    symbol: str,
    limit: int = 1000,
    db: Session = Depends(get_db),
):
    """Trains the ensemble models and HMM regime detector."""
    return train_models_for_symbol(symbol=symbol, limit=limit, db=db)


@router.get("/predict/{symbol}")
@limiter.limit("60/minute")
def get_live_signal(
    request: Request,
    symbol: str,
    force_execution: bool = False,
    db: Session = Depends(get_db),
):
    """Generates a live trading signal."""
    return generate_live_signal(symbol=symbol, db=db, force_execution=force_execution)
