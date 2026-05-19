import pandas as pd
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
    if df.empty or df is None:
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
        return None, "HMM not trained"

    # Format the live data exactly how the HMM expects it
    df_live = df.copy()
    df_live["returns"] = (df_live["close"] - df_live["close"].shift(1)) / (
        df_live["close"].shift(1) + 1e-6
    )

    # Grab the very last row (Today)
    latest_data = df_live.dropna().iloc[-1:]
    X_live = latest_data[["returns", "atr"]].values

    # Predict the hidden state (will return 0, 1, or 2)
    current_state = int(hmm_model.predict(X_live)[0])

    # HMM states are unsupervised, so we don't inherently know which number is
    # "Bull" or "Bear".
    # But we can look at the current volatility (ATR) to guess if it's dangerous.
    current_atr = latest_data["atr"].iloc[0]
    avg_atr = df_live["atr"].mean()

    is_dangerous = current_atr > (
        avg_atr * 1.5
    )  # If volatility is 50% higher than average

    return current_state, is_dangerous
