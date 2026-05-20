from sqlalchemy.orm import Session

from db.models import Candle
from exceptions.custom_errors import QuantumFlowException
from services.feature_engineering import generate_features
from services.market_data import fetch_and_store_candles


def ingest_market_data(symbol: str, period: str, db: Session) -> dict:
    """Fetch historical market data and persist it."""
    count = fetch_and_store_candles(symbol, db, period)

    if count == 0:
        raise QuantumFlowException(
            message=f"No data found for ticker {symbol}",
            status_code=404,
        )

    return {
        "message": f"Successfully ingested {count} candles for {symbol.upper()}"
    }


def get_recent_candles(symbol: str, limit: int, db: Session) -> list[Candle]:
    """Retrieve the most recent candles for a symbol."""
    return (
        db.query(Candle)
        .filter(Candle.symbol == symbol.upper())
        .order_by(Candle.time.desc())
        .limit(limit)
        .all()
    )


def get_technical_features(symbol: str, limit: int, db: Session) -> list[dict]:
    """Generate technical indicators and serialize them for the API."""
    df = generate_features(symbol, db, limit)

    if df is None or df.empty:
        raise QuantumFlowException(
            message=f"Not enough data to calculate features for {symbol}",
            status_code=404,
        )

    return df.reset_index().to_dict(orient="records")
