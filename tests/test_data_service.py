from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from exceptions.custom_errors import QuantumFlowException
from services.data_service import (
    get_recent_candles,
    get_technical_features,
    ingest_market_data,
)


def test_ingest_market_data_success():
    db = MagicMock()

    with patch("services.data_service.fetch_and_store_candles", return_value=3):
        result = ingest_market_data("aapl", "1y", db)

    assert result == {"message": "Successfully ingested 3 candles for AAPL"}


def test_ingest_market_data_raises_when_no_rows_found():
    db = MagicMock()

    with patch("services.data_service.fetch_and_store_candles", return_value=0):
        with pytest.raises(QuantumFlowException) as exc_info:
            ingest_market_data("missing", "1y", db)

    assert exc_info.value.status_code == 404
    assert "missing" in exc_info.value.message


def test_get_recent_candles_queries_uppercase_symbol():
    candle = SimpleNamespace(symbol="AAPL", close=150)
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.limit.return_value = query
    query.all.return_value = [candle]
    db = MagicMock()
    db.query.return_value = query

    result = get_recent_candles("aapl", 10, db)

    assert result == [candle]
    query.limit.assert_called_once_with(10)


def test_get_technical_features_serializes_dataframe():
    db = MagicMock()
    df = pd.DataFrame(
        {"close": [150.0], "rsi": [55.0]},
        index=pd.DatetimeIndex([pd.Timestamp("2026-01-01")], name="time"),
    )

    with patch("services.data_service.generate_features", return_value=df):
        result = get_technical_features("AAPL", 100, db)

    assert result[0]["close"] == 150.0
    assert result[0]["rsi"] == 55.0
    assert result[0]["time"] == pd.Timestamp("2026-01-01")


def test_get_technical_features_raises_when_empty():
    db = MagicMock()

    with patch("services.data_service.generate_features", return_value=pd.DataFrame()):
        with pytest.raises(QuantumFlowException) as exc_info:
            get_technical_features("AAPL", 100, db)

    assert exc_info.value.status_code == 404
