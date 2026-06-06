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


from exceptions.custom_errors import ModelNotTrainedError, QuantumFlowException, InsufficientDataError

def get_market_prediction(symbol: str, db: Session) -> dict:
    """Evaluate live market regimes and optionally ML models for a signal."""
    # 1. Graceful Degradation for Data Generation
    try:
        df = generate_features(symbol, db, limit=100)
        if df is None or df.empty:
            raise InsufficientDataError(process="evaluate market regime")
    except InsufficientDataError:
        return {
            "symbol": symbol.upper(),
            "regime": "UNKNOWN",
            "is_dangerous": False,
            "signal": "NEUTRAL",
            "status": "INSUFFICIENT_DATA",
        }

    # 2. Evaluate Regime
    current_state, readable_state, is_dangerous = detect_current_regime(symbol, df)

    # 3. Calculate simple signal
    if is_dangerous:
        signal = "NEUTRAL"
    else:
        # Evaluate existing XGBoost/LightGBM models if active
        try:
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
            
            actual_features = [col for col in df.columns if col not in ["time", "target"]]
            if set(actual_features) == set(expected_features):
                latest_data = df.iloc[-1:]
                latest_features = latest_data[expected_features]
                xgb_prob = float(xgb_model.predict_proba(latest_features)[:, 1][0])
                lgb_prob = float(lgb_model.predict_proba(latest_features)[:, 1][0])
                ensemble_score = (xgb_prob + lgb_prob) / 2
                
                if ensemble_score >= metadata.get("threshold_used", 0.55):
                    signal = "BUY"
                elif ensemble_score <= (1 - metadata.get("threshold_used", 0.55)):
                    signal = "SELL"
                else:
                    signal = "NEUTRAL"
            else:
                signal = "BUY"
        except Exception:
            # Fallback if no models are trained or missing files
            signal = "BUY"

    return {
        "symbol": symbol.upper(),
        "regime": readable_state,
        "is_dangerous": is_dangerous,
        "signal": signal,
        "status": "ANALYSIS_COMPLETE",
    }
