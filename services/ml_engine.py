from datetime import datetime, timezone
import hashlib
import json
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

    df = df.iloc[:-1]
    df.dropna(inplace=True)

    features = [col for col in df.columns if col not in ["target"]]
    X = df[features]
    y = df["target"]

    # Chronological Split (80/20)
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    print(
        f"Training on {len(X_train)} rows (Past),"
        f" Testing on {len(X_test)} "
        "rows (Future)..."
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

    training_timestamp = datetime.now(timezone.utc).isoformat()
    # Create a deterministic hash of the data used for this exact training run
    data_checksum = hashlib.sha256(df.to_string().encode()).hexdigest()[:8]
    # Safe filename string (no colons or spaces)
    version = f"{training_timestamp.replace(':', '')}_{data_checksum}"

    metadata = {
        "symbol": symbol.upper(),
        "version": version,
        "trained_at": training_timestamp,
        "data_checksum": data_checksum,
        "training_rows": len(X_train),
        "testing_rows": len(X_test),
        "feature_names": features,
        "ensemble_accuracy": round(accuracy, 4),
        "threshold_used": CONFIDENCE_THRESHOLD,
        "message": "Ensemble models trained and saved.",
    }

    # Define final destination paths
    xgb_path = os.path.join(MODEL_DIR, f"{symbol.lower()}_xgb_{version}.pkl")
    lgb_path = os.path.join(MODEL_DIR, f"{symbol.lower()}_lgb_{version}.pkl")
    meta_path = os.path.join(MODEL_DIR, f"{symbol.lower()}_metadata_{version}.json")

    joblib.dump(xgb_model, xgb_path)
    joblib.dump(lgb_model, lgb_path)

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=4)
        f.flush()
        os.fsync(f.fileno())

    # Prepare the Commit (The Pointer)
    pointer_path = os.path.join(MODEL_DIR, f"{symbol.lower()}_latest.json")
    temp_pointer_path = f"{pointer_path}.tmp"

    # Write the new version to a temporary file first
    with open(temp_pointer_path, "w") as f:
        json.dump({"latest_version": version}, f)
        f.flush()
        os.fsync(f.fileno())

    os.replace(temp_pointer_path, pointer_path)

    return metadata
