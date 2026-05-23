import json
from unittest.mock import patch
from core.cache import get_cached_signal, set_cached_signal


@patch("core.cache.redis_client")
def test_cache_high_demand_symbol(mock_redis):
    """Proves that a high-demand stock (AAPL) successfully triggers a Redis save."""
    # 1. Arrange
    symbol = "AAPL"
    payload = {"signal": "BUY", "confidence": 85.0}

    # 2. Act
    set_cached_signal(symbol, payload)

    # 3. Assert
    # Verify setex was called exactly once
    mock_redis.setex.assert_called_once()

    # Extract the exact arguments passed to Redis to ensure they match our architecture
    called_args, called_kwargs = mock_redis.setex.call_args
    assert called_kwargs["name"] == "signal:AAPL"
    assert called_kwargs["time"] == 60
    assert called_kwargs["value"] == json.dumps(payload)


@patch("core.cache.redis_client")
def test_cache_low_demand_symbol(mock_redis):
    """Proves that a low-demand stock (ZBRA) is intentionally ignored by
    Redis to save RAM."""
    # 1. Arrange
    symbol = "ZBRA"  # Not in the HIGH_DEMAND_SYMBOLS set
    payload = {"signal": "SELL", "confidence": 90.0}

    # 2. Act
    set_cached_signal(symbol, payload)

    # 3. Assert
    # Mathematically prove that Redis was NEVER called
    mock_redis.setex.assert_not_called()


@patch("core.cache.redis_client")
def test_get_cached_signal_hit(mock_redis):
    """Proves that fetching an existing signal correctly decodes the JSON payload."""
    # 1. Arrange
    symbol = "BTC"
    fake_payload = {"signal": "NEUTRAL"}
    mock_redis.get.return_value = json.dumps(fake_payload)

    # 2. Act
    result = get_cached_signal(symbol)

    # 3. Assert
    mock_redis.get.assert_called_once_with("signal:BTC")
    assert result == fake_payload


@patch("core.cache.redis_client")
def test_get_cached_signal_miss(mock_redis):
    """Proves that requesting a missing symbol safely returns None without crashing."""
    # 1. Arrange
    mock_redis.get.return_value = None

    # 2. Act
    result = get_cached_signal("UNKNOWN")

    # 3. Assert
    assert result is None
