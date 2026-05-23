import yfinance as yf
from sqlalchemy.orm import Session

from db.models import Candle
from repositories import candle_repository


def fetch_and_store_candles(
    symbol: str, db: Session, period: str = "1y", interval: str = "1d"
):
    print(f"Fetching market data for {symbol}...")
    stock = yf.Ticker(symbol)
    df = stock.history(period=period, interval=interval)

    if df.empty:
        return 0

    # Standardize Timezone (The fix we just applied)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    # Drop duplicate timestamps, keeping the most recent data
    df = df[~df.index.duplicated(keep="last")]

    records = []
    for index, row in df.iterrows():
        records.append(
            {
                "time": index,
                "symbol": symbol.upper(),
                "timeframe": interval,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]),
            }
        )

        candle_repository.upsert_candles(db, records)

        return len(records)
