from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from exceptions.custom_errors import QuantumFlowException, InsufficientDataError
from services.ml_service import get_market_prediction, train_models_for_symbol


def test_train_models_for_symbol_combines_model_statuses():
    db = MagicMock()

    with patch(
        "services.ml_service.train_ensemble_model",
        return_value={"symbol": "AAPL", "message": "Ensemble trained"},
    ), patch(
        "services.ml_service.train_regime_model",
        return_value={"message": "Regime trained"},
    ):
        result = train_models_for_symbol("AAPL", 1000, db)

    assert result["symbol"] == "AAPL"
    assert result["regime_status"] == "Regime trained"


def test_train_models_for_symbol_raises_on_ensemble_error():
    db = MagicMock()

    with patch(
        "services.ml_service.train_ensemble_model",
        return_value={"error": "Not enough data"},
    ), patch("services.ml_service.train_regime_model", return_value={}):
        with pytest.raises(QuantumFlowException) as exc_info:
            train_models_for_symbol("AAPL", 1000, db)

    assert exc_info.value.status_code == 400
    assert "Not enough data" in exc_info.value.message


@patch("services.ml_service.generate_features")
def test_get_market_prediction_returns_insufficient_data(mock_generate):
    mock_generate.return_value = pd.DataFrame()
    
    result = get_market_prediction("AAPL", MagicMock())
    
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["signal"] == "NEUTRAL"
    assert result["symbol"] == "AAPL"


@patch("services.ml_service.detect_current_regime", return_value=(2, "Low Vol", False))
@patch("services.ml_service.generate_features")
@patch("services.ml_service.joblib.load")
@patch("builtins.open")
def test_get_market_prediction_returns_buy_signal(
    mock_open, mock_load, mock_generate, mock_regime
):
    xgb_model = MagicMock()
    xgb_model.predict_proba.return_value = np.array([[0.3, 0.7]])
    lgb_model = MagicMock()
    lgb_model.predict_proba.return_value = np.array([[0.4, 0.6]])
    mock_load.side_effect = [xgb_model, lgb_model]
    
    mock_open.return_value.__enter__.return_value.read.return_value = '{"latest_version": "v1", "feature_names": ["rsi", "atr"]}'
    
    # We need to mock json.load specifically to return what we want
    with patch("services.ml_service.json.load") as mock_json_load:
        mock_json_load.side_effect = [
            {"latest_version": "v1"},
            {"feature_names": ["rsi", "atr"]}
        ]
        
        mock_generate.return_value = pd.DataFrame(
            {"close": [150.0], "rsi": [55.0], "atr": [2.5]},
            index=[pd.Timestamp("2026-01-01")],
        )

        result = get_market_prediction("AAPL", MagicMock())

        assert result["symbol"] == "AAPL"
        assert result["signal"] == "BUY"
        assert result["status"] == "ANALYSIS_COMPLETE"
