from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from services.ml_service import generate_live_signal, train_models_for_symbol

router = APIRouter()


@router.post("/train/{symbol}")
def train_model(symbol: str, limit: int = 1000, db: Session = Depends(get_db)):
    """Trains the ensemble models and HMM regime detector."""
    return train_models_for_symbol(symbol=symbol, limit=limit, db=db)


@router.get("/predict/{symbol}")
def get_live_signal(symbol: str, db: Session = Depends(get_db)):
    """Generates a live trading signal."""
    return generate_live_signal(symbol=symbol, db=db)
