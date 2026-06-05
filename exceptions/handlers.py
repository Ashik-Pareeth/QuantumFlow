from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from exceptions.custom_errors import QuantumFlowException
from core.logger import get_logger

logger = get_logger(__name__)


async def custom_domain_exception_handler(request: Request, exc: Exception):
    """Catches our custom business logic errors."""
    if not isinstance(exc, QuantumFlowException):
        raise exc
    logger.warning(
        f"Domain Rule Triggered: {exc.message}",
        extra={"request_path": request.url.path},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "Domain Error", "message": exc.message},
    )


async def validation_exception_handler(request: Request, exc: Exception):
    """Cleans up Pydantic validation arrays."""
    if not isinstance(exc, RequestValidationError):
        raise exc
    simplified_errors = [
        {"field": err.get("loc")[-1], "message": err.get("msg")} for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "Validation Error", "details": simplified_errors},
    )


async def http_exception_handler(request: Request, exc: Exception):
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "Client Error", "message": exc.detail},
    )


async def global_exception_handler(request: Request, exc: Exception):
    """The 500 Catch-All."""
    # This will now output a massive, highly detailed JSON block to your terminal
    logger.error(
        f"CRITICAL SYSTEM ERROR: {repr(exc)}",
        exc_info=True,
        extra={"request_path": request.url.path},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected system error occurred.",
        },
    )
