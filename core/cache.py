import json
import redis
from core.logger import get_logger
from core.config import settings

logger = get_logger(__name__)


# Connect to the Dockerized Redis container
# decode_responses=True ensures we get clean strings back instead of raw bytes
redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=0,
    decode_responses=True,
)


CACHE_TTL = settings.cache_ttl_seconds
HIGH_DEMAND_SYMBOLS = {"AAPL", "NVDA", "TSLA", "SPY", "QQQ", "BTC"}


def get_cached_signal(symbol: str):
    """Attempts to fetch a cached prediction."""
    try:
        cached_data = redis_client.get(f"signal:{symbol.upper()}")
        if cached_data:
            logger.info(f"CACHE HIT: Returning cached signal for {symbol}")
            return json.loads(cached_data)
        return None
    except redis.ConnectionError:
        logger.warning("Redis is unreachable. Bypassing cache.")
        return None


def set_cached_signal(symbol: str, payload: dict):
    """Saves predictions, but only if they are high-demand or require it."""

    symbol_upper = symbol.upper()

    if symbol_upper not in HIGH_DEMAND_SYMBOLS:
        logger.info(f"CACHE BYPASS: {symbol_upper} is low demand. Skipping Redis.")
        return  # Exit the function without saving to memory

    try:
        redis_client.setex(
            name=f"signal:{symbol_upper}", time=CACHE_TTL, value=json.dumps(payload)
        )
        logger.info(f"CACHE SET: Saved signal for {symbol} (Expires in {CACHE_TTL}s)")
    except redis.ConnectionError:
        pass
