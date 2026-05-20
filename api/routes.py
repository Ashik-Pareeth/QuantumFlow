from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
import os
import joblib
from decimal import Decimal

from db.database import get_db
from db.models import Wallet, Position, Trade, TradeSide, Candle
from services.market_data import fetch_and_store_candles
from services.feature_engineering import generate_features
from services.ml_engine import train_ensemble_model
from services.regime_detection import train_regime_model, detect_current_regime
from core.cache import get_cached_signal, set_cached_signal
from api.schemas import BuyTradeRequest
from exceptions.custom_errors import (
    ModelNotTrainedError,
    QuantumFlowException,
    InsufficientDataError,
    RiskGateBlockedError,
)

router = APIRouter()


@router.post("/ingest/{symbol}")
def ingest_data(symbol: str, period: str = "1y", db: Session = Depends(get_db)):
    """Fetches historical data from Yahoo Finance and saves it to TimescaleDB."""
    count = fetch_and_store_candles(symbol, db, period)

    if count == 0:
        raise QuantumFlowException(
            detail=f"No data found for ticker {symbol}", status_code=404
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
        raise QuantumFlowException(
            detail=f"Not enough data to calculate features for {symbol}",
            status_code=404,
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
        raise QuantumFlowException(detail=result["error"], status_code=400)

    return result


@router.get("/predict/{symbol}")
def get_live_signal(symbol: str, db: Session = Depends(get_db)):
    """Generates a live trading signal based on the most recent market data."""

    cached_response = get_cached_signal(symbol)
    if cached_response:
        return cached_response

    # 1. Load the trained brains
    MODEL_DIR = "models/"
    try:
        xgb_model = joblib.load(os.path.join(MODEL_DIR, f"{symbol.lower()}_xgb.pkl"))
        lgb_model = joblib.load(os.path.join(MODEL_DIR, f"{symbol.lower()}_lgb.pkl"))
        expected_features = joblib.load(
            os.path.join(MODEL_DIR, f"{symbol.lower()}_features.pkl")
        )
    except FileNotFoundError:
        raise ModelNotTrainedError(symbol=symbol)

    # 2. Get the latest features
    # We only need enough data to calculate the moving averages (limit=100 is plenty)
    df = generate_features(symbol, db, limit=100)
    if df is None or df.empty:
        raise QuantumFlowException(
            message="Not enough live data to predict.", status_code=400
        )

    # 3. Grab the absolute newest row of data (Today/Right Now)
    latest_data = df.iloc[-1:]

    # Ensure columns perfectly match what the AI was trained on
    latest_features = latest_data[expected_features]

    # 4. Ask the Ensemble for its probabilities
    xgb_prob = float(xgb_model.predict_proba(latest_features)[:, 1][0])
    lgb_prob = float(lgb_model.predict_proba(latest_features)[:, 1][0])

    ensemble_score = (xgb_prob + lgb_prob) / 2

    current_state, readable_state, is_dangerous = detect_current_regime(symbol, df)

    # 5. Format the Signal
    signal = "NEUTRAL"
    if ensemble_score >= 0.55:
        signal = "BUY "
    elif ensemble_score <= 0.45:
        signal = "SELL "

    if is_dangerous:
        signal = f"BLOCKED BY RISK GATE (Extreme Volatility, Regime {current_state})"

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

    # 7. SAVE TO CACHE: Store it in Docker for the next user
    set_cached_signal(symbol, final_payload)

    return final_payload


@router.post("/trade/buy")
def execute_buy(request: BuyTradeRequest, db: Session = Depends(get_db)):
    """Executes a trade, backed by the HMM Risk Gate."""
    symbol = request.symbol.upper()

    # ==========================================
    # 1. RISK GATE & PRICING (Read Operations)
    # ==========================================

    latest_candle = (
        db.query(Candle)
        .filter(Candle.symbol == symbol)
        .order_by(Candle.time.desc())
        .first()
    )
    if not latest_candle:
        raise QuantumFlowException(
            message=f"No pricing data available for {symbol}", status_code=404
        )

    execution_price = latest_candle.close
    total_cost = request.qty * execution_price

    df = generate_features(symbol, db, limit=100)
    if df is None or df.empty:
        raise InsufficientDataError()

    current_state, readable_state, is_dangerous = detect_current_regime(symbol, df)

    if is_dangerous and not request.force_execution:
        raise RiskGateBlockedError(
            reason=f"Market regime is currently {readable_state}."
            " To proceed anyway, confirm the risk.",
            status_code=status.HTTP_409_CONFLICT,
        )

    # ==========================================
    # 2. THE VIRTUAL ECONOMY (Write Operations)
    # ==========================================

    try:
        # Lock the user's wallet row to prevent double-spend race conditions
        wallet = (
            db.query(Wallet)
            .filter(Wallet.user_id == request.user_id)
            .with_for_update()
            .first()
        )
        if not wallet:
            raise QuantumFlowException(message="Wallet not found.", status_code=404)

        if wallet.cash_balance < total_cost:
            raise QuantumFlowException(message="Insufficient funds.", status_code=400)

        # 20% Position Limit Guardrail
        positions = db.query(Position).filter(Position.user_id == request.user_id).all()
        invested_value = sum((p.qty * p.avg_price) for p in positions)
        estimated_portfolio_value = wallet.cash_balance + invested_value

        if total_cost > (estimated_portfolio_value * Decimal("0.20")):
            raise QuantumFlowException(
                message="Position limit exceeded."
                " You cannot invest more than 20% of your portfolio in a single asset.",
                status_code=400,
            )

        # 1. Deduct Cash
        wallet.cash_balance -= total_cost

        # 2. Log the Trade (Immutable Ledger)
        new_trade = Trade(
            user_id=request.user_id,
            symbol=symbol,
            side=TradeSide.BUY,
            qty=request.qty,
            price=execution_price,
            pnl=Decimal("0.00"),
        )
        db.add(new_trade)

        # 3. Upsert the Position (Average Down Math)
        position = (
            db.query(Position)
            .filter(Position.user_id == request.user_id, Position.symbol == symbol)
            .first()
        )

        if position:
            total_historical_cost = position.qty * position.avg_price
            new_total_cost = total_historical_cost + total_cost
            new_total_qty = position.qty + request.qty

            position.avg_price = new_total_cost / new_total_qty
            position.qty = new_total_qty
        else:
            position = Position(
                user_id=request.user_id,
                symbol=symbol,
                qty=request.qty,
                avg_price=execution_price,
            )
            db.add(position)

        db.commit()

        # TODO: Phase 4.5 -> Emit event to Redis Stream for Leaderboard Worker here

        return {
            "message": "BUY order executed successfully.",
            "symbol": symbol,
            "qty": request.qty,
            "execution_price": execution_price,
            "total_cost": total_cost,
            "remaining_balance": wallet.cash_balance,
            "new_avg_price": position.avg_price,
            "market_regime_id": current_state,
        }

    except Exception as e:
        db.rollback()
        raise e
