import os
import json
import joblib
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from core.cache import get_cached_signal, set_cached_signal
from core.config import settings
from exceptions.custom_errors import ModelNotTrainedError, QuantumFlowException
from services.feature_engineering import generate_features
from services.ml_engine import train_ensemble_model
from services.regime_detection import detect_current_regime, train_regime_model

MODEL_DIR = settings.model_dir


def train_models_for_symbol(symbol: str, limit: int, db: Session) -> dict:
    """Train ensemble and regime models for a symbol."""
    result = train_ensemble_model(symbol, db, limit)
    regime_result = train_regime_model(symbol, db, limit)

    result["regime_status"] = regime_result.get("message", "Failed")
    if "error" in result:
        raise QuantumFlowException(message=result["error"], status_code=400)
    return result


def generate_live_signal(
    symbol: str, db: Session, force_execution: bool = False
) -> dict:
    """Generate and cache a live trading signal."""
    # NOTE: In production, the cache key should include the force_execution boolean!
    cached_response = get_cached_signal(f"{symbol}_{force_execution}")
    if cached_response:
        return cached_response

    try:
        # --- DEFENSE LAYER 3: DYNAMIC MODEL LOADING ---
        with open(os.path.join(MODEL_DIR, f"{symbol.lower()}_latest.json"), "r") as f:
            version_info = json.load(f)

        version = version_info["latest_version"]
        xgb_model = joblib.load(
            os.path.join(MODEL_DIR, f"{symbol.lower()}_xgb_{version}.pkl")
        )
        lgb_model = joblib.load(
            os.path.join(MODEL_DIR, f"{symbol.lower()}_lgb_{version}.pkl")
        )

        with open(
            os.path.join(MODEL_DIR, f"{symbol.lower()}_metadata_{version}.json"), "r"
        ) as f:
            metadata = json.load(f)
            expected_features = metadata["feature_names"]
            trained_at = datetime.fromisoformat(metadata["trained_at"])

    except (FileNotFoundError, KeyError):
        raise ModelNotTrainedError(symbol=symbol)

    # Validate Model Age (Warn if > 30 days old)
    age_days = (datetime.now(timezone.utc) - trained_at).days
    if age_days > 90:
        raise QuantumFlowException(
            message=f"Model for {symbol} is {age_days} days old and stale."
            " Retrain immediately.",
            status_code=503,
        )

    df = generate_features(symbol, db, limit=100)
    if df is None or df.empty:
        raise QuantumFlowException(
            message="Not enough live data to predict.", status_code=400
        )

    # --- DEFENSE LAYER 4: STRICT SCHEMA VALIDATION (ISSUE-006) ---
    actual_features = [col for col in df.columns if col not in ["time", "target"]]
    if set(actual_features) != set(expected_features):
        missing = set(expected_features) - set(actual_features)
        raise QuantumFlowException(
            message="Feature schema mismatch."
            f" Model expects {len(expected_features)} columns. Missing: {missing}",
            status_code=503,
        )

    latest_data = df.iloc[-1:]
    latest_features = latest_data[expected_features]

    xgb_prob = float(xgb_model.predict_proba(latest_features)[:, 1][0])
    lgb_prob = float(lgb_model.predict_proba(latest_features)[:, 1][0])
    ensemble_score = (xgb_prob + lgb_prob) / 2

    current_state, readable_state, is_dangerous = detect_current_regime(symbol, df)

    signal = "NEUTRAL"
    if ensemble_score >= metadata.get("threshold_used", 0.55):
        signal = "BUY"
    elif ensemble_score <= (1 - metadata.get("threshold_used", 0.55)):
        signal = "SELL"

    # --- DEFENSE LAYER 5: RESPECT THE OVERRIDE (ISSUE-012) ---
    if is_dangerous and not force_execution:
        signal = f"BLOCKED BY RISK GATE (Extreme Volatility, Regime {current_state})"

    final_payload = {
        "symbol": symbol.upper(),
        "timestamp": latest_data.index[0].isoformat(),
        "latest_close_price": float(latest_data["close"].iloc[0]),
        "signal": signal,
        "force_execution_applied": force_execution,
        "confidence_score": round(ensemble_score * 100, 2),
        "model_version": version,
        "model_age_days": age_days,
        "market_regime": {
            "hmm_state": current_state,
            "description": readable_state,
            "high_volatility_warning": is_dangerous,
        },
    }

    set_cached_signal(f"{symbol}_{force_execution}", final_payload)
    return final_payload
