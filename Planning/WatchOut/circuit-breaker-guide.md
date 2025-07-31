# Circuit Breaker Integration Patterns Guide

This guide provides best practices for using and testing the `CircuitBreakerStrategy` in the YTArchive error recovery system. The circuit breaker is an advanced resilience pattern designed to prevent an application from repeatedly trying to execute an operation that is likely to fail.

## 1. Understanding the Circuit Breaker

The `CircuitBreakerStrategy` acts like an electrical circuit breaker. It monitors for failures, and if they reach a certain threshold, it "trips" or "opens the circuit," causing subsequent calls to fail immediately without even attempting the operation. This prevents the application from wasting resources on a failing service.

### The Three States

1.  **`closed`**: The default state. Operations are executed normally. The breaker counts consecutive failures. If the count exceeds `failure_threshold`, it transitions to `open`.
2.  **`open`**: The circuit is "tripped." All attempts to execute the operation will fail immediately for a duration defined by `recovery_timeout`. After the timeout, the breaker transitions to `half_open`.
3.  **`half_open`**: The circuit allows a single "trial" operation to proceed.
    *   If this trial operation **succeeds**, the breaker resets and transitions back to `closed`.
    *   If this trial operation **fails**, the breaker immediately transitions back to `open`, restarting the `recovery_timeout`.

## 2. Configuration

The `CircuitBreakerStrategy` is configured through the `RetryConfig` model. The key parameters are:

*   **`failure_threshold`**: The number of *consecutive* failures required to open the circuit. (e.g., `3`)
*   **`recovery_timeout`**: The duration in seconds that the circuit will remain open before transitioning to `half_open`. (e.g., `60.0`)
*   **`max_attempts`**: The total number of retries allowed when the circuit is `closed` or `half_open`.

```python
# Example configuration for a circuit breaker
from services.error_recovery.types import RetryConfig
from services.error_recovery.retry import CircuitBreakerStrategy

circuit_breaker_config = RetryConfig(
    max_attempts=5,          # Max attempts when closed/half-open
    failure_threshold=3,     # Open after 3 consecutive failures
    recovery_timeout=60.0,   # Stay open for 60 seconds
    base_delay=1.0           # Standard backoff delay
)

strategy = CircuitBreakerStrategy(circuit_breaker_config)
```

## 3. How to Test the Circuit Breaker

Testing the circuit breaker requires careful isolation of the failing operation. A common pitfall is allowing other, successful operations to run within the same test, as they can inadvertently reset the circuit breaker's internal failure count.

### The Failure Count Reset Pitfall

**Problem**: In our early tests, the circuit breaker's `failure_count` was being reset to zero by successful, unrelated operations (like reporting status) that were part of the same workflow. This prevented the circuit from ever opening, even when the main operation was persistently failing.

**Solution**: Isolate the failing operation. In your test, ensure that the `ErrorRecoveryManager` *only* executes the function that is supposed to fail. Mock any other operations that would normally occur in the workflow.

### Standard Testing Pattern

This pattern, taken from `test_download_service_retry_integration.py`, demonstrates the correct way to test the circuit breaker.

```python
import pytest
from unittest.mock import patch, AsyncMock
from services.error_recovery import ErrorRecoveryManager
from services.error_recovery.retry import CircuitBreakerStrategy
from services.error_recovery.types import ErrorContext, RetryConfig

@pytest.mark.integration
@pytest.mark.asyncio
async def test_circuit_breaker_opens_on_persistent_failure(self):
    """Verify that the circuit breaker opens after persistent failures."""

    # 1. Configure the circuit breaker for a fast test
    retry_config = RetryConfig(
        max_attempts=10,       # Allow enough attempts to trip
        failure_threshold=3,   # Trip after 3 failures
        base_delay=0.01        # Use a small delay
    )
    strategy = CircuitBreakerStrategy(retry_config)
    manager = ErrorRecoveryManager(
        retry_strategy=strategy,
        error_reporter=AsyncMock(), # Mock the reporter
        service_handler=DownloadErrorHandler()
    )

    # 2. Mock the operation to *always* fail
    async def always_failing_operation(*args, **kwargs):
        raise ConnectionError("Persistent network failure")

    # 3. Patch the specific failing method on the service
    with patch.object(
        self.download_service,
        "_download_video",
        side_effect=always_failing_operation,
    ) as mock_download:

        # 4. Isolate the call: Mock other methods in the workflow to prevent them
        # from resetting the failure counter.
        with patch.object(self.download_service, "_get_storage_path", return_value="/tmp"):

            # 5. Execute the operation via the manager
            with pytest.raises(ConnectionError):
                await manager.execute_with_retry(
                    self.download_service._download_video,
                    ErrorContext(operation_name="test_download"),
                    retry_config,
                    # ...args for _download_video
                )

            # 6. Assert the state of the circuit breaker
            assert strategy.state == "open"
            assert strategy.failure_count >= retry_config.failure_threshold

            # The operation should have been called 'failure_threshold' times
            assert mock_download.call_count == retry_config.failure_threshold
```

## 4. Best Practices for Using Circuit Breakers

1.  **Use for High-Cost Failures**: The circuit breaker is most effective for operations that are resource-intensive and have a high probability of remaining unavailable for a period (e.g., calls to a downed external service, database connections).

2.  **Tune Thresholds Carefully**:
    *   A low `failure_threshold` makes the system very sensitive and can trip the circuit on transient blips.
    *   A high `recovery_timeout` can lead to long periods of unavailability.
    *   Start with conservative values (e.g., 5 failures, 60-second timeout) and adjust based on production monitoring.

3.  **Isolate Operations**: As demonstrated in the testing pattern, ensure that the circuit breaker is tracking failures for the correct, isolated operation. Avoid using a single `ErrorRecoveryManager` instance for many different types of operations if they have different failure characteristics.

4.  **Provide User Feedback**: When a circuit is open, the system should provide immediate, clear feedback to the user (e.g., "Service is temporarily unavailable, please try again later") instead of making them wait for a timeout.
