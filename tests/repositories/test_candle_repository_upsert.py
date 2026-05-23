from repositories.candle_repository import upsert_candles
from db.models.market import Candle
from datetime import datetime, timezone


def test_repository_upsert_isolates_timeframes_and_prevents_crashes(db_session):
    """Proves the DB allows multiple timeframes but rejects exact duplicates silently."""

    base_time = datetime(2026, 5, 22, 14, 0, tzinfo=timezone.utc)

    # 1. Insert a Daily candle and an Hourly candle at the exact same time
    initial_records = [
        {
            "time": base_time,
            "symbol": "AAPL",
            "timeframe": "1d",
            "open": 100,
            "high": 110,
            "low": 90,
            "close": 105,
            "volume": 1000,
        },
        {
            "time": base_time,
            "symbol": "AAPL",
            "timeframe": "1h",
            "open": 100,
            "high": 102,
            "low": 99,
            "close": 101,
            "volume": 500,
        },
    ]
    upsert_candles(db_session, initial_records)

    # Verify both were inserted (Timeframe isolation works)
    count = db_session.query(Candle).count()
    assert count == 2, "Failed to isolate 1d and 1h timeframes"

    # 2. Try to insert the exact same Daily candle again (The Upsert test)
    duplicate_record = [
        {
            "time": base_time,
            "symbol": "AAPL",
            "timeframe": "1d",
            "open": 999,
            "high": 999,
            "low": 999,
            "close": 999,
            "volume": 999,
        }
    ]
    upsert_candles(db_session, duplicate_record)

    # Verify the database didn't crash, and the count is still 2
    count_after_duplicate = db_session.query(Candle).count()
    assert (
        count_after_duplicate == 2
    ), "Upsert failed; duplicate was inserted or crashed"

    # Verify the original price (105) wasn't overwritten by the duplicate (999)
    daily_candle = db_session.query(Candle).filter_by(timeframe="1d").first()
    assert (
        daily_candle.close == 105
    ), "ON CONFLICT DO NOTHING failed; data was overwritten"
