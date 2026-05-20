import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import numpy as np
import pandas as pd

from api.ml import router
from db.database import get_db
from exceptions.custom_errors import ModelNotTrainedError


def override_get_db():
    yield MagicMock()


# Initialize a clean, isolated testing app instance
app = FastAPI()
app.include_router(router)
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
