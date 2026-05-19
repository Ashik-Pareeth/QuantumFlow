import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from exceptions.custom_errors import QuantumFlowException

logger = logging.getLogger(__name__)


async def custom_domain_exception_handler(request: Request, exc: QuantumFlowException):
    """Catches our custom business logic errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "Domain Error", "message": exc.message},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Cleans up Pydantic validation arrays."""
    simplified_errors = [
        {"field": err.get("loc")[-1], "message": err.get("msg")} for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "Validation Error", "details": simplified_errors},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "Client Error", "message": exc.detail},
    )


async def global_exception_handler(request: Request, exc: Exception):
    """The 500 Catch-All."""
    logger.error(
        f"CRITICAL SYSTEM ERROR at {request.url.path}: {repr(exc)}", exc_info=True
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected system error occurred.",
        },
    )
