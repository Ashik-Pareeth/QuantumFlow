import pandas as pd
import numpy as np
from hmmlearn.hmm import GaussianHMM
import joblib
import os
from sqlalchemy.orm import Session
from services.feature_engineering import generate_features

MODEL_DIR = "models/"
os.makedirs(MODEL_DIR, exist_ok=True)


def train_regime_model(symbol: str, db: Session, limit: int = 5000):
    print(f"Training Hidden Markov Model for {symbol} Regimes...")

    df = generate_features(symbol, db, limit)
    if df is None or df.empty:
        return {"error": "Not enough data"}

    df["returns"] = (df["close"] - df["close"].shift(1)) / df["close"] + 1e-6
    df.dropna(inplace=True)

    # Returns and Volatility (ATR)
    X_hmm = df[["returns", "atr"]].values

    # Initialize a 6-State Markov Model
    hmm_model = GaussianHMM(
        n_components=6, covariance_type="full", n_iter=1000, random_state=42
    )
    hmm_model.fit(X_hmm)

    # Save the model
    joblib.dump(hmm_model, os.path.join(MODEL_DIR, f"{symbol.lower()}_hmm.pkl"))
    return {"message": "Regime model trained successfully.", "states_found": 3}


def detect_current_regime(symbol: str, df: pd.DataFrame):
    """Takes live data and asks the HMM what regime we are currently in."""
    try:
        hmm_model = joblib.load(os.path.join(MODEL_DIR, f"{symbol.lower()}_hmm.pkl"))
    except FileNotFoundError:
        return None, "HMM OFFLINE", True

    # Format the live data exactly how the HMM expects it
    df_live = df.copy()
    df_live["returns"] = (df_live["close"] - df_live["close"].shift(1)) / (
        df_live["close"].shift(1) + 1e-6
    )

    # Grab the very last row (Today)
    latest_data = df_live.dropna().iloc[-1:]
    X_live = latest_data[["returns", "atr"]].values

    # Predict the hidden state (will return 0, 1, 2, 3, 4, or 5)
    current_state = int(hmm_model.predict(X_live)[0])

    # Get the dynamic human-readable labels
    regime_labels = interpret_regimes(hmm_model)
    readable_state = regime_labels[current_state]

    # look at the current volatility (ATR) to guess if it's dangerous.
    current_atr = latest_data["atr"].iloc[0]
    avg_atr = df_live["atr"].mean()

    is_dangerous = bool(
        current_atr > (avg_atr * 1.5)
    )  # If volatility is 50% higher than average

    return current_state, readable_state, is_dangerous


def interpret_regimes(hmm_model):
    """
    Dynamically labels HMM states by analyzing their mathematical properties.
    hmm_model.means_ is a matrix where:
    Column 0 = Average Daily Return for that state
    Column 1 = Average Volatility (ATR) for that state
    """
    labels = {}

    # Extract the means for all 6 states
    returns = hmm_model.means_[:, 0]
    volatilities = hmm_model.means_[:, 1]

    # Find the medians to establish baselines
    median_return = np.median(returns)
    median_vol = np.median(volatilities)

    for i in range(hmm_model.n_components):
        state_return = returns[i]
        state_vol = volatilities[i]

        # Determine Direction
        if state_return > median_return and state_return > 0:
            direction = "Bullish"
        elif state_return < median_return and state_return < 0:
            direction = "Bearish"
        else:
            direction = "Sideways/Choppy"

        # Determine Volatility
        if state_vol > (median_vol * 1.2):
            vol_label = "Extreme Volatility"
        elif state_vol > median_vol:
            vol_label = "High Volatility"
        else:
            vol_label = "Low Volatility"

        # Combine into a human-readable label
        labels[i] = f"{vol_label} {direction}"

    return labels
