"""Comprehensive edge case tests for ErrorRecoveryManager."""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from services.error_recovery.base import (
    ErrorRecoveryManager,
    ErrorContext,
    RetryConfig,
    RetryReason,
)
from services.error_recovery.retry.strategies import ExponentialBackoffStrategy


class MockException(Exception):
    """Mock exception for testing with response attribute."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        if status_code:
            self.response = MagicMock()
            self.response.status_code = status_code


class TestErrorRecoveryManagerEdgeCases:
    """Test ErrorRecoveryManager edge cases and complex scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.retry_strategy = ExponentialBackoffStrategy(RetryConfig(max_attempts=3))
        self.error_reporter = AsyncMock()
        self.service_handler = AsyncMock()
        self.manager = ErrorRecoveryManager(
            retry_strategy=self.retry_strategy,
            error_reporter=self.error_reporter,
            service_handler=self.service_handler,
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_retry_reason_connection_error(self):
        """Test _determine_retry_reason with ConnectionError."""
        context = ErrorContext(
            operation_name="test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        error = ConnectionError("Connection failed")
        reason = self.manager._determine_retry_reason(error, context)
        assert reason == RetryReason.NETWORK_ERROR

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_retry_reason_timeout_error(self):
        """Test _determine_retry_reason with TimeoutError."""
        context = ErrorContext(
            operation_name="test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        error = TimeoutError("Request timed out")
        reason = self.manager._determine_retry_reason(error, context)
        assert reason == RetryReason.NETWORK_ERROR

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_retry_reason_quota_exceeded_case_insensitive(self):
        """Test _determine_retry_reason with quota keywords (case insensitive)."""
        context = ErrorContext(
            operation_name="test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        # Test various case combinations
        quota_messages = [
            "QUOTA exceeded",
            "quota EXCEEDED",
            "Api Quota Limit",
            "daily quota reached",
        ]

        for message in quota_messages:
            error = ValueError(message)
            reason = self.manager._determine_retry_reason(error, context)
            assert (
                reason == RetryReason.API_QUOTA_EXCEEDED
            ), f"Failed for message: {message}"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_retry_reason_rate_limited_case_insensitive(self):
        """Test _determine_retry_reason with rate keywords (case insensitive)."""
        context = ErrorContext(
            operation_name="test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        # Test various rate limiting messages
        rate_messages = [
            "RATE limit exceeded",
            "rate LIMITED",
            "Rate throttling active",
            "request rate too high",
        ]

        for message in rate_messages:
            error = ValueError(message)
            reason = self.manager._determine_retry_reason(error, context)
            assert reason == RetryReason.RATE_LIMITED, f"Failed for message: {message}"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_retry_reason_io_errors(self):
        """Test _determine_retry_reason with IO and OS errors."""
        context = ErrorContext(
            operation_name="test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        # Test IOError
        io_error = IOError("File read failed")
        reason = self.manager._determine_retry_reason(io_error, context)
        assert reason == RetryReason.DOWNLOAD_FAILED

        # Test OSError
        os_error = OSError("Disk full")
        reason = self.manager._determine_retry_reason(os_error, context)
        assert reason == RetryReason.DOWNLOAD_FAILED

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_retry_reason_http_status_codes(self):
        """Test _determine_retry_reason with HTTP status codes."""
        context = ErrorContext(
            operation_name="test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        # Test 503 Service Unavailable
        error_503 = MockException("Service unavailable", 503)
        reason = self.manager._determine_retry_reason(error_503, context)
        assert reason == RetryReason.SERVICE_UNAVAILABLE

        # Test 429 Rate Limited
        error_429 = MockException("Too many requests", 429)
        reason = self.manager._determine_retry_reason(error_429, context)
        assert reason == RetryReason.RATE_LIMITED

        # Test 500+ Server Errors
        for status_code in [500, 501, 502, 504, 505]:
            error = MockException(f"Server error {status_code}", status_code)
            reason = self.manager._determine_retry_reason(error, context)
            assert (
                reason == RetryReason.SERVER_ERROR
            ), f"Failed for status code: {status_code}"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_retry_reason_missing_response_attribute(self):
        """Test _determine_retry_reason with exception missing response attribute."""
        context = ErrorContext(
            operation_name="test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        # Exception without response attribute
        error = Exception("Some error without response")
        reason = self.manager._determine_retry_reason(error, context)
        assert reason == RetryReason.UNKNOWN

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_retry_reason_response_without_status_code(self):
        """Test _determine_retry_reason with response missing status_code."""
        context = ErrorContext(
            operation_name="test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        # Exception with response but no status_code attribute
        error = Exception("Error with response")
        error.response = object()  # Simple object without status_code attribute

        reason = self.manager._determine_retry_reason(error, context)
        assert reason == RetryReason.UNKNOWN

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_retry_reason_unknown_exception(self):
        """Test _determine_retry_reason with unknown exception types."""
        context = ErrorContext(
            operation_name="test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        # Custom exception not covered by logic
        class CustomException(Exception):
            pass

        error = CustomException("Unknown error type")
        reason = self.manager._determine_retry_reason(error, context)
        assert reason == RetryReason.UNKNOWN

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_concurrent_recovery_operations(self):
        """Test multiple concurrent recovery operations."""

        async def mock_function(delay, should_fail=False):
            await asyncio.sleep(delay)
            if should_fail:
                raise Exception("Function failed")
            return f"success_after_{delay}"

        context = ErrorContext(
            operation_name="concurrent_test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        # Start multiple concurrent operations
        tasks = []
        for i in range(5):
            task = asyncio.create_task(
                self.manager.execute_with_retry(
                    mock_function,
                    context,
                    RetryConfig(max_attempts=2),
                    0.01,  # Small delay
                    False,  # Don't fail
                )
            )
            tasks.append(task)

        # Wait for all to complete
        results = await asyncio.gather(*tasks)

        # Verify all succeeded
        for i, result in enumerate(results):
            assert result == "success_after_0.01"

        # Verify active recoveries were cleaned up
        assert len(self.manager.active_recoveries) == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_service_handler_exception_during_error_handling(self):
        """Test behavior when service handler raises exception during error handling."""

        # Configure service handler to raise exception
        self.service_handler.handle_error.side_effect = Exception(
            "Service handler failed"
        )

        call_count = 0

        async def failing_function():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Network error")

        context = ErrorContext(
            operation_name="test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        # Should still retry despite service handler failure
        with pytest.raises(ConnectionError):
            await self.manager.execute_with_retry(
                failing_function, context, RetryConfig(max_attempts=3)
            )

        # Verify function was called the expected number of times
        assert call_count == 3

        # Verify service handler was called
        assert self.service_handler.handle_error.call_count == 3

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_error_reporter_exception_during_reporting(self):
        """Test behavior when error reporter raises exception during reporting."""

        # Configure error reporter to raise exception
        self.error_reporter.report_error.side_effect = Exception(
            "Error reporter failed"
        )

        async def failing_function():
            raise ValueError("Test error")

        context = ErrorContext(
            operation_name="test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        # Should still propagate original exception despite error reporter failure
        with pytest.raises(ValueError, match="Test error"):
            await self.manager.execute_with_retry(
                failing_function, context, RetryConfig(max_attempts=2)
            )

        # Verify error reporter was called
        assert self.error_reporter.report_error.call_count == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_active_recovery_tracking_and_cleanup(self):
        """Test active recovery operation tracking and cleanup."""

        # Track when function starts and ends
        function_started = asyncio.Event()
        function_can_complete = asyncio.Event()

        async def long_running_function():
            function_started.set()
            await function_can_complete.wait()
            return "completed"

        context = ErrorContext(
            operation_name="long_running_test",
            operation_context={"key": "value"},
            timestamp=datetime.now(timezone.utc),
        )

        # Start the recovery operation
        task = asyncio.create_task(
            self.manager.execute_with_retry(
                long_running_function, context, RetryConfig(max_attempts=2)
            )
        )

        # Wait for function to start
        await function_started.wait()

        # Verify active recovery is tracked
        assert len(self.manager.active_recoveries) == 1

        operation_id = list(self.manager.active_recoveries.keys())[0]
        recovery_info = self.manager.active_recoveries[operation_id]

        assert recovery_info["function"] == "long_running_function"
        assert recovery_info["context"] == context
        assert recovery_info["attempts"] == 1
        assert "started_at" in recovery_info

        # Allow function to complete
        function_can_complete.set()
        result = await task

        # Verify cleanup
        assert len(self.manager.active_recoveries) == 0
        assert result == "completed"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_active_recovery_cleanup_on_exception(self):
        """Test active recovery cleanup when operation fails completely."""

        async def always_failing_function():
            raise ValueError("Always fails")

        context = ErrorContext(
            operation_name="failing_test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        # Start operation that will fail
        with pytest.raises(ValueError):
            await self.manager.execute_with_retry(
                always_failing_function, context, RetryConfig(max_attempts=2)
            )

        # Verify cleanup happened even on failure
        assert len(self.manager.active_recoveries) == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_uuid_generation_uniqueness(self):
        """Test that operation IDs are unique across concurrent operations."""

        operation_ids = set()
        ids_lock = asyncio.Lock()

        async def id_tracking_function():
            # Capture operation ID during execution
            async with ids_lock:
                # Find our operation ID
                for op_id in self.manager.active_recoveries.keys():
                    operation_ids.add(op_id)
            return "success"

        context = ErrorContext(
            operation_name="id_test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        # Start many concurrent operations
        tasks = []
        for i in range(10):
            task = asyncio.create_task(
                self.manager.execute_with_retry(
                    id_tracking_function, context, RetryConfig(max_attempts=1)
                )
            )
            tasks.append(task)

        # Wait for all to complete
        await asyncio.gather(*tasks)

        # Verify all operation IDs were unique
        assert len(operation_ids) == 10

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_retry_strategy_record_attempt_success_path(self):
        """Test retry strategy records successful attempts correctly."""

        async def succeeding_function():
            return "success"

        context = ErrorContext(
            operation_name="test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        # Reset strategy state
        self.retry_strategy.total_attempts = 0
        self.retry_strategy.successful_attempts = 0

        result = await self.manager.execute_with_retry(
            succeeding_function, context, RetryConfig(max_attempts=3)
        )

        assert result == "success"
        assert self.retry_strategy.total_attempts == 1
        assert self.retry_strategy.successful_attempts == 1
        assert self.retry_strategy.failed_attempts == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_retry_strategy_record_attempt_failure_path(self):
        """Test retry strategy records failed attempts correctly."""

        async def failing_function():
            raise ConnectionError("Network error")

        context = ErrorContext(
            operation_name="test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        # Reset strategy state
        self.retry_strategy.total_attempts = 0
        self.retry_strategy.failed_attempts = 0

        with pytest.raises(ConnectionError):
            await self.manager.execute_with_retry(
                failing_function, context, RetryConfig(max_attempts=3)
            )

        assert self.retry_strategy.total_attempts == 3
        assert self.retry_strategy.failed_attempts == 3
        assert self.retry_strategy.successful_attempts == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_retry_config_none_uses_default(self):
        """Test that None retry_config uses default configuration."""

        async def succeeding_function():
            return "success"

        context = ErrorContext(
            operation_name="test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        # Pass None for retry_config
        result = await self.manager.execute_with_retry(
            succeeding_function, context, None  # Should use default RetryConfig()
        )

        assert result == "success"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_mixed_exception_types_in_determine_retry_reason(self):
        """Test _determine_retry_reason with mixed exception characteristics."""
        context = ErrorContext(
            operation_name="test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        # ValueError with quota keyword should be API_QUOTA_EXCEEDED
        quota_error = ValueError("API quota exceeded for today")
        reason = self.manager._determine_retry_reason(quota_error, context)
        assert reason == RetryReason.API_QUOTA_EXCEEDED

        # ValueError with rate keyword should be RATE_LIMITED
        rate_error = ValueError("Request rate too high")
        reason = self.manager._determine_retry_reason(rate_error, context)
        assert reason == RetryReason.RATE_LIMITED

        # ValueError without special keywords should be UNKNOWN
        generic_error = ValueError("Generic value error")
        reason = self.manager._determine_retry_reason(generic_error, context)
        assert reason == RetryReason.UNKNOWN

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_function_args_kwargs_preservation(self):
        """Test that function arguments and kwargs are preserved through retries."""

        received_args = []
        received_kwargs = []

        async def argument_tracking_function(*args, **kwargs):
            received_args.append(args)
            received_kwargs.append(kwargs)
            return f"args: {args}, kwargs: {kwargs}"

        context = ErrorContext(
            operation_name="test",
            operation_context={},
            timestamp=datetime.now(timezone.utc),
        )

        # Call with specific args and kwargs
        await self.manager.execute_with_retry(
            argument_tracking_function,
            context,
            RetryConfig(max_attempts=1),
            "arg1",
            "arg2",
            kwarg1="value1",
            kwarg2="value2",
        )

        # Verify arguments were preserved
        assert len(received_args) == 1
        assert len(received_kwargs) == 1
        assert received_args[0] == ("arg1", "arg2")
        assert received_kwargs[0] == {"kwarg1": "value1", "kwarg2": "value2"}
