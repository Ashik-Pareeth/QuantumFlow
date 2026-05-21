import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import ANY, patch, MagicMock
import numpy as np
import pandas as pd

from api.data import router as data_router
from api.ml import router as ml_router
from api.trading import router as trading_router
from db.database import get_db
from db.models import TradeSide
from exceptions.custom_errors import ModelNotTrainedError


def override_get_db():
    yield MagicMock()


# Initialize a clean, isolated testing app instance
app = FastAPI()
app.include_router(data_router)
app.include_router(ml_router)
app.include_router(trading_router)
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    """Provides a fresh FastAPI test client for network call isolation."""
    return TestClient(app)


@patch("services.ml_service.get_cached_signal")
def test_predict_endpoint_cache_hit(mock_get_cache, client):
    """Proves that the endpoint hits the Redis shield instantly if data is cached."""
    # 1. Arrange
    symbol = "NVDA"
    cached_payload = {"symbol": "NVDA", "signal": "BUY", "confidence_score": 92.5}
    mock_get_cache.return_value = cached_payload

    # 2. Act
    response = client.get(f"/predict/{symbol}")

    # 3. Assert
    assert response.status_code == 200
    assert response.json() == cached_payload


@patch("services.ml_service.get_cached_signal")
@patch("services.ml_service.joblib.load")
def test_predict_endpoint_model_not_trained(mock_load, mock_get_cache, client):
    """Verifies standard exception propagation if artifacts do not exist on disk."""
    # 1. Arrange
    symbol = "TSLA"
    mock_get_cache.return_value = None
    mock_load.side_effect = FileNotFoundError()

    # 2. Act & Assert
    # We test that the custom error gets raised out of the endpoint.
    # Note: If your app has global handlers registered,
    # assert response.status_code instead.
    with pytest.raises(ModelNotTrainedError):
        client.get(f"/predict/{symbol}")


@patch("services.ml_service.set_cached_signal")
@patch("services.ml_service.detect_current_regime")
@patch("services.ml_service.generate_features")
@patch("services.ml_service.joblib.load")
@patch("services.ml_service.get_cached_signal")
def test_predict_endpoint_cache_miss_success(
    mock_get_cache, mock_load, mock_generate, mock_regime, mock_set_cache, client
):
    """Tests a full end-to-end prediction run on a cache miss."""
    # 1. Arrange
    mock_get_cache.return_value = None  # Cache Miss

    # FIX: Wrap the mock return values in np.array so they support [:, 1] slicing
    mock_xgb = MagicMock()
    mock_xgb.predict_proba.return_value = np.array([[0.4, 0.6]])  # 60% confidence Up
    mock_lgb = MagicMock()
    mock_lgb.predict_proba.return_value = np.array([[0.3, 0.7]])  # 70% confidence Up

    # Control the mock execution chain order
    mock_load.side_effect = [mock_xgb, mock_lgb, ["rsi", "atr"]]

    # Mock out technical indicator dataframe ingestion
    df_mock = pd.DataFrame(
        {"close": [150.0], "rsi": [55.0], "atr": [2.5]}, index=[pd.Timestamp.now()]
    )
    mock_generate.return_value = df_mock

    # Mock out the HMM Risk gate values (Safe regime)
    mock_regime.return_value = (0, "Low Volatility Bullish", False)

    # 2. Act
    response = client.get("/predict/AAPL")

    # 3. Assert
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["signal"] == "BUY"
    assert data["confidence_score"] == 65.0  # Average of 60% and 70%
    assert data["market_regime"]["high_volatility_warning"] is False

    # Verify it saved this compute block back to Redis for the next run
    mock_set_cache.assert_called_once()


@patch("api.routers.data.ingest_market_data")
def test_ingest_endpoint_delegates_to_data_service(mock_ingest, client):
    """Integration check for the thin data ingestion route."""
    mock_ingest.return_value = {"message": "ok"}

    response = client.post("/ingest/AAPL?period=6mo")

    assert response.status_code == 200
    assert response.json() == {"message": "ok"}
    mock_ingest.assert_called_once_with(symbol="AAPL", period="6mo", db=ANY)


@patch("api.routers.data.get_recent_candles")
def test_candles_endpoint_delegates_to_data_service(mock_get_candles, client):
    """Integration check for the candles route."""
    mock_get_candles.return_value = [{"symbol": "AAPL", "close": 150}]

    response = client.get("/candles/aapl?limit=5")

    assert response.status_code == 200
    assert response.json() == [{"symbol": "AAPL", "close": 150}]
    mock_get_candles.assert_called_once_with(symbol="aapl", limit=5, db=ANY)


@patch("api.routers.trading.execute_trade_order")
def test_trade_endpoint_delegates_to_trading_service(mock_execute_trade, client):
    """Integration check for request parsing and service delegation."""
    user_id = "85a3a49f-e498-44f4-974f-7f4cb2d60a40"
    mock_execute_trade.return_value = {
        "message": "BUY order executed successfully.",
        "symbol": "AAPL",
    }

    response = client.post(
        "/",
        json={
            "user_id": user_id,
            "symbol": "aapl",
            "side": "buy",
            "qty": "1.5000",
            "force_execution": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["symbol"] == "AAPL"
    call_kwargs = mock_execute_trade.call_args.kwargs
    assert str(call_kwargs["user_id"]) == user_id
    assert call_kwargs["symbol"] == "AAPL"
    assert call_kwargs["side"] == TradeSide.BUY
    assert str(call_kwargs["qty"]) == "1.5000"
    assert call_kwargs["force_execution"] is True
