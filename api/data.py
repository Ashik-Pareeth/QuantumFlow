from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Candle
from services.market_data import fetch_and_store_candles
from services.feature_engineering import generate_features
from exceptions.custom_errors import QuantumFlowException

router = APIRouter()


@router.post("/ingest/{symbol}")
def ingest_data(symbol: str, period: str = "1y", db: Session = Depends(get_db)):
    """Fetches historical data from Yahoo Finance and saves it to TimescaleDB."""
    count = fetch_and_store_candles(symbol, db, period)

    if count == 0:
        raise QuantumFlowException(
            detail=f"No data found for ticker {symbol}",
            status_code=404,
        )

    return {
        "message": (f"Successfully ingested {count} candles " f"for {symbol.upper()}")
    }


@router.get("/candles/{symbol}")
def get_candles(symbol: str, limit: int = 100, db: Session = Depends(get_db)):
    """Retrieves the most recent candles from the database."""
    candles = (
        db.query(Candle)
        .filter(Candle.symbol == symbol.upper())
        .order_by(Candle.time.desc())
        .limit(limit)
        .all()
    )

    return candles


@router.get("/features/{symbol}")
def get_features(symbol: str, limit: int = 500, db: Session = Depends(get_db)):
    """Retrieves raw candles and calculates technical indicators."""
    df = generate_features(symbol, db, limit)

    if df is None or df.empty:
        raise QuantumFlowException(
            detail=f"Not enough data to calculate features for {symbol}",
            status_code=404,
        )

    result = df.reset_index().to_dict(orient="records")

    return result
