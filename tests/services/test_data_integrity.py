import pandas as pd
from datetime import datetime
from services.market_data import fetch_and_store_candles
from unittest.mock import patch


def test_ingestion_purges_duplicates_and_enforces_utc(db_session):
    """Guarantees the ingestion pipeline fixes yfinance data before the DB."""

    # 1. Create dirty, timezone-naive data with a duplicate timestamp
    dirty_times = [
        datetime(2026, 5, 22, 9, 30),  # Time naive
        datetime(2026, 5, 22, 9, 30),  # DUPLICATE!
        datetime(2026, 5, 22, 9, 35),
    ]

    # The duplicate has a different close price to test keep='last'
    dirty_df = pd.DataFrame(
        {
            "Open": [100, 100, 105],
            "High": [110, 110, 106],
            "Low": [90, 90, 104],
            "Close": [105, 108, 105],  # 108 should win
            "Volume": [1000, 1000, 500],
        },
        index=dirty_times,
    )

    # 2. Mock yfinance to return our dirty dataframe
    with patch("services.market_data.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = dirty_df

        # 3. Run the ingestion
        # We must patch the repository call to just return the cleaned records
        with patch(
            "services.market_data.candle_repository.upsert_candles"
        ) as mock_upsert:
            fetch_and_store_candles("AAPL", db_session, interval="5m")

            # 4. Extract the cleaned records sent to the database
            cleaned_records = mock_upsert.call_args[0][1]

            # ASSERTIONS
            assert len(cleaned_records) == 2, "Failed to drop duplicate timestamp"

            first_record = cleaned_records[0]
            assert (
                first_record["close"] == 108.0
            ), "Failed to keep the 'last' duplicate value"
            assert (
                first_record["time"].tzinfo is not None
            ), "Failed to localize timezone"
            assert (
                str(first_record["time"].tzinfo) == "UTC"
            ), "Timezone must be strictly UTC"
            assert first_record["timeframe"] == "5m", "Timeframe was not injected"
