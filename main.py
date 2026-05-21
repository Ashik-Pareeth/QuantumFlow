from fastapi import FastAPI
from api import data, ml, trading, portfolio, gamification, auth
import os

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from exceptions.custom_errors import QuantumFlowException
from exceptions.handlers import (
    custom_domain_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    global_exception_handler,
)

app = FastAPI(
    title="QuantumFlow AI",
    description="Real-time market intelligence monolith",
    version="1.0.0",
)

app.add_exception_handler(QuantumFlowException, custom_domain_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

app.include_router(data.router, prefix="/api/v1/data", tags=["Market Data"])
app.include_router(ml.router, prefix="/api/v1/ml", tags=["Machine Learning Engine"])
app.include_router(trading.router, prefix="/api/v1/trade", tags=["Trading Execution"])
app.include_router(
    portfolio.router, prefix="/api/v1/portfolio", tags=["User Portfolio"]
)
app.include_router(
    gamification.router, prefix="/api/v1/game", tags=["Gamification & Leaderboard"]
)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication & Users"])


@app.get("/health")
def health_check():
    return {"status": "QuantumFlow Monolith is operational", "phase": 1}


if __name__ == "__main__":
    import uvicorn

    API_HOST = os.getenv("API_HOST")
    API_PORT = int(os.getenv("API_PORT"))

    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)
