from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from services.data_service import (
    get_recent_candles,
    get_technical_features,
    ingest_market_data,
)

router = APIRouter()


@router.post("/ingest/{symbol}")
def ingest_data(symbol: str, period: str = "1y", db: Session = Depends(get_db)):
    """Fetches historical data from Yahoo Finance and saves it to TimescaleDB."""
    return ingest_market_data(symbol=symbol, period=period, db=db)


@router.get("/candles/{symbol}")
def get_candles(symbol: str, limit: int = 100, db: Session = Depends(get_db)):
    """Retrieves the most recent candles from the database."""
    return get_recent_candles(symbol=symbol, limit=limit, db=db)


@router.get("/features/{symbol}")
def get_features(symbol: str, limit: int = 500, db: Session = Depends(get_db)):
    """Retrieves raw candles and calculates technical indicators."""
    return get_technical_features(symbol=symbol, limit=limit, db=db)
