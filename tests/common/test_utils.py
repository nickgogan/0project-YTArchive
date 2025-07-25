import asyncio
from unittest.mock import AsyncMock


import pytest

from services.common.utils import CircuitBreaker, retry_with_backoff


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_with_backoff():
    """Test that the retry_with_backoff decorator works as expected."""
    mock_func = AsyncMock(side_effect=Exception("Test error"))

    @retry_with_backoff(retries=3, base_delay=0.01)
    async def decorated_func():
        await mock_func()

    with pytest.raises(Exception, match="Test error"):
        await decorated_func()

    assert mock_func.call_count == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_circuit_breaker():
    """Test the CircuitBreaker class state transitions."""
    mock_func = AsyncMock()
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
    decorated_func = breaker(mock_func)

    # State: CLOSED -> OPEN
    mock_func.side_effect = ValueError("Service unavailable")
    with pytest.raises(ValueError):
        await decorated_func()  # First failure
    with pytest.raises(ValueError):
        await decorated_func()  # Second failure, circuit opens

    assert breaker.state == "OPEN"
    assert mock_func.call_count == 2

    # State: OPEN
    with pytest.raises(Exception, match="Circuit is open"):
        await decorated_func()
    assert mock_func.call_count == 2  # Should not be called again

    # State: OPEN -> HALF_OPEN -> CLOSED
    await asyncio.sleep(0.2)  # Wait for recovery timeout
    mock_func.side_effect = None  # The call will now succeed
    await decorated_func()
    assert breaker.state == "CLOSED"
    assert mock_func.call_count == 3
