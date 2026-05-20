from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from exceptions.custom_errors import ModelNotTrainedError, QuantumFlowException
from services.ml_service import generate_live_signal, train_models_for_symbol


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


@patch("services.ml_service.get_cached_signal")
def test_generate_live_signal_returns_cache_hit(mock_get_cache):
    cached_payload = {"symbol": "AAPL", "signal": "BUY"}
    mock_get_cache.return_value = cached_payload

    assert generate_live_signal("AAPL", MagicMock()) == cached_payload


@patch("services.ml_service.get_cached_signal", return_value=None)
@patch("services.ml_service.joblib.load", side_effect=FileNotFoundError)
def test_generate_live_signal_raises_when_models_are_missing(mock_load, mock_get_cache):
    with pytest.raises(ModelNotTrainedError):
        generate_live_signal("TSLA", MagicMock())


@patch("services.ml_service.set_cached_signal")
@patch("services.ml_service.detect_current_regime", return_value=(2, "Low Vol", False))
@patch("services.ml_service.generate_features")
@patch("services.ml_service.joblib.load")
@patch("services.ml_service.get_cached_signal", return_value=None)
def test_generate_live_signal_builds_and_caches_payload(
    mock_get_cache, mock_load, mock_generate, mock_regime, mock_set_cache
):
    xgb_model = MagicMock()
    xgb_model.predict_proba.return_value = np.array([[0.3, 0.7]])
    lgb_model = MagicMock()
    lgb_model.predict_proba.return_value = np.array([[0.4, 0.6]])
    mock_load.side_effect = [xgb_model, lgb_model, ["rsi", "atr"]]
    mock_generate.return_value = pd.DataFrame(
        {"close": [150.0], "rsi": [55.0], "atr": [2.5]},
        index=[pd.Timestamp("2026-01-01")],
    )

    result = generate_live_signal("aapl", MagicMock())

    assert result["symbol"] == "AAPL"
    assert result["signal"] == "BUY"
    assert result["confidence_score"] == 65.0
    mock_set_cache.assert_called_once_with("aapl", result)
