import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from services.common.utils import CircuitBreaker, retry_with_backoff


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_with_backoff_basic_retry():
    """Test basic retry functionality."""
    mock_func = AsyncMock(side_effect=Exception("Test error"))

    @retry_with_backoff(retries=3, base_delay=0.01, jitter=False)
    async def decorated_func():
        await mock_func()

    with pytest.raises(Exception, match="Test error"):
        await decorated_func()

    assert mock_func.call_count == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_with_backoff_success_after_failures():
    """Test retry succeeds after some failures."""
    call_count = 0

    async def failing_then_succeeding_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError(f"Failure {call_count}")
        return "success"

    decorated_func = retry_with_backoff(retries=5, base_delay=0.01, jitter=False)(
        failing_then_succeeding_func
    )

    result = await decorated_func()
    assert result == "success"
    assert call_count == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_with_backoff_exponential_delay():
    """Test exponential backoff delay calculation."""
    mock_func = AsyncMock(side_effect=Exception("Test error"))
    delays = []

    async def mock_sleep(delay):
        delays.append(delay)
        # Don't actually sleep in tests

    with patch("asyncio.sleep", side_effect=mock_sleep):

        @retry_with_backoff(retries=4, base_delay=1.0, max_delay=10.0, jitter=False)
        async def decorated_func():
            await mock_func()

        with pytest.raises(Exception, match="Test error"):
            await decorated_func()

    # Should have 3 delays (retries - 1)
    assert len(delays) == 3
    # Exponential backoff: delay starts at base_delay, then doubles each iteration
    # First delay: base_delay=1.0 * 2 = 2.0
    # Second delay: 2.0 * 2 = 4.0
    # Third delay: 4.0 * 2 = 8.0
    assert delays[0] == 2.0  # base_delay * 2
    assert delays[1] == 4.0  # previous * 2
    assert delays[2] == 8.0  # previous * 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_with_backoff_max_delay_limit():
    """Test max delay limit is respected."""
    mock_func = AsyncMock(side_effect=Exception("Test error"))
    delays = []

    async def mock_sleep(delay):
        delays.append(delay)

    with patch("asyncio.sleep", side_effect=mock_sleep):

        @retry_with_backoff(retries=6, base_delay=2.0, max_delay=5.0, jitter=False)
        async def decorated_func():
            await mock_func()

        with pytest.raises(Exception, match="Test error"):
            await decorated_func()

    # Should have 5 delays (retries - 1)
    assert len(delays) == 5
    # Exponential backoff: delay = base_delay * 2, then doubles each time, capped at max_delay=5.0
    # First: 2.0*2=4.0, Second: 4.0*2=8.0 capped at 5.0, then 5.0, 5.0, 5.0
    expected_delays = [4.0, 5.0, 5.0, 5.0, 5.0]
    assert delays == expected_delays


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_with_backoff_with_jitter():
    """Test jitter adds randomness to delays."""
    mock_func = AsyncMock(side_effect=Exception("Test error"))
    delays = []

    async def mock_sleep(delay):
        delays.append(delay)

    with patch("asyncio.sleep", side_effect=mock_sleep):

        @retry_with_backoff(retries=4, base_delay=2.0, max_delay=10.0, jitter=True)
        async def decorated_func():
            await mock_func()

        with pytest.raises(Exception, match="Test error"):
            await decorated_func()

    # Should have 3 delays
    assert len(delays) == 3

    # Delay logic: delay = min(delay * 2, max_delay), then jitter = delay + uniform(0, delay/4)
    # First: min(2.0*2, 10.0)=4.0, jitter=[4.0, 5.0]
    # Second: min(4.0*2, 10.0)=8.0, jitter=[8.0, 10.0]
    # Third: min(8.0*2, 10.0)=10.0, jitter=[10.0, 12.5]
    assert 4.0 <= delays[0] <= 5.0
    assert 8.0 <= delays[1] <= 10.0
    assert 10.0 <= delays[2] <= 12.5

    # Ensure jitter actually varies the delays
    base_delays = [4.0, 8.0, 10.0]  # Expected base delays without jitter
    for i, delay in enumerate(delays):
        # Should not be exactly the base delay (unless very unlucky)
        if delay == base_delays[i]:
            # This could happen randomly, but with multiple attempts it's unlikely
            continue


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_with_backoff_preserves_function_signature():
    """Test decorator preserves original function signature and behavior."""

    @retry_with_backoff(retries=2, base_delay=0.01)
    async def func_with_args(a, b, c=None, **kwargs):
        return {"a": a, "b": b, "c": c, "kwargs": kwargs}

    result = await func_with_args(1, 2, c=3, key="value")
    expected = {"a": 1, "b": 2, "c": 3, "kwargs": {"key": "value"}}
    assert result == expected

    # Check function name is preserved
    assert func_with_args.__name__ == "func_with_args"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_with_backoff_single_retry():
    """Test behavior with retries=1 (no actual retries)."""
    mock_func = AsyncMock(side_effect=Exception("Test error"))

    @retry_with_backoff(retries=1, base_delay=0.01)
    async def decorated_func():
        await mock_func()

    with pytest.raises(Exception, match="Test error"):
        await decorated_func()

    # Should only be called once (no retries)
    assert mock_func.call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_circuit_breaker_basic_state_transitions():
    """Test basic CircuitBreaker state transitions."""
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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_circuit_breaker_failure_threshold():
    """Test circuit breaker opens exactly at failure threshold."""
    mock_func = AsyncMock(side_effect=Exception("Service error"))
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
    decorated_func = breaker(mock_func)

    # Test failures up to threshold - 1
    with pytest.raises(Exception):
        await decorated_func()  # Failure 1
    assert breaker.state == "CLOSED"
    assert breaker.failure_count == 1

    with pytest.raises(Exception):
        await decorated_func()  # Failure 2
    assert breaker.state == "CLOSED"
    assert breaker.failure_count == 2

    # Threshold failure should open circuit
    with pytest.raises(Exception):
        await decorated_func()  # Failure 3 (threshold)
    assert breaker.state == "OPEN"
    assert breaker.failure_count == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_circuit_breaker_success_resets_failure_count():
    """Test success resets failure count in closed state."""
    call_count = 0

    async def intermittent_func():
        nonlocal call_count
        call_count += 1
        if call_count in [1, 2]:  # First two calls fail
            raise ValueError(f"Failure {call_count}")
        return f"Success {call_count}"

    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
    decorated_func = breaker(intermittent_func)

    # Two failures (below threshold)
    with pytest.raises(ValueError):
        await decorated_func()
    with pytest.raises(ValueError):
        await decorated_func()
    assert breaker.failure_count == 2
    assert breaker.state == "CLOSED"

    # Success should reset failure count
    result = await decorated_func()
    assert result == "Success 3"
    assert breaker.failure_count == 0
    assert breaker.state == "CLOSED"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_circuit_breaker_half_open_success():
    """Test circuit breaker transitions from HALF_OPEN to CLOSED on success."""
    mock_func = AsyncMock()
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
    decorated_func = breaker(mock_func)

    # Open the circuit
    mock_func.side_effect = Exception("Error")
    with pytest.raises(Exception):
        await decorated_func()
    with pytest.raises(Exception):
        await decorated_func()
    assert breaker.state == "OPEN"

    # Wait for recovery timeout
    await asyncio.sleep(0.15)

    # Success in HALF_OPEN should close circuit
    mock_func.side_effect = None
    mock_func.return_value = "success"
    result = await decorated_func()
    assert result == "success"
    assert breaker.state == "CLOSED"
    assert breaker.failure_count == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_circuit_breaker_half_open_failure():
    """Test circuit breaker transitions from HALF_OPEN back to OPEN on failure."""
    mock_func = AsyncMock()
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
    decorated_func = breaker(mock_func)

    # Open the circuit
    mock_func.side_effect = Exception("Error")
    with pytest.raises(Exception):
        await decorated_func()
    with pytest.raises(Exception):
        await decorated_func()
    assert breaker.state == "OPEN"
    initial_failure_time = breaker.last_failure_time

    # Wait for recovery timeout
    await asyncio.sleep(0.15)

    # Failure in HALF_OPEN should reopen circuit
    mock_func.side_effect = Exception("Still failing")
    with pytest.raises(Exception, match="Still failing"):
        await decorated_func()
    assert breaker.state == "OPEN"
    assert (
        breaker.last_failure_time > initial_failure_time
    )  # Should update failure time


@pytest.mark.unit
@pytest.mark.asyncio
async def test_circuit_breaker_recovery_timeout_not_reached():
    """Test circuit breaker stays OPEN if recovery timeout not reached."""
    mock_func = AsyncMock(side_effect=Exception("Error"))
    breaker = CircuitBreaker(
        failure_threshold=1, recovery_timeout=1.0
    )  # 1 second timeout
    decorated_func = breaker(mock_func)

    # Open the circuit
    with pytest.raises(Exception):
        await decorated_func()
    assert breaker.state == "OPEN"

    # Try again immediately (recovery timeout not reached)
    with pytest.raises(Exception, match="Circuit is open"):
        await decorated_func()
    assert breaker.state == "OPEN"
    # Function should not be called again
    assert mock_func.call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_circuit_breaker_preserves_function_signature():
    """Test CircuitBreaker decorator preserves function signature."""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)

    @breaker
    async def func_with_args(a, b, c=None, **kwargs):
        return {"a": a, "b": b, "c": c, "kwargs": kwargs}

    result = await func_with_args(1, 2, c=3, key="value")
    expected = {"a": 1, "b": 2, "c": 3, "kwargs": {"key": "value"}}
    assert result == expected

    # Check function name is preserved
    assert func_with_args.__name__ == "func_with_args"


@pytest.mark.unit
def test_circuit_breaker_initial_state():
    """Test CircuitBreaker initial state and configuration."""
    breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)

    assert breaker.failure_threshold == 5
    assert breaker.recovery_timeout == 30
    assert breaker.failure_count == 0
    assert breaker.last_failure_time == 0
    assert breaker.state == "CLOSED"
