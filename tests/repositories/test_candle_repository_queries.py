from repositories.candle_repository import get_latest_prices_by_symbols
from datetime import timedelta, datetime, timezone
from repositories.candle_repository import upsert_candles


def test_get_latest_prices_guarantees_absolute_newest_row(db_session):
    """Proves the repository subquery always fetches the maximum timestamp."""

    base_time = datetime(2026, 5, 22, 14, 0, tzinfo=timezone.utc)
    older_time = base_time - timedelta(hours=1)
    newest_time = base_time + timedelta(hours=1)

    # Insert scrambled chronological data
    records = [
        {
            "time": older_time,
            "symbol": "TSLA",
            "timeframe": "1h",
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 150,
            "volume": 1,
        },
        {
            "time": newest_time,
            "symbol": "TSLA",
            "timeframe": "1h",
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 300,
            "volume": 1,
        },  # This is the newest TSLA
        {
            "time": base_time,
            "symbol": "TSLA",
            "timeframe": "1h",
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 200,
            "volume": 1,
        },
        {
            "time": base_time,
            "symbol": "AAPL",
            "timeframe": "1h",
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 105,
            "volume": 1,
        },  # This is the newest AAPL
        {
            "time": older_time,
            "symbol": "AAPL",
            "timeframe": "1h",
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 90,
            "volume": 1,
        },
    ]
    upsert_candles(db_session, records)

    # Fetch latest
    latest_prices = get_latest_prices_by_symbols(db_session, ["AAPL", "TSLA"])

    # ASSERTIONS
    assert latest_prices["TSLA"] == 300.0, "Failed to get the newest TSLA price"
    assert latest_prices["AAPL"] == 105.0, "Failed to get the newest AAPL price"
