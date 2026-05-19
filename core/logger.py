import logging
import json
from datetime import datetime, timezone
import traceback


class QuantumFlowJSONFormatter(logging.Formatter):
    """Formats standard Python logs into enterprise-grade JSON."""

    def format(self, record: logging.LogRecord) -> str:
        # Build the structured payload
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "path": getattr(record, "request_path", "SYSTEM"),
        }

        # If the logger caught an exception, extract the exact line of code that failed
        if record.exc_info:
            log_record["error_trace"] = traceback.format_exception(*record.exc_info)

        return json.dumps(log_record)


def get_logger(name: str = "QuantumFlow"):
    """Initializes the JSON logger."""
    logger = logging.getLogger(name)

    # Prevent duplicate log entries if this function is called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(QuantumFlowJSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Stop logs from bubbling up to Uvicorn's default messy logger
        logger.propagate = False

    return logger
