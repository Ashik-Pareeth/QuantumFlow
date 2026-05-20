import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from services.feature_engineering import generate_features


def generate_dummy_candles(num_candles: int = 50):
    """Creates a list of fake Candle objects to simulate database rows."""
    candles = []
    base_time = datetime(2026, 1, 1)

    for i in range(num_candles):
        mock_candle = MagicMock()
        mock_candle.time = base_time + timedelta(days=i)
        # Create a slight upward trend so indicators actually calculate numbers
        mock_candle.open = 100.0 + i
        mock_candle.high = 105.0 + i
        mock_candle.low = 95.0 + i
        mock_candle.close = 102.0 + i
        mock_candle.volume = 1000 + (i * 10)
        candles.append(mock_candle)

    return candles


def test_generate_features_success():
    """Tests if technical indicators are correctly applied and NaNs are dropped."""
    # 1. Arrange: Create our fake DB session and 50 days of fake data
    mock_db = MagicMock()
    fake_data = generate_dummy_candles(50)

    # We have to mock the SQLAlchemy query chain:
    #  query().filter().order_by().limit().all()
    query_mock = mock_db.query.return_value
    filtered_mock = query_mock.filter.return_value
    ordered_mock = filtered_mock.order_by.return_value
    limited_mock = ordered_mock.limit.return_value

    limited_mock.all.return_value = fake_data

    # 2. Act: Call the function with our fake DB
    df = generate_features("AAPL", mock_db, limit=50)

    # 3. Assert
    assert df is not None
    assert isinstance(df, pd.DataFrame)

    # After dropping NaNs (RSI needs 14, MACD needs 26),
    # we should have fewer than 50 rows, but more than 0
    assert 0 < len(df) < 50

    # Check that pandas-ta actually attached the new columns
    assert "rsi" in df.columns
    assert "atr" in df.columns
    # MACD generates columns like MACD_12_26_9, so we check if any column contains "MACD"
    assert any("MACD" in col for col in df.columns)

    # Mathematically prove there are no empty values crashing the ML engine
    assert df.isna().sum().sum() == 0


def test_generate_features_empty_database():
    """Tests if the function safely handles an empty database return."""
    # 1. Arrange: Fake DB that returns an empty list
    mock_db = MagicMock()
    query = MagicMock()

    mock_db.query.return_value = query

    query.filter.return_value = query
    query.order_by.return_value = query
    query.limit.return_value = query

    query.all.return_value = []

    # 2. Act
    df = generate_features("AAPL", mock_db)

    # 3. Assert
    assert df is None
