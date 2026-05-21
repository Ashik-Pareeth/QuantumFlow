import pandas as pd
import pandas_ta as ta
from sqlalchemy.orm import Session

from repositories import candle_repository


def generate_features(symbol: str, db: Session, limit: int = 500):
    print(f"Engineering features for {symbol}...")

    candles = candle_repository.get_chronological_for_symbol(db, symbol, limit)

    # 2. Convert to a Pandas DataFrame
    # We use a list comprehension to extract the data efficiently
    data = [
        {
            "time": c.time,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
        }
        for c in candles
    ]

    if not data:
        return None

    df = pd.DataFrame(data)
    df.set_index("time", inplace=True)

    # 3. Calculate Technical Indicators using pandas-ta

    # RSI (14-period default)
    df["rsi"] = ta.rsi(df["close"], length=14)

    # MACD (Returns 3 columns: MACD line, Histogram, Signal line)
    # We use append=True to add them directly to our DataFrame
    df.ta.macd(append=True)

    # ATR (14-period)
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)

    # Bollinger Bands
    df.ta.bbands(append=True)

    # 4. Clean up the data
    # The first 14+ rows will have 'NaN' (Not a Number) because you can't calculate a
    # 14-day average on day 1.
    # ML models crash if they see NaN, so we drop those rows.
    df.dropna(inplace=True)

    return df
