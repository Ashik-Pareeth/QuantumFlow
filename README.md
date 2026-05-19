# QuantumFlow

QuantumFlow is a production-grade, real-time market intelligence and quantitative trading backend. It ingests time-series market data, performs automated feature engineering, and generates live trading signals using a dual-model machine learning ensemble (XGBoost & LightGBM). All signals are routed through an unsupervised 6-state Hidden Markov Model (HMM) risk gate to guard against market volatility.

---

## Core Architecture

| Component        | Technology                                                     |
| ---------------- | -------------------------------------------------------------- |
| Framework        | FastAPI (Asynchronous Python)                                  |
| Database         | PostgreSQL / TimescaleDB (time-series optimized)               |
| Caching          | Redis (tiered cache-aside pattern for sub-millisecond latency) |
| Machine Learning | XGBoost, LightGBM, scikit-learn                                |
| Telemetry        | Structured JSON logging for enterprise monitoring              |
| Containerization | Docker (for Redis and future microservices)                    |

---

## Project Structure

```
quantum_flow/
├── api/
│   └── routes.py               # FastAPI endpoints (/train, /predict)
├── core/
│   ├── cache.py                # Redis demand-tiered caching logic
│   └── logger.py               # Structured JSON telemetry
├── db/
│   └── database.py             # SQLAlchemy & TimescaleDB connections
├── exceptions/
│   ├── custom_errors.py        # Domain-specific business logic errors
│   └── handlers.py             # Global API error interceptors
├── models/                     # Stored .pkl files (ML models & scalers)
├── services/
│   ├── feature_engineering.py  # Technical indicator calculations (Pandas-TA)
│   ├── ml_engine.py            # XGBoost/LightGBM training pipeline
│   └── regime_detection.py     # HMM volatility risk gate
├── main.py                     # Uvicorn application entry point
├── .env.example                # Environment variable template
└── requirements.txt            # Python dependencies
```

---

## Installation & Setup

### Prerequisites

- Python 3.10+
- Docker Desktop (for local Redis)
- PostgreSQL database (local or cloud)

### 1. Clone & Environment

```bash
git clone https://github.com/yourusername/quantumflow.git
cd quantumflow
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configuration

Copy the environment template and fill in your database credentials:

```bash
cp .env.example .env
```

Ensure your TimescaleDB instance is running and accessible via the `DATABASE_URL` in your `.env` file.

### 3. Start Redis Cache

Start the local Redis container using Docker:

```bash
docker run -d --name quantum-redis -p 6379:6379 redis:alpine
```

---

## Running the Server

```bash
uvicorn main:app --reload
```

The interactive API documentation (Swagger UI) will be available at `http://127.0.0.1:8000/docs`.

---

## API Endpoints

### `GET /health`

Returns system operational status.

### `POST /train/{symbol}`

Triggers the full ML training pipeline. Fetches historical data, trains the XGBoost/LightGBM ensemble, clusters the HMM regime states, and persists the resulting `.pkl` model files to the `models/` directory.

### `GET /predict/{symbol}`

Returns a live trading signal (`BUY` / `SELL` / `NEUTRAL`) along with the current detected market regime. High-demand symbols are automatically cached in Redis for 60 seconds to ensure sub-millisecond response times.

---

## Disclaimer

This software is for educational and research purposes only and does not constitute financial advice. Do not use these signals for live trading without rigorous backtesting and professional financial consultation. The developers assume no liability for financial losses incurred.
