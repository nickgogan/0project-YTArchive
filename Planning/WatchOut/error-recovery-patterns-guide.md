# Error Recovery Patterns Guide

This guide provides comprehensive patterns and best practices for implementing and using the YTArchive error recovery system, covering retry strategies, service handlers, and common integration issues.

## System Overview

### Architecture Components

```
ErrorRecoveryManager
├── RetryStrategy (ExponentialBackoff, CircuitBreaker, Adaptive, FixedDelay)
├── ErrorReporter (BasicErrorReporter)
└── ServiceErrorHandler (DownloadErrorHandler, MetadataErrorHandler, etc.)
```

### Key Classes and Interfaces

1. **`ErrorRecoveryManager`** - Central coordinator for all retry operations
2. **`RetryStrategy`** - Abstract strategy for retry logic and timing
3. **`ServiceErrorHandler`** - Service-specific error classification and recovery
4. **`ErrorReporter`** - Error logging and reporting interface
5. **`ErrorContext`** - Context information for error operations
6. **`RetryConfig`** - Configuration for retry behavior

## Core Patterns

### 1. Basic Retry Pattern

```python
from services.error_recovery import ErrorRecoveryManager
from services.error_recovery.retry import ExponentialBackoffStrategy
from services.error_recovery.reporting import BasicErrorReporter
from services.error_recovery.types import ErrorContext, RetryConfig

# Set up error recovery components
retry_config = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=60.0,
    jitter=True,
    exponential_base=2.0
)

strategy = ExponentialBackoffStrategy(retry_config)
reporter = BasicErrorReporter()
manager = ErrorRecoveryManager(
    retry_strategy=strategy,
    error_reporter=reporter
)

# Create error context
context = ErrorContext(
    operation_name="download_video",
    operation_context={
        "video_id": "test-123",
        "quality": "1080p"
    },
    service_name="download"
)

# Execute operation with retry
async def risky_operation():
    # Your operation that might fail
    return await download_video("test-123")

result = await manager.execute_with_retry(
    risky_operation,
    context,
    retry_config  # Optional override
)
```

### 2. Service-Specific Error Handler Pattern

```python
from services.error_recovery.contracts import ServiceErrorHandler
from services.error_recovery.types import ErrorContext, RetryReason

class CustomServiceErrorHandler(ServiceErrorHandler):
    """Example service-specific error handler."""

    async def handle_error(self, exception: Exception, context: ErrorContext) -> bool:
        """
        Handle service-specific errors.

        Returns:
            bool: True if error was handled, False if should continue normal retry
        """
        error_msg = str(exception).lower()

        # Handle specific error types
        if "network" in error_msg or "timeout" in error_msg:
            logger.warning(f"Network error in {context.operation_name}: {exception}")
            return False  # Continue retry

        if "quota exceeded" in error_msg:
            logger.error(f"API quota exceeded: {exception}")
            # Could implement quota backoff here
            return False  # Continue retry with longer delays

        if "unauthorized" in error_msg:
            logger.critical(f"Authentication failure: {exception}")
            return True  # Stop retry - auth won't fix itself

        return False  # Default: continue retry

    def get_recovery_suggestions(self, exception: Exception) -> List[str]:
        """Provide human-readable recovery suggestions."""
        error_msg = str(exception).lower()
        suggestions = []

        if "network" in error_msg:
            suggestions.append("Check network connectivity")
            suggestions.append("Verify proxy settings if using proxy")

        if "disk" in error_msg or "space" in error_msg:
            suggestions.append("Check available disk space in output directory")
            suggestions.append("Clean up temporary files")

        if "permission" in error_msg:
            suggestions.append("Check file system permissions")
            suggestions.append("Verify write access to output directory")

        return suggestions or ["Review error logs for more details"]

# Integration with ErrorRecoveryManager
handler = CustomServiceErrorHandler()
manager = ErrorRecoveryManager(
    retry_strategy=strategy,
    error_reporter=reporter,
    service_handler=handler  # Add service handler
)
```

### 3. Circuit Breaker Pattern

```python
from services.error_recovery.retry import CircuitBreakerStrategy

# Configure circuit breaker
circuit_config = RetryConfig(
    max_attempts=5,
    base_delay=1.0,
    failure_threshold=3,  # Open after 3 consecutive failures
    recovery_timeout=60.0  # Wait 60s before trying again
)

strategy = CircuitBreakerStrategy(circuit_config)
manager = ErrorRecoveryManager(
    retry_strategy=strategy,
    error_reporter=reporter,
    service_handler=handler
)

# Circuit breaker will:
# 1. Allow normal retries up to failure_threshold
# 2. Open circuit after consecutive failures
# 3. Reject requests during recovery_timeout
# 4. Try half-open state after timeout
# 5. Close circuit on successful operation
```

### 4. Adaptive Strategy Pattern

```python
from services.error_recovery.retry import AdaptiveStrategy

# Configure adaptive strategy
adaptive_config = RetryConfig(
    max_attempts=10,
    base_delay=0.5,
    max_delay=120.0
)

strategy = AdaptiveStrategy(
    config=adaptive_config,
    window_size=50,  # Track last 50 attempts
    success_threshold=0.7  # Adapt if success rate < 70%
)

# Adaptive strategy will:
# - Track success rates in sliding window
# - Increase delays if success rate is low
# - Decrease delays if success rate is high
# - Dynamically adjust based on recent performance
```

## Common Issues and Solutions

### Issue 1: Retry Configuration Not Used

**Problem**: Error recovery uses default config instead of strategy's config

```python
# ❌ WRONG - This causes the issue
retry_config = retry_config or RetryConfig()  # Always creates new config!

# ✅ CORRECT - Use strategy's config
if retry_config is None:
    strategy_config = getattr(self.retry_strategy, "config", None)
    retry_config = (
        strategy_config if isinstance(strategy_config, RetryConfig)
        else RetryConfig()
    )
```

**Root Cause**: The `or` operator creates a new `RetryConfig()` even when strategy has its own config.

**Solution**: Check strategy's config attribute explicitly and validate type.

### Issue 2: Service Handler Interface Compliance

**Problem**: Service handlers not implementing required interface methods

```python
# ❌ WRONG - Missing method or wrong signature
class BadHandler(ServiceErrorHandler):
    def handle_error(self, exception: Exception) -> Dict:  # Wrong signature!
        return {"handled": True}

    # Missing get_recovery_suggestions method!

# ✅ CORRECT - Full interface implementation
class GoodHandler(ServiceErrorHandler):
    async def handle_error(self, exception: Exception, context: ErrorContext) -> bool:
        # Proper async method with correct signature
        return False

    def get_recovery_suggestions(self, exception: Exception) -> List[str]:
        # Required method implementation
        return ["Check logs for details"]
```

**Root Cause**: Interface not fully implemented or wrong method signatures.

**Solution**: Always implement full `ServiceErrorHandler` interface with correct signatures.

### Issue 3: Circuit Breaker Failure Counting

**Problem**: Circuit breaker failure count reset by unrelated operations

```python
# ❌ WRONG - This resets failure count
async def problematic_test():
    # Main operation fails
    await manager.execute_with_retry(failing_operation, context, config)

    # But this successful operation resets circuit breaker
    await some_other_successful_operation()

    # Circuit breaker state is now inconsistent

# ✅ CORRECT - Isolate operations or mock non-failing parts
async def proper_test():
    # Mock unrelated successful operations
    with patch.object(service, 'other_operation', return_value="success"):
        # Now circuit breaker only sees the failing operation
        await manager.execute_with_retry(failing_operation, context, config)
```

**Root Cause**: Circuit breaker tracks all operations, not just the specific failing one.

**Solution**: Mock successful operations or use separate error recovery managers for different operation types.

### Issue 4: Error Context Field Names

**Problem**: Using wrong field names in `ErrorContext`

```python
# ❌ WRONG - Old field names
context = ErrorContext(
    operation="download",  # Should be operation_name
    context={"video_id": "123"}  # Should be operation_context
)

# ✅ CORRECT - Current field names
context = ErrorContext(
    operation_name="download_video",
    operation_context={"video_id": "123", "quality": "1080p"},
    service_name="download",
    video_id="123"  # Can also be explicit
)
```

**Root Cause**: Field names changed during refactoring but some code wasn't updated.

**Solution**: Use current field names as defined in `ErrorContext` model.

## Advanced Patterns

### 1. Multi-Level Retry Coordination

```python
# Pattern for coordinating retries across service boundaries
class JobsServiceWithRetry:
    def __init__(self):
        # Jobs service has its own error recovery
        self.error_manager = ErrorRecoveryManager(
            retry_strategy=ExponentialBackoffStrategy(RetryConfig(max_attempts=5)),
            error_reporter=BasicErrorReporter()
        )

    async def orchestrate_download(self, video_id: str):
        """Jobs service orchestrating download with retry coordination."""
        context = ErrorContext(
            operation_name="orchestrate_download",
            operation_context={"video_id": video_id},
            service_name="jobs"
        )

        # Jobs-level retry wraps the entire operation
        return await self.error_manager.execute_with_retry(
            self._coordinate_download_services,
            context,
            None,  # Use strategy's config
            video_id
        )

    async def _coordinate_download_services(self, video_id: str):
        """Internal coordination logic - downstream services have own retry."""
        # Each service has its own retry logic
        metadata = await metadata_service.get_metadata(video_id)  # May retry internally
        storage_path = await storage_service.get_path(video_id)    # May retry internally
        result = await download_service.download(video_id, storage_path)  # May retry internally
        return result
```

### 2. Custom Retry Reason Handling

```python
from services.error_recovery.types import RetryReason

class SmartRetryStrategy(ExponentialBackoffStrategy):
    """Custom strategy with reason-specific behavior."""

    async def get_delay(self, attempt: int, reason: RetryReason) -> float:
        """Custom delay calculation based on retry reason."""
        base_delay = await super().get_delay(attempt, reason)

        # Longer delays for quota/rate limiting
        if reason in [RetryReason.API_QUOTA_EXCEEDED, RetryReason.RATE_LIMITED]:
            return base_delay * 3.0

        # Shorter delays for network errors
        if reason == RetryReason.NETWORK_ERROR:
            return base_delay * 0.5

        # Much longer delays for service unavailable
        if reason == RetryReason.SERVICE_UNAVAILABLE:
            return base_delay * 5.0

        return base_delay

    async def should_retry(self, attempt: int, exception: Exception, reason: RetryReason) -> bool:
        """Custom retry logic based on reason."""
        # Never retry these permanent errors
        permanent_reasons = {
            RetryReason.QUALITY_NOT_AVAILABLE,
        }

        if reason in permanent_reasons:
            return False

        # Custom retry limits for different reasons
        if reason == RetryReason.API_QUOTA_EXCEEDED and attempt >= 2:
            return False  # Only retry quota errors twice

        return await super().should_retry(attempt, exception, reason)
```

### 3. Integration Testing Pattern

```python
@pytest.mark.asyncio
async def test_error_recovery_integration():
    """Proper integration test setup for error recovery."""

    # Set up error recovery components
    retry_config = RetryConfig(max_attempts=3, base_delay=0.01)
    strategy = ExponentialBackoffStrategy(retry_config)
    error_handler = DownloadErrorHandler()
    reporter = AsyncMock()  # Mock reporter to avoid I/O

    manager = ErrorRecoveryManager(
        retry_strategy=strategy,
        error_reporter=reporter,
        service_handler=error_handler
    )

    # Mock the service being tested
    mock_service = AsyncMock()

    # Configure failure then success pattern
    mock_service._download_video.side_effect = [
        ConnectionError("Network timeout"),  # First attempt fails
        ConnectionError("Connection refused"),  # Second attempt fails
        {"status": "success", "path": "/tmp/video.mp4"}  # Third attempt succeeds
    ]

    # Mock storage path to avoid HTTP calls
    with patch.object(mock_service, '_get_storage_path', return_value="/tmp/test"):
        context = ErrorContext(
            operation_name="download_video",
            operation_context={"video_id": "test-123"},
            service_name="download"
        )

        # Execute with retry
        result = await manager.execute_with_retry(
            mock_service._download_video,
            context,
            retry_config,
            "test-123",
            "1080p",
            "/tmp/test"
        )

        # Verify retry behavior
        assert mock_service._download_video.call_count == 3
        assert result["status"] == "success"

        # Verify error reporting
        assert reporter.report_error.call_count == 2  # Two failures reported
```

## Testing Best Practices

### 1. Mock External Dependencies

```python
# Always mock HTTP calls and I/O operations
with patch.object(service, '_get_storage_path', return_value="/tmp/test"):
    with patch.object(service, '_report_job_status', return_value=None):
        # Your retry test here
        pass
```

### 2. Use Fast Delays in Tests

```python
# Use small delays for fast test execution
test_config = RetryConfig(
    max_attempts=3,
    base_delay=0.01,  # 10ms instead of 1s
    max_delay=0.1,    # 100ms instead of 60s
    jitter=False      # Consistent timing for tests
)
```

### 3. Verify Retry Behavior

```python
# Check that retry actually happened
assert mock_operation.call_count == expected_attempts

# Check error reporting
assert error_reporter.report_error.call_count == expected_failures

# Check strategy metrics
assert strategy.total_attempts == expected_total
assert strategy.successful_attempts == expected_successes
```

## Configuration Guidelines

### Development Configuration
```python
# Fast, verbose retries for development
dev_config = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=10.0,
    jitter=True
)
```

### Production Configuration
```python
# Robust, conservative retries for production
prod_config = RetryConfig(
    max_attempts=5,
    base_delay=2.0,
    max_delay=300.0,  # 5 minutes max
    jitter=True,
    failure_threshold=5,
    recovery_timeout=120.0
)
```

### Testing Configuration
```python
# Fast, predictable retries for tests
test_config = RetryConfig(
    max_attempts=3,
    base_delay=0.01,
    max_delay=0.1,
    jitter=False
)
```

## Performance Considerations

1. **Memory Usage**: Adaptive strategy with large windows can use significant memory
2. **CPU Overhead**: Error classification has minimal overhead but shouldn't be in tight loops
3. **Network Impact**: Exponential backoff prevents overwhelming failing services
4. **Monitoring**: Error reporting helps identify systematic issues

## Debugging Checklist

When error recovery isn't working:

- [ ] Verify `ServiceErrorHandler` implements full interface
- [ ] Check `ErrorContext` uses correct field names
- [ ] Confirm retry config is being used (not defaults)
- [ ] Validate error classification logic
- [ ] Mock external dependencies in tests
- [ ] Use appropriate delays for environment
- [ ] Check circuit breaker state isn't reset by other operations
- [ ] Verify async/await usage is correct

---

This guide should resolve most error recovery implementation issues and provide patterns for robust error handling across YTArchive services.
