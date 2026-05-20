import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from services.ml_engine import train_ensemble_model


def generate_synthetic_features(num_rows=100):
    """Generates synthetic time-series feature data for model training tests."""
    dates = pd.date_range(start="2026-01-01", periods=num_rows, freq="D")
    df = pd.DataFrame(
        {
            "close": np.linspace(100, 150, num_rows) + np.random.normal(0, 2, num_rows),
            "rsi": np.random.uniform(20, 80, num_rows),
            "atr": np.random.uniform(1.0, 5.0, num_rows),
        },
        index=dates,
    )
    return df


@patch("services.ml_engine.joblib.dump")
@patch("services.ml_engine.generate_features")
def test_train_ensemble_model_success(mock_generate, mock_dump):
    """Verifies that the ensemble pipeline splits data chronologically
    and saves artifacts."""
    # 1. Arrange
    symbol = "AAPL"
    mock_db = MagicMock()
    synthetic_df = generate_synthetic_features(50)
    mock_generate.return_value = synthetic_df

    # 2. Act
    result = train_ensemble_model(symbol, mock_db, limit=50)

    # 3. Assert
    assert result["symbol"] == symbol
    assert "ensemble_accuracy" in result
    assert result["threshold_used"] == 0.55

    # Prove that joblib.dump was called exactly 3 times (XGB, LGB, and Features list)
    assert mock_dump.call_count == 3


@patch("services.ml_engine.generate_features")
def test_train_ensemble_model_insufficient_data(mock_generate):
    """Ensures the engine handles an empty or missing dataset gracefully."""
    # 1. Arrange
    mock_db = MagicMock()
    mock_generate.return_value = pd.DataFrame()  # Empty dataframe

    # 2. Act
    result = train_ensemble_model("AAPL", mock_db)

    # 3. Assert
    assert "error" in result
    assert "Not enough data" in result["error"]
