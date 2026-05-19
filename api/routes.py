from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import os
import joblib
from db.database import get_db
from db.models import Candle
from services.market_data import fetch_and_store_candles
from services.feature_engineering import generate_features
from services.ml_engine import train_ensemble_model
from services.regime_detection import train_regime_model, detect_current_regime

router = APIRouter()


@router.post("/ingest/{symbol}")
def ingest_data(symbol: str, period: str = "1y", db: Session = Depends(get_db)):
    """Fetches historical data from Yahoo Finance and saves it to TimescaleDB."""
    count = fetch_and_store_candles(symbol, db, period)

    if count == 0:
        raise HTTPException(
            status_code=404, detail=f"No data found for ticker {symbol}"
        )

    return {"message": f"Successfully ingested {count} candles for {symbol.upper()}"}


@router.get("/candles/{symbol}")
def get_candles(symbol: str, limit: int = 100, db: Session = Depends(get_db)):
    """Retrieves the most recent candles from the database."""
    # We query by symbol, order by time descending, and limit the results
    candles = (
        db.query(Candle)
        .filter(Candle.symbol == symbol.upper())
        .order_by(Candle.time.desc())
        .limit(limit)
        .all()
    )
    return candles


@router.get("/features/{symbol}")
def get_features(symbol: str, limit: int = 500, db: Session = Depends(get_db)):
    """Retrieves raw candles and calculates technical indicators."""
    df = generate_features(symbol, db, limit)

    if df is None or df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Not enough data to calculate features for {symbol}",
        )

    # Convert the DataFrame back to a dictionary so FastAPI can return it as JSON
    # We reset the index so 'time' becomes a normal column again
    result = df.reset_index().to_dict(orient="records")
    return result


@router.post("/train/{symbol}")
def train_model(symbol: str, limit: int = 1000, db: Session = Depends(get_db)):
    """Trains the XGBoost classifier on historical features and saves the model."""
    result = train_ensemble_model(symbol, db, limit)

    regime_result = train_regime_model(symbol, db, limit)
    result["regime_status"] = regime_result.get("message", "Failed")

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/predict/{symbol}")
def get_live_signal(symbol: str, db: Session = Depends(get_db)):
    """Generates a live trading signal based on the most recent market data."""

    # 1. Load the trained brains
    MODEL_DIR = "models/"
    try:
        xgb_model = joblib.load(os.path.join(MODEL_DIR, f"{symbol.lower()}_xgb.pkl"))
        lgb_model = joblib.load(os.path.join(MODEL_DIR, f"{symbol.lower()}_lgb.pkl"))
        expected_features = joblib.load(
            os.path.join(MODEL_DIR, f"{symbol.lower()}_features.pkl")
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=400,
            detail=f"Models for {symbol} not found. Run /train/{symbol} first.",
        )

    # 2. Get the latest features
    # We only need enough data to calculate the moving averages (limit=100 is plenty)
    df = generate_features(symbol, db, limit=100)
    if df is None or df.empty:
        raise HTTPException(status_code=400, detail="Not enough live data to predict.")

    # 3. Grab the absolute newest row of data (Today/Right Now)
    latest_data = df.iloc[-1:]

    # Ensure columns perfectly match what the AI was trained on
    latest_features = latest_data[expected_features]

    # 4. Ask the Ensemble for its probabilities
    xgb_prob = float(xgb_model.predict_proba(latest_features)[:, 1][0])
    lgb_prob = float(lgb_model.predict_proba(latest_features)[:, 1][0])

    ensemble_score = (xgb_prob + lgb_prob) / 2

    current_state, is_dangerous = detect_current_regime(symbol, df)

    # 5. Format the Signal
    signal = "NEUTRAL"
    if ensemble_score >= 0.55:
        signal = "BUY "
    elif ensemble_score <= 0.45:
        signal = "SELL "

    if is_dangerous:
        signal = f"BLOCKED BY RISK GATE (Extreme Volatility, Regime {current_state})"

    return {
        "symbol": symbol.upper(),
        "timestamp": latest_data.index[0].isoformat(),
        "latest_close_price": float(latest_data["close"].iloc[0]),
        "signal": signal,
        "confidence_score": round(ensemble_score * 100, 2),
        "market_regime": {
            "hmm_state": current_state,
            "high_volatility_warning": is_dangerous,
        },
        "breakdown": {
            "xgboost_probability": round(xgb_prob * 100, 2),
            "lightgbm_probability": round(lgb_prob * 100, 2),
        },
    }
