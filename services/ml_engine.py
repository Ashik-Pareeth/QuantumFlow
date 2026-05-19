import pandas as pd
import xgboost as xgb
import lightgbm as lgb
import joblib
import os
from sklearn.metrics import accuracy_score
from sqlalchemy.orm import Session
from services.feature_engineering import generate_features

MODEL_DIR = "models/"
os.makedirs(MODEL_DIR, exist_ok=True)


def train_ensemble_model(symbol: str, db: Session, limit: int = 2000):
    print(f"🧠 Training Ensemble Brain for {symbol}...")

    df = generate_features(symbol, db, limit)
    if df is None or df.empty:
        return {"error": "Not enough data to train."}

    # The Target: Will the next candle close higher than this one?
    df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)
    df.dropna(inplace=True)

    features = [col for col in df.columns if col not in ["target"]]
    X = df[features]
    y = df["target"]

    # Chronological Split (80/20)
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    print(
        f"Training on {len(X_train)} rows (Past), Testing on {len(X_test)} rows (Future)..."
    )

    # --- MODEL 1: XGBoost ---
    print("🌲 Training XGBoost...")
    xgb_model = xgb.XGBClassifier(
        n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42
    )
    xgb_model.fit(X_train, y_train)

    # --- MODEL 2: LightGBM ---
    print("⚡ Training LightGBM...")
    lgb_model = lgb.LGBMClassifier(
        n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42, verbose=-1
    )
    lgb_model.fit(X_train, y_train)

    # --- ENSEMBLE VOTING (The "Soft Vote") ---
    # predict_proba returns an array: [Probability of 0, Probability of 1]
    # We only want the probability of 1 (price going up), so we take [:, 1]
    xgb_probs = xgb_model.predict_proba(X_test)[:, 1]
    lgb_probs = lgb_model.predict_proba(X_test)[:, 1]

    # The Ensemble Score is the average of both brains
    ensemble_probs = (xgb_probs + lgb_probs) / 2

    # We only execute a "Buy" if BOTH models combined are more than 55% confident
    # In finance, a high threshold protects you from random noise
    CONFIDENCE_THRESHOLD = 0.55
    ensemble_predictions = (ensemble_probs >= CONFIDENCE_THRESHOLD).astype(int)

    accuracy = accuracy_score(y_test, ensemble_predictions)

    # Save both models and the feature list (so we know exactly what columns the AI expects later)
    joblib.dump(xgb_model, os.path.join(MODEL_DIR, f"{symbol.lower()}_xgb.pkl"))
    joblib.dump(lgb_model, os.path.join(MODEL_DIR, f"{symbol.lower()}_lgb.pkl"))
    joblib.dump(features, os.path.join(MODEL_DIR, f"{symbol.lower()}_features.pkl"))

    return {
        "symbol": symbol,
        "ensemble_accuracy": round(accuracy, 4),
        "threshold_used": CONFIDENCE_THRESHOLD,
        "message": "Ensemble models trained and saved.",
    }
