import json
import redis
from core.logger import get_logger

logger = get_logger(__name__)

# Connect to the Dockerized Redis container
# decode_responses=True ensures we get clean strings back instead of raw bytes
redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

CACHE_TTL = 60  # Cache lives for 60 seconds


def get_cached_signal(symbol: str):
    """Attempts to fetch a cached prediction."""
    try:
        cached_data = redis_client.get(f"signal:{symbol.upper()}")
        if cached_data:
            logger.info(f"⚡ CACHE HIT: Returning cached signal for {symbol}")
            return json.loads(cached_data)
        return None
    except redis.ConnectionError:
        logger.warning("Redis is unreachable. Bypassing cache.")
        return None


def set_cached_signal(symbol: str, payload: dict):
    """Saves a prediction to Redis with a 60-second expiration."""
    try:
        redis_client.setex(
            name=f"signal:{symbol.upper()}", time=CACHE_TTL, value=json.dumps(payload)
        )
        logger.info(f"CACHE SET: Saved signal for {symbol} (Expires in {CACHE_TTL}s)")
    except redis.ConnectionError:
        pass
