import yfinance as yf
from sqlalchemy.orm import Session

from db.models import Candle
from repositories import candle_repository


def fetch_and_store_candles(symbol: str, db: Session, period: str = "1y"):
    print(f"Fetching market data for {symbol}...")
    stock = yf.Ticker(symbol)
    df = stock.history(period=period)

    if df.empty:
        return 0

    # Strip timezone info to keep PostgreSQL timestamps clean
    df.index = df.index.tz_localize(None)

    candles = []
    # Iterate through the Pandas DataFrame and build SQLAlchemy objects
    for index, row in df.iterrows():
        candle = Candle(
            time=index,
            symbol=symbol.upper(),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=int(row["Volume"]),
        )
        candles.append(candle)

    candle_repository.replace_for_symbol(db, symbol, candles)
    db.commit()

    return len(candles)
