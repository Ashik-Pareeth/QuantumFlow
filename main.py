from fastapi import FastAPI
from api.routes import router
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

app.include_router(router)


@app.get("/health")
def health_check():
    return {"status": "QuantumFlow Monolith is operational", "phase": 1}


if __name__ == "__main__":
    import uvicorn

    API_HOST = os.getenv("API_HOST")
    API_PORT = int(os.getenv("API_PORT"))

    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)
