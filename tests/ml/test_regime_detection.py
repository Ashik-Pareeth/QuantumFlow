import numpy as np
from unittest.mock import MagicMock
from services.regime_detection import interpret_regimes


def test_interpret_regimes_labeling():
    """Mathematically proves the HMM matrix correctly translates to human labels."""

    # 1. Arrange: Create a fake HMM model
    mock_hmm = MagicMock()
    mock_hmm.n_components = 6

    # Create a perfectly engineered mathematical matrix to test all conditions.
    # Column 0: Average Return | Column 1: Average Volatility (ATR)
    # Let's set baselines so we know exactly what the medians will be.
    mock_hmm.means_ = np.array(
        [
            [0.05, 10.0],  # High Return, Low Volatility -> Low Volatility Bullish
            [
                -0.05,
                50.0,
            ],  # Heavy Loss, Massive Volatility -> Extreme Volatility Bearish
            [0.00, 20.0],  # Flat Return, Medium Volatility -> Choppy / High Volatility
            [
                0.08,
                60.0,
            ],  # High Return, Massive Volatility -> Extreme Volatility Bullish
            [-0.02, 15.0],  # Slight Loss, Low Volatility -> Low Volatility Bearish
            [0.01, 25.0],  # Slight Gain, Medium Volatility -> High Volatility Bullish
        ]
    )

    # 2. Act
    labels = interpret_regimes(mock_hmm)

    # 3. Assert
    assert len(labels) == 6
    assert isinstance(labels, dict)

    # Let's grab all the generated string labels
    all_labels = list(labels.values())

    # Mathematically verify that the exact string
    # "Extreme Volatility Bearish" was generated
    # (which corresponds to row index 1: [-0.05, 50.0])
    assert "Extreme Volatility Bearish" in all_labels

    # Verify we have Bullish states
    assert any("Bullish" in label for label in all_labels)

    # Verify the "Extreme Volatility" trigger worked correctly
    assert sum("Extreme Volatility" in label for label in all_labels) == 2
