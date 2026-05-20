from exceptions.custom_errors import ModelNotTrainedError, RiskGateBlockedError
import pandas as pd
from unittest.mock import MagicMock, patch
from services.regime_detection import detect_current_regime


def test_model_not_trained_error_formatting():
    """Tests if the ModelNotTrainedError correctly formats the symbol and status code."""
    # 1. Arrange
    test_symbol = "AAPL"

    # 2. Act
    error = ModelNotTrainedError(symbol=test_symbol)

    # 3. Assert
    assert error.status_code == 404
    assert "AAPL" in error.message
    assert "not trained" in error.message


def test_risk_gate_error_formatting():
    """Tests if the Risk Gate exception securely defaults to a 422
    Unprocessable Entity."""
    # 1. Arrange
    reason = "Extreme Volatility Bearish"

    # 2. Act
    error = RiskGateBlockedError(reason=reason)

    # 3. Assert
    assert error.status_code == 422
    assert reason in error.message
    assert "Risk Gate" in error.message


def test_detect_current_regime_missing_model():
    """Tests the fallback safety mechanism if the HMM model hasn't been trained yet."""
    # 1. Arrange: Create a minimal dummy dataframe
    dummy_df = pd.DataFrame({"close": [100.0, 101.0], "atr": [1.5, 1.6]})

    # 2. Act & Assert: Intercept joblib.load to force a FileNotFoundError
    with patch("services.regime_detection.joblib.load", side_effect=FileNotFoundError):
        state, label, is_dangerous = detect_current_regime("FAKE_SYMBOL", dummy_df)

    assert state is None
    assert label == "HMM OFFLINE"
    assert is_dangerous is True


@patch("services.regime_detection.joblib.load")
@patch("services.regime_detection.interpret_regimes")
def test_detect_current_regime_success(mock_interpret, mock_load):
    """Tests the live detection logic with a fully mocked machine learning model."""
    # 1. Arrange
    # Mock the human-readable labels
    mock_interpret.return_value = {
        0: "Low Volatility Bullish",
        1: "Extreme Volatility Bearish",
    }

    # Mock the HMM model's predict function to always return state '1'
    mock_model = MagicMock()
    mock_model.predict.return_value = [1]
    mock_load.return_value = mock_model

    # Create 3 days of dummy data.
    # The massive final ATR (8.0) should trigger the danger gate.
    dummy_df = pd.DataFrame({"close": [100.0, 105.0, 95.0], "atr": [2.0, 2.5, 8.0]})

    # 2. Act
    state, label, is_dangerous = detect_current_regime("AAPL", dummy_df)

    # 3. Assert
    assert state == 1
    assert label == "Extreme Volatility Bearish"
    assert is_dangerous is True
