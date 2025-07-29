"""Tests for the error recovery library."""

import asyncio
import pytest
from unittest.mock import AsyncMock

from services.error_recovery import ErrorRecoveryManager
from services.error_recovery.retry import (
    ExponentialBackoffStrategy,
    CircuitBreakerStrategy,
)
from services.error_recovery.reporting import BasicErrorReporter
from services.error_recovery.types import (
    RetryConfig,
    ErrorContext,
    ErrorSeverity,
    RetryReason,
)


class TestRetryStrategies:
    """Test retry strategy implementations."""

    def test_exponential_backoff_delay_calculation(self):
        """Test exponential backoff delay calculation."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)
        strategy = ExponentialBackoffStrategy(config)

        # Test delay progression
        assert asyncio.run(strategy.get_delay(0, RetryReason.NETWORK_ERROR)) == 1.0
        assert asyncio.run(strategy.get_delay(1, RetryReason.NETWORK_ERROR)) == 2.0
        assert asyncio.run(strategy.get_delay(2, RetryReason.NETWORK_ERROR)) == 4.0

    def test_exponential_backoff_max_delay(self):
        """Test that delays are capped at max_delay."""
        config = RetryConfig(
            base_delay=1.0, exponential_base=2.0, max_delay=5.0, jitter=False
        )
        strategy = ExponentialBackoffStrategy(config)

        # Large attempt should be capped
        delay = asyncio.run(strategy.get_delay(10, RetryReason.NETWORK_ERROR))
        assert delay == 5.0

    def test_should_retry_max_attempts(self):
        """Test retry limit enforcement."""
        config = RetryConfig(max_attempts=3)
        strategy = ExponentialBackoffStrategy(config)

        assert asyncio.run(
            strategy.should_retry(0, Exception(), RetryReason.NETWORK_ERROR)
        )
        assert asyncio.run(
            strategy.should_retry(2, Exception(), RetryReason.NETWORK_ERROR)
        )
        assert not asyncio.run(
            strategy.should_retry(3, Exception(), RetryReason.NETWORK_ERROR)
        )

    def test_circuit_breaker_state_transitions(self):
        """Test circuit breaker state transitions."""
        config = RetryConfig(failure_threshold=2)
        strategy = CircuitBreakerStrategy(config)

        # Initially closed
        assert strategy.state == "closed"

        # Record failures to trigger opening
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)

        # Should be open after threshold failures
        assert strategy.state == "open"

        # Success should transition to closed from half_open
        strategy.state = "half_open"
        strategy.record_attempt(True)
        assert strategy.state == "closed"


class TestErrorReporter:
    """Test error reporting functionality."""

    @pytest.mark.asyncio
    async def test_error_report_creation(self, tmp_path):
        """Test basic error report creation."""
        reporter = BasicErrorReporter(reports_dir=str(tmp_path))

        context = ErrorContext(
            video_id="test123", service_name="test_service", operation="test_operation"
        )

        exception = ValueError("Test error message")
        report = await reporter.report_error(exception, ErrorSeverity.HIGH, context)

        # Verify report structure
        assert report.severity == ErrorSeverity.HIGH
        assert report.exception_type == "ValueError"
        assert report.message == "Test error message"
        assert report.context.video_id == "test123"
        assert len(report.suggested_actions) > 0

    @pytest.mark.asyncio
    async def test_error_summary(self, tmp_path):
        """Test error summary generation."""
        reporter = BasicErrorReporter(reports_dir=str(tmp_path))

        context = ErrorContext(service_name="test_service")

        # Report some errors
        await reporter.report_error(ValueError("Error 1"), ErrorSeverity.HIGH, context)
        await reporter.report_error(
            ConnectionError("Error 2"), ErrorSeverity.MEDIUM, context
        )

        summary = await reporter.get_error_summary(hours=1)

        assert summary["total_errors"] == 2
        assert summary["severity_breakdown"]["high"] == 1
        assert summary["severity_breakdown"]["medium"] == 1
        assert len(summary["recent_errors"]) == 2


class TestErrorRecoveryManager:
    """Test error recovery manager functionality."""

    @pytest.mark.asyncio
    async def test_successful_execution_no_retry(self):
        """Test successful execution without retry."""
        config = RetryConfig(max_attempts=3)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(operation="test_operation")

        # Mock successful function
        mock_func = AsyncMock(return_value="success")

        result = await manager.execute_with_retry(mock_func, context)

        assert result == "success"
        assert mock_func.call_count == 1
        assert strategy.successful_attempts == 1
        assert strategy.failed_attempts == 0

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test retry behavior on failures."""
        config = RetryConfig(max_attempts=3, base_delay=0.01)  # Fast retry for testing
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(operation="test_operation")

        # Mock function that fails twice then succeeds
        mock_func = AsyncMock(
            side_effect=[ValueError("fail"), ValueError("fail"), "success"]
        )

        result = await manager.execute_with_retry(mock_func, context)

        assert result == "success"
        assert mock_func.call_count == 3
        assert strategy.successful_attempts == 1
        assert strategy.failed_attempts == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded."""
        config = RetryConfig(max_attempts=2, base_delay=0.01)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(operation="test_operation")

        # Mock function that always fails
        mock_func = AsyncMock(side_effect=ValueError("always fails"))

        with pytest.raises(ValueError, match="always fails"):
            await manager.execute_with_retry(mock_func, context)

        assert mock_func.call_count == 2
        assert strategy.failed_attempts == 2

    @pytest.mark.asyncio
    async def test_service_error_handler_recovery(self):
        """Test service-specific error handling."""
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()

        # Mock service handler that can recover from certain errors
        service_handler = AsyncMock()
        service_handler.handle_error.return_value = True  # Indicates recovery

        manager = ErrorRecoveryManager(strategy, reporter, service_handler)
        context = ErrorContext(operation="test_operation")

        # Mock function that fails once (but service handler recovers)
        mock_func = AsyncMock(side_effect=[ValueError("recoverable"), "success"])

        result = await manager.execute_with_retry(mock_func, context)

        assert result == "success"
        assert service_handler.handle_error.call_count == 1
        assert mock_func.call_count == 2


class TestIntegration:
    """Integration tests for the complete error recovery system."""

    @pytest.mark.asyncio
    async def test_end_to_end_error_recovery(self, tmp_path):
        """Test complete error recovery flow."""
        # Setup
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter(reports_dir=str(tmp_path))
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(
            video_id="test_video",
            service_name="download_service",
            operation="download_video",
        )

        # Simulate a function that fails then succeeds
        call_count = 0

        async def failing_download():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("Network error")
            return "download_complete"

        # Execute with retry
        result = await manager.execute_with_retry(failing_download, context)

        # Verify results
        assert result == "download_complete"
        assert call_count == 3
        assert strategy.successful_attempts == 1
        assert strategy.failed_attempts == 2

        # Check error summary
        summary = await reporter.get_error_summary()
        assert summary["total_errors"] == 0  # No final errors since it succeeded


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
