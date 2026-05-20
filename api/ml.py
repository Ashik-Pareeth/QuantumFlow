from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import joblib
import os

from db.database import get_db
from services.feature_engineering import generate_features
from services.ml_engine import train_ensemble_model
from services.regime_detection import (
    train_regime_model,
    detect_current_regime,
)
from core.cache import get_cached_signal, set_cached_signal
from exceptions.custom_errors import (
    ModelNotTrainedError,
    QuantumFlowException,
)

router = APIRouter()


@router.post("/train/{symbol}")
def train_model(symbol: str, limit: int = 1000, db: Session = Depends(get_db)):
    """Trains the ensemble models and HMM regime detector."""

    result = train_ensemble_model(symbol, db, limit)

    regime_result = train_regime_model(symbol, db, limit)

    result["regime_status"] = regime_result.get("message", "Failed")

    if "error" in result:
        raise QuantumFlowException(
            detail=result["error"],
            status_code=400,
        )

    return result


@router.get("/predict/{symbol}")
def get_live_signal(symbol: str, db: Session = Depends(get_db)):
    """Generates a live trading signal."""

    cached_response = get_cached_signal(symbol)

    if cached_response:
        return cached_response

    model_dir = "models/"

    try:
        xgb_model = joblib.load(os.path.join(model_dir, f"{symbol.lower()}_xgb.pkl"))

        lgb_model = joblib.load(os.path.join(model_dir, f"{symbol.lower()}_lgb.pkl"))

        expected_features = joblib.load(
            os.path.join(model_dir, f"{symbol.lower()}_features.pkl")
        )

    except FileNotFoundError:
        raise ModelNotTrainedError(symbol=symbol)

    df = generate_features(symbol, db, limit=100)

    if df is None or df.empty:
        raise QuantumFlowException(
            message="Not enough live data to predict.",
            status_code=400,
        )

    latest_data = df.iloc[-1:]

    latest_features = latest_data[expected_features]

    xgb_prob = float(xgb_model.predict_proba(latest_features)[:, 1][0])

    lgb_prob = float(lgb_model.predict_proba(latest_features)[:, 1][0])

    ensemble_score = (xgb_prob + lgb_prob) / 2

    current_state, readable_state, is_dangerous = detect_current_regime(symbol, df)

    signal = "NEUTRAL"

    if ensemble_score >= 0.55:
        signal = "BUY"

    elif ensemble_score <= 0.45:
        signal = "SELL"

    if is_dangerous:
        signal = "BLOCKED BY RISK GATE " f"(Extreme Volatility, Regime {current_state})"

    final_payload = {
        "symbol": symbol.upper(),
        "timestamp": latest_data.index[0].isoformat(),
        "latest_close_price": float(latest_data["close"].iloc[0]),
        "signal": signal,
        "confidence_score": round(ensemble_score * 100, 2),
        "market_regime": {
            "hmm_state": current_state,
            "description": readable_state,
            "high_volatility_warning": is_dangerous,
        },
        "breakdown": {
            "xgboost_probability": round(xgb_prob * 100, 2),
            "lightgbm_probability": round(lgb_prob * 100, 2),
        },
    }

    set_cached_signal(symbol, final_payload)

    return final_payload
