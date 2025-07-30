"""Tests for the error recovery library."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from services.error_recovery import ErrorRecoveryManager
from services.error_recovery.retry import (
    ExponentialBackoffStrategy,
    CircuitBreakerStrategy,
    AdaptiveStrategy,
    FixedDelayStrategy,
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

    @pytest.mark.unit
    def test_exponential_backoff_delay_calculation(self):
        """Test exponential backoff delay calculation."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)
        strategy = ExponentialBackoffStrategy(config)

        # Test delay progression
        assert asyncio.run(strategy.get_delay(0, RetryReason.NETWORK_ERROR)) == 1.0
        assert asyncio.run(strategy.get_delay(1, RetryReason.NETWORK_ERROR)) == 2.0
        assert asyncio.run(strategy.get_delay(2, RetryReason.NETWORK_ERROR)) == 4.0

    @pytest.mark.unit
    def test_exponential_backoff_max_delay(self):
        """Test that delays are capped at max_delay."""
        config = RetryConfig(
            base_delay=1.0, exponential_base=2.0, max_delay=5.0, jitter=False
        )
        strategy = ExponentialBackoffStrategy(config)

        # Large attempt should be capped
        delay = asyncio.run(strategy.get_delay(10, RetryReason.NETWORK_ERROR))
        assert delay == 5.0

    @pytest.mark.unit
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

    @pytest.mark.unit
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

    @pytest.mark.unit
    async def test_circuit_breaker_should_retry_closed_state(self):
        """Test circuit breaker should_retry behavior in closed state."""
        config = RetryConfig(max_attempts=3, failure_threshold=2)
        strategy = CircuitBreakerStrategy(config)

        # In closed state, should behave like normal retry strategy
        assert strategy.state == "closed"
        assert (
            await strategy.should_retry(0, Exception(), RetryReason.NETWORK_ERROR)
            is True
        )
        assert (
            await strategy.should_retry(1, Exception(), RetryReason.NETWORK_ERROR)
            is True
        )
        assert (
            await strategy.should_retry(2, Exception(), RetryReason.NETWORK_ERROR)
            is True
        )
        assert (
            await strategy.should_retry(3, Exception(), RetryReason.NETWORK_ERROR)
            is False
        )

    @pytest.mark.unit
    async def test_circuit_breaker_should_retry_open_state(self):
        """Test circuit breaker should_retry behavior in open state."""
        config = RetryConfig(max_attempts=3, failure_threshold=2, recovery_timeout=5.0)
        strategy = CircuitBreakerStrategy(config)

        # Force open state
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        assert strategy.state == "open"

        # In open state, should always return False (no retries)
        assert (
            await strategy.should_retry(0, Exception(), RetryReason.NETWORK_ERROR)
            is False
        )
        assert (
            await strategy.should_retry(1, Exception(), RetryReason.NETWORK_ERROR)
            is False
        )
        assert (
            await strategy.should_retry(2, Exception(), RetryReason.NETWORK_ERROR)
            is False
        )

    @pytest.mark.unit
    async def test_circuit_breaker_recovery_timeout(self):
        """Test circuit breaker automatic recovery after timeout."""
        import time

        config = RetryConfig(
            max_attempts=3, failure_threshold=2, recovery_timeout=0.1
        )  # 100ms
        strategy = CircuitBreakerStrategy(config)

        # Force open state
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        assert strategy.state == "open"

        # Should not retry immediately when open
        assert (
            await strategy.should_retry(0, Exception(), RetryReason.NETWORK_ERROR)
            is False
        )

        # Wait for recovery timeout
        time.sleep(0.15)  # Wait slightly longer than recovery_timeout

        # Should transition to half_open and allow retry
        assert (
            await strategy.should_retry(0, Exception(), RetryReason.NETWORK_ERROR)
            is True
        )
        assert strategy.state == "half_open"

    @pytest.mark.unit
    async def test_circuit_breaker_half_open_success_closes(self):
        """Test circuit breaker transitions from half_open to closed on success."""
        config = RetryConfig(failure_threshold=2)
        strategy = CircuitBreakerStrategy(config)

        # Force half_open state
        strategy.state = "half_open"
        strategy.failure_count = 1  # Some previous failures

        # Success in half_open should transition to closed and reset failure count
        strategy.record_attempt(True)
        assert strategy.state == "closed"
        assert strategy.failure_count == 0

    @pytest.mark.unit
    async def test_circuit_breaker_half_open_failure_opens(self):
        """Test circuit breaker transitions from half_open to open on failure."""
        config = RetryConfig(failure_threshold=2)
        strategy = CircuitBreakerStrategy(config)

        # Start with half_open state and some existing failures
        strategy.state = "half_open"
        strategy.failure_count = 1

        # Failure in half_open should increment count
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        assert strategy.failure_count == 2
        assert strategy.state == "open"  # Should transition to open

    @pytest.mark.unit
    async def test_circuit_breaker_get_delay_closed_state(self):
        """Test circuit breaker delay calculation in closed state."""
        config = RetryConfig(base_delay=2.0, exponential_base=2.0, max_delay=10.0)
        strategy = CircuitBreakerStrategy(config)

        # In closed state, should use exponential backoff
        assert strategy.state == "closed"

        delay0 = await strategy.get_delay(0, RetryReason.NETWORK_ERROR)
        delay1 = await strategy.get_delay(1, RetryReason.NETWORK_ERROR)
        delay2 = await strategy.get_delay(2, RetryReason.NETWORK_ERROR)

        # base_delay * exponential_base^attempt
        assert delay0 == 2.0 * (2.0**0)  # 2.0
        assert delay1 == 2.0 * (2.0**1)  # 4.0
        assert delay2 == 2.0 * (2.0**2)  # 8.0

    @pytest.mark.unit
    async def test_circuit_breaker_get_delay_open_state(self):
        """Test circuit breaker delay calculation in open state."""
        config = RetryConfig(base_delay=1.0, recovery_timeout=30.0, failure_threshold=2)
        strategy = CircuitBreakerStrategy(config)

        # Force open state
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        assert strategy.state == "open"

        # In open state, should return recovery_timeout
        delay = await strategy.get_delay(0, RetryReason.NETWORK_ERROR)
        assert delay == 30.0

        # Should be consistent regardless of attempt number
        delay1 = await strategy.get_delay(5, RetryReason.NETWORK_ERROR)
        assert delay1 == 30.0

    @pytest.mark.unit
    async def test_circuit_breaker_get_delay_max_delay_limit(self):
        """Test circuit breaker respects max_delay in closed/half_open state."""
        config = RetryConfig(base_delay=5.0, exponential_base=3.0, max_delay=20.0)
        strategy = CircuitBreakerStrategy(config)

        # High attempt number should be capped by max_delay
        delay = await strategy.get_delay(5, RetryReason.NETWORK_ERROR)
        # base_delay * exponential_base^attempt = 5.0 * 3^5 = 1215.0
        # Should be capped at max_delay = 20.0
        assert delay == 20.0

        # Test in half_open state too
        strategy.state = "half_open"
        delay_half_open = await strategy.get_delay(5, RetryReason.NETWORK_ERROR)
        assert delay_half_open == 20.0

    @pytest.mark.unit
    def test_circuit_breaker_metrics_tracking(self):
        """Test circuit breaker metrics tracking."""
        config = RetryConfig(failure_threshold=3)
        strategy = CircuitBreakerStrategy(config)

        # Initially zero
        assert strategy.total_attempts == 0
        assert strategy.successful_attempts == 0
        assert strategy.failed_attempts == 0

        # Record various attempts
        strategy.record_attempt(True)
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        strategy.record_attempt(True)
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        strategy.record_attempt(
            False, RetryReason.NETWORK_ERROR
        )  # 3rd consecutive failure

        # Check metrics
        assert strategy.total_attempts == 6
        assert strategy.successful_attempts == 2
        assert strategy.failed_attempts == 4

        # Should be open now (3 consecutive failures >= threshold 3)
        assert strategy.state == "open"

    @pytest.mark.unit
    def test_circuit_breaker_failure_threshold_exact(self):
        """Test circuit breaker opens at exact failure threshold."""
        config = RetryConfig(failure_threshold=3)
        strategy = CircuitBreakerStrategy(config)

        # Record failures up to threshold - 1
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        assert strategy.state == "closed"  # Still closed
        assert strategy.failure_count == 2

        # One more failure should open the circuit
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        assert strategy.state == "open"
        assert strategy.failure_count == 3

    @pytest.mark.unit
    def test_circuit_breaker_success_resets_failure_count(self):
        """Test circuit breaker resets failure count on success."""
        config = RetryConfig(failure_threshold=3)
        strategy = CircuitBreakerStrategy(config)

        # Record some failures
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        assert strategy.failure_count == 2
        assert strategy.state == "closed"

        # Success should reset failure count
        strategy.record_attempt(True)
        assert strategy.failure_count == 0
        assert strategy.state == "closed"

        # Should need full threshold failures again to open
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        assert strategy.state == "closed"  # Still closed

        strategy.record_attempt(False, RetryReason.NETWORK_ERROR)
        assert strategy.state == "open"  # Now open

    @pytest.mark.unit
    async def test_adaptive_strategy_success_rate_calculation(self):
        """Test adaptive strategy success rate calculation."""
        config = RetryConfig(max_attempts=5, base_delay=1.0)
        strategy = AdaptiveStrategy(config)

        # Initially empty, should return 1.0
        assert strategy._calculate_success_rate() == 1.0

        # Record some attempts
        strategy.record_attempt(True)  # Success
        strategy.record_attempt(False)  # Failure
        strategy.record_attempt(True)  # Success

        # Should be 2/3 = 0.667
        success_rate = strategy._calculate_success_rate()
        assert abs(success_rate - 0.6666666666666666) < 0.001

        # Fill up the adaptation window (10 attempts)
        for _ in range(7):
            strategy.record_attempt(False)

        # Should be 2 successes out of 10 = 0.2
        success_rate = strategy._calculate_success_rate()
        assert success_rate == 0.2

    @pytest.mark.unit
    async def test_adaptive_strategy_sliding_window(self):
        """Test adaptive strategy sliding window behavior."""
        config = RetryConfig(max_attempts=5, base_delay=1.0)
        strategy = AdaptiveStrategy(config)

        # Fill adaptation window with failures
        for _ in range(10):
            strategy.record_attempt(False)
        assert len(strategy.recent_attempts) == 10
        assert strategy._calculate_success_rate() == 0.0

        # Add one more - should push out oldest
        strategy.record_attempt(True)
        assert len(strategy.recent_attempts) == 10  # Still 10
        assert strategy._calculate_success_rate() == 0.1  # 1 success out of 10

        # Add 9 more successes - should push out all failures
        for _ in range(9):
            strategy.record_attempt(True)
        assert strategy._calculate_success_rate() == 1.0  # All successes

    @pytest.mark.unit
    async def test_adaptive_strategy_early_termination(self):
        """Test adaptive strategy early retry termination on low success rate."""
        config = RetryConfig(max_attempts=5, base_delay=1.0)
        strategy = AdaptiveStrategy(config)

        # Create low success rate scenario (< 0.3)
        strategy.record_attempt(False)
        strategy.record_attempt(False)
        strategy.record_attempt(False)
        strategy.record_attempt(True)  # 1 success, 3 failures = 0.25 success rate

        # Should allow retries for attempt 0 and 1
        assert (
            await strategy.should_retry(0, Exception(), RetryReason.NETWORK_ERROR)
            is True
        )
        assert (
            await strategy.should_retry(1, Exception(), RetryReason.NETWORK_ERROR)
            is True
        )

        # Should terminate early at attempt 2 due to low success rate
        assert (
            await strategy.should_retry(2, Exception(), RetryReason.NETWORK_ERROR)
            is False
        )

    @pytest.mark.unit
    async def test_adaptive_strategy_high_success_rate_behavior(self):
        """Test adaptive strategy behavior with high success rate."""
        config = RetryConfig(max_attempts=5, base_delay=1.0)
        strategy = AdaptiveStrategy(config)

        # Create high success rate scenario (> 0.7)
        for _ in range(8):
            strategy.record_attempt(True)
        strategy.record_attempt(False)
        strategy.record_attempt(False)  # 8 successes, 2 failures = 0.8 success rate

        # Should allow all retries within max_attempts
        assert (
            await strategy.should_retry(0, Exception(), RetryReason.NETWORK_ERROR)
            is True
        )
        assert (
            await strategy.should_retry(1, Exception(), RetryReason.NETWORK_ERROR)
            is True
        )
        assert (
            await strategy.should_retry(2, Exception(), RetryReason.NETWORK_ERROR)
            is True
        )
        assert (
            await strategy.should_retry(3, Exception(), RetryReason.NETWORK_ERROR)
            is True
        )

        # Should respect max_attempts
        assert (
            await strategy.should_retry(5, Exception(), RetryReason.NETWORK_ERROR)
            is False
        )

    @pytest.mark.unit
    async def test_adaptive_strategy_delay_calculation(self):
        """Test adaptive strategy delay calculation based on success rate."""
        config = RetryConfig(
            max_attempts=5, base_delay=2.0, exponential_base=2.0, jitter=False
        )
        strategy = AdaptiveStrategy(config)

        # Test with low success rate (< 0.7) - should use 2.0 multiplier
        for _ in range(6):
            strategy.record_attempt(False)
        for _ in range(4):
            strategy.record_attempt(True)  # 0.4 success rate

        delay = await strategy.get_delay(1, RetryReason.NETWORK_ERROR)
        # base_delay * exponential_base^attempt * multiplier = 2.0 * 2^1 * 2.0 = 8.0
        expected_delay = 2.0 * (2.0**1) * 2.0
        assert delay == expected_delay

        # Test with high success rate (>= 0.7) - should use 0.5 multiplier
        strategy = AdaptiveStrategy(config)
        for _ in range(8):
            strategy.record_attempt(True)
        for _ in range(2):
            strategy.record_attempt(False)  # 0.8 success rate

        delay = await strategy.get_delay(1, RetryReason.NETWORK_ERROR)
        # base_delay * exponential_base^attempt * multiplier = 2.0 * 2^1 * 0.5 = 2.0
        expected_delay = 2.0 * (2.0**1) * 0.5
        assert delay == expected_delay

    @pytest.mark.unit
    async def test_adaptive_strategy_delay_with_jitter(self):
        """Test adaptive strategy delay calculation with jitter."""
        config = RetryConfig(
            max_attempts=5, base_delay=2.0, exponential_base=2.0, jitter=True
        )
        strategy = AdaptiveStrategy(config)

        # Set up medium success rate
        for _ in range(5):
            strategy.record_attempt(True)
        for _ in range(5):
            strategy.record_attempt(False)  # 0.5 success rate

        # Test multiple calls to ensure jitter varies delay
        delays = []
        for _ in range(10):
            delay = await strategy.get_delay(1, RetryReason.NETWORK_ERROR)
            delays.append(delay)
            assert delay >= 0  # Should never be negative

        # Base calculation: 2.0 * 2^1 * 2.0 = 8.0
        # With 10% jitter: 8.0 +/- 0.8, so range [7.2, 8.8]
        base_delay = 2.0 * (2.0**1) * 2.0
        jitter_range = base_delay * 0.1

        for delay in delays:
            assert (
                delay >= base_delay - jitter_range - 0.1
            )  # Small tolerance for floating point
            assert delay <= base_delay + jitter_range + 0.1

        # Ensure jitter actually varies the delay (not all identical)
        assert len(set(delays)) > 1

    @pytest.mark.unit
    async def test_adaptive_strategy_max_delay_limit(self):
        """Test adaptive strategy respects max_delay limit."""
        config = RetryConfig(
            max_attempts=10,
            base_delay=5.0,
            max_delay=20.0,
            exponential_base=3.0,
            jitter=False,
        )
        strategy = AdaptiveStrategy(config)

        # Set up low success rate for maximum multiplier (2.0)
        for _ in range(10):
            strategy.record_attempt(False)

        # High attempt number should be capped by max_delay
        delay = await strategy.get_delay(5, RetryReason.NETWORK_ERROR)
        # base_delay * exponential_base^attempt * multiplier = 5.0 * 3^5 * 2.0 = 2430.0
        # Should be capped at max_delay = 20.0
        assert delay == 20.0

    @pytest.mark.unit
    def test_adaptive_strategy_metrics_tracking(self):
        """Test adaptive strategy metrics tracking."""
        config = RetryConfig(max_attempts=5, base_delay=1.0)
        strategy = AdaptiveStrategy(config)

        # Initially zero
        assert strategy.total_attempts == 0
        assert strategy.successful_attempts == 0
        assert strategy.failed_attempts == 0

        # Record some attempts
        strategy.record_attempt(True)
        strategy.record_attempt(False)
        strategy.record_attempt(True)
        strategy.record_attempt(False)
        strategy.record_attempt(False)

        # Check metrics
        assert strategy.total_attempts == 5
        assert strategy.successful_attempts == 2
        assert strategy.failed_attempts == 3

    @pytest.mark.unit
    async def test_fixed_delay_strategy_should_retry(self):
        """Test fixed delay strategy should_retry logic."""
        config = RetryConfig(max_attempts=3, base_delay=2.0)
        strategy = FixedDelayStrategy(config)

        # Should allow retries within max_attempts
        assert (
            await strategy.should_retry(0, Exception(), RetryReason.NETWORK_ERROR)
            is True
        )
        assert (
            await strategy.should_retry(1, Exception(), RetryReason.NETWORK_ERROR)
            is True
        )
        assert (
            await strategy.should_retry(2, Exception(), RetryReason.NETWORK_ERROR)
            is True
        )

        # Should not allow retries at or beyond max_attempts
        assert (
            await strategy.should_retry(3, Exception(), RetryReason.NETWORK_ERROR)
            is False
        )
        assert (
            await strategy.should_retry(4, Exception(), RetryReason.NETWORK_ERROR)
            is False
        )

    @pytest.mark.unit
    async def test_fixed_delay_strategy_delay_without_jitter(self):
        """Test fixed delay strategy delay calculation without jitter."""
        config = RetryConfig(max_attempts=5, base_delay=3.5, jitter=False)
        strategy = FixedDelayStrategy(config)

        # Should always return base_delay regardless of attempt number
        delay1 = await strategy.get_delay(0, RetryReason.NETWORK_ERROR)
        delay2 = await strategy.get_delay(1, RetryReason.NETWORK_ERROR)
        delay3 = await strategy.get_delay(5, RetryReason.NETWORK_ERROR)

        assert delay1 == 3.5
        assert delay2 == 3.5
        assert delay3 == 3.5

        # Test with different retry reasons - should still be consistent
        delay4 = await strategy.get_delay(2, RetryReason.API_QUOTA_EXCEEDED)
        delay5 = await strategy.get_delay(3, RetryReason.RATE_LIMITED)

        assert delay4 == 3.5
        assert delay5 == 3.5

    @pytest.mark.unit
    async def test_fixed_delay_strategy_delay_with_jitter(self):
        """Test fixed delay strategy delay calculation with jitter."""
        config = RetryConfig(max_attempts=5, base_delay=10.0, jitter=True)
        strategy = FixedDelayStrategy(config)

        # Test multiple calls to ensure jitter varies delay
        delays = []
        for _ in range(20):  # More samples for better jitter testing
            delay = await strategy.get_delay(0, RetryReason.NETWORK_ERROR)
            delays.append(delay)
            assert delay >= 0  # Should never be negative

        # With 10% jitter on base_delay=10.0: jitter_range = 1.0
        # Range should be [9.0, 11.0]
        base_delay = 10.0
        jitter_range = base_delay * 0.1

        for delay in delays:
            assert (
                delay >= base_delay - jitter_range - 0.1
            )  # Small tolerance for floating point
            assert delay <= base_delay + jitter_range + 0.1

        # Ensure jitter actually varies the delay (not all identical)
        # With 20 samples, we should have some variation
        unique_delays = set(delays)
        assert (
            len(unique_delays) > 1
        ), f"Expected varied delays with jitter, got: {unique_delays}"

    @pytest.mark.unit
    async def test_fixed_delay_strategy_jitter_edge_cases(self):
        """Test fixed delay strategy jitter edge cases."""
        # Test with very small base_delay
        config = RetryConfig(max_attempts=3, base_delay=0.1, jitter=True)
        strategy = FixedDelayStrategy(config)

        delays = []
        for _ in range(10):
            delay = await strategy.get_delay(0, RetryReason.NETWORK_ERROR)
            delays.append(delay)
            assert delay >= 0  # Should never be negative even with jitter

        # All delays should be close to 0.1 with small jitter
        for delay in delays:
            assert 0.0 <= delay <= 0.2  # Reasonable range for 0.1 +/- 10%

        # Test with zero base_delay
        config_zero = RetryConfig(max_attempts=3, base_delay=0.0, jitter=True)
        strategy_zero = FixedDelayStrategy(config_zero)

        delay_zero = await strategy_zero.get_delay(0, RetryReason.NETWORK_ERROR)
        assert delay_zero >= 0  # Should handle zero gracefully

    @pytest.mark.unit
    def test_fixed_delay_strategy_metrics_tracking(self):
        """Test fixed delay strategy metrics tracking."""
        config = RetryConfig(max_attempts=5, base_delay=1.0)
        strategy = FixedDelayStrategy(config)

        # Initially zero
        assert strategy.total_attempts == 0
        assert strategy.successful_attempts == 0
        assert strategy.failed_attempts == 0

        # Record various attempts
        strategy.record_attempt(True)
        strategy.record_attempt(False)
        strategy.record_attempt(True)
        strategy.record_attempt(True)
        strategy.record_attempt(False)
        strategy.record_attempt(False)

        # Check metrics
        assert strategy.total_attempts == 6
        assert strategy.successful_attempts == 3
        assert strategy.failed_attempts == 3

        # Record attempts with retry reasons (should not affect counting)
        strategy.record_attempt(True, RetryReason.NETWORK_ERROR)
        strategy.record_attempt(False, RetryReason.API_QUOTA_EXCEEDED)

        assert strategy.total_attempts == 8
        assert strategy.successful_attempts == 4
        assert strategy.failed_attempts == 4

    @pytest.mark.unit
    async def test_fixed_delay_strategy_different_retry_reasons(self):
        """Test fixed delay strategy behavior with different retry reasons."""
        config = RetryConfig(max_attempts=3, base_delay=2.0, jitter=False)
        strategy = FixedDelayStrategy(config)

        # Test all retry reasons - delay should be consistent
        retry_reasons = [
            RetryReason.NETWORK_ERROR,
            RetryReason.API_QUOTA_EXCEEDED,
            RetryReason.RATE_LIMITED,
            RetryReason.DOWNLOAD_FAILED,
            RetryReason.SERVICE_UNAVAILABLE,
            RetryReason.QUALITY_NOT_AVAILABLE,
            RetryReason.SERVER_ERROR,
            RetryReason.RESOURCE_EXHAUSTED,
            RetryReason.TIMEOUT,
            RetryReason.UNKNOWN,
        ]

        for reason in retry_reasons:
            # should_retry should be consistent regardless of reason
            assert await strategy.should_retry(0, Exception(), reason) is True
            assert await strategy.should_retry(2, Exception(), reason) is True
            assert await strategy.should_retry(3, Exception(), reason) is False

            # get_delay should be consistent regardless of reason
            delay = await strategy.get_delay(1, reason)
            assert delay == 2.0


class TestErrorReporter:
    """Test error reporting functionality."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_error_report_creation(self, tmp_path):
        """Test basic error report creation."""
        reporter = BasicErrorReporter(reports_dir=str(tmp_path))

        context = ErrorContext(
            video_id="test123",
            service_name="test_service",
            operation_name="test_operation",
        )

        exception = ValueError("Test error message")
        report = await reporter.report_error(exception, ErrorSeverity.HIGH, context)

        # Verify report structure
        assert report.severity == ErrorSeverity.HIGH
        assert report.exception_type == "ValueError"
        assert report.message == "Test error message"
        assert report.context.video_id == "test123"
        assert len(report.suggested_actions) > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_error_summary(self, tmp_path):
        """Test error summary generation."""
        reporter = BasicErrorReporter(reports_dir=str(tmp_path))

        context = ErrorContext(
            operation_name="test_service", service_name="test_service"
        )

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

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_successful_execution_no_retry(self):
        """Test successful execution without retry."""
        config = RetryConfig(max_attempts=3)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(operation_name="test_operation")

        # Mock successful function
        mock_func = AsyncMock(return_value="success")

        result = await manager.execute_with_retry(mock_func, context)

        assert result == "success"
        assert mock_func.call_count == 1
        assert strategy.successful_attempts == 1
        assert strategy.failed_attempts == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test retry behavior on failures."""
        config = RetryConfig(max_attempts=3, base_delay=0.01)  # Fast retry for testing
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(operation_name="test_operation")

        # Mock function that fails twice then succeeds
        mock_func = AsyncMock(
            side_effect=[ValueError("fail"), ValueError("fail"), "success"]
        )

        result = await manager.execute_with_retry(mock_func, context)

        assert result == "success"
        assert mock_func.call_count == 3
        assert strategy.successful_attempts == 1
        assert strategy.failed_attempts == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded."""
        config = RetryConfig(max_attempts=2, base_delay=0.01)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(operation_name="test_operation")

        # Mock function that always fails
        mock_func = AsyncMock(side_effect=ValueError("always fails"))

        with pytest.raises(ValueError, match="always fails"):
            await manager.execute_with_retry(mock_func, context, config)

        assert mock_func.call_count == 2
        assert strategy.failed_attempts == 2

    @pytest.mark.unit
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
        context = ErrorContext(operation_name="test_operation")

        # Mock function that fails once (but service handler recovers)
        mock_func = AsyncMock(side_effect=[ValueError("recoverable"), "success"])

        result = await manager.execute_with_retry(mock_func, context)

        assert result == "success"
        assert service_handler.handle_error.call_count == 1
        assert mock_func.call_count == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_retry_reason_network_errors(self):
        """Test _determine_retry_reason with network-related exceptions."""
        config = RetryConfig(max_attempts=2)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(operation_name="test_network")

        # Test ConnectionError
        reason = manager._determine_retry_reason(
            ConnectionError("Connection failed"), context
        )
        assert reason == RetryReason.NETWORK_ERROR

        # Test TimeoutError
        reason = manager._determine_retry_reason(
            TimeoutError("Request timeout"), context
        )
        assert reason == RetryReason.NETWORK_ERROR

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_retry_reason_api_errors(self):
        """Test _determine_retry_reason with API-related exceptions."""
        config = RetryConfig(max_attempts=2)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(operation_name="test_api")

        # Test quota exceeded
        reason = manager._determine_retry_reason(
            ValueError("API quota exceeded"), context
        )
        assert reason == RetryReason.API_QUOTA_EXCEEDED

        # Test rate limited
        reason = manager._determine_retry_reason(
            ValueError("Rate limit reached"), context
        )
        assert reason == RetryReason.RATE_LIMITED

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_retry_reason_io_errors(self):
        """Test _determine_retry_reason with IO-related exceptions."""
        config = RetryConfig(max_attempts=2)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(operation_name="test_io")

        # Test IOError
        reason = manager._determine_retry_reason(IOError("File access failed"), context)
        assert reason == RetryReason.DOWNLOAD_FAILED

        # Test OSError
        reason = manager._determine_retry_reason(OSError("System error"), context)
        assert reason == RetryReason.DOWNLOAD_FAILED

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_retry_reason_http_status_codes(self):
        """Test _determine_retry_reason with HTTP status codes."""
        config = RetryConfig(max_attempts=2)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(operation_name="test_http")

        # Mock HTTP exception with response
        class MockResponse:
            def __init__(self, status_code):
                self.status_code = status_code

        class MockHTTPException(Exception):
            def __init__(self, status_code):
                self.response = MockResponse(status_code)

        # Test server error (500+)
        reason = manager._determine_retry_reason(MockHTTPException(500), context)
        assert reason == RetryReason.SERVER_ERROR

        # Test service unavailable (503)
        reason = manager._determine_retry_reason(MockHTTPException(503), context)
        assert reason == RetryReason.SERVICE_UNAVAILABLE

        # Test rate limited (429)
        reason = manager._determine_retry_reason(MockHTTPException(429), context)
        assert reason == RetryReason.RATE_LIMITED

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_retry_reason_unknown_error(self):
        """Test _determine_retry_reason with unknown exception types."""
        config = RetryConfig(max_attempts=2)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(operation_name="test_unknown")

        # Test unknown exception
        reason = manager._determine_retry_reason(RuntimeError("Unknown error"), context)
        assert reason == RetryReason.UNKNOWN

        # Test generic ValueError without keywords
        reason = manager._determine_retry_reason(ValueError("Generic error"), context)
        assert reason == RetryReason.UNKNOWN

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_active_recovery_tracking(self):
        """Test active recovery operations tracking."""
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(operation_name="test_tracking")

        # Initially no active recoveries
        assert len(manager.get_active_recoveries()) == 0

        # Mock function that fails once then succeeds
        mock_func = AsyncMock(side_effect=[ValueError("fail"), "success"])

        # Check active recovery during execution
        async def check_during_execution():
            active = manager.get_active_recoveries()
            assert len(active) == 1
            recovery = list(active.values())[0]
            assert recovery["function"] == mock_func.__name__
            assert recovery["context"] == context
            assert "started_at" in recovery
            assert recovery["attempts"] >= 1

        # Patch the function to check active recoveries mid-execution
        original_record = strategy.record_attempt
        check_called = False

        def patched_record(success, reason=None):
            nonlocal check_called
            if not success and not check_called:
                check_called = True
                asyncio.create_task(check_during_execution())
            return original_record(success, reason)

        strategy.record_attempt = patched_record

        result = await manager.execute_with_retry(mock_func, context)

        assert result == "success"
        # After completion, no active recoveries
        assert len(manager.get_active_recoveries()) == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cleanup_on_exception(self):
        """Test resource cleanup when operation fails completely."""
        config = RetryConfig(max_attempts=2, base_delay=0.01)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(operation_name="test_cleanup")

        # Mock function that always fails
        mock_func = AsyncMock(side_effect=ValueError("always fails"))

        # Verify active recovery is tracked during execution
        with pytest.raises(ValueError, match="always fails"):
            await manager.execute_with_retry(mock_func, context)

        # After exception, active recoveries should be cleaned up
        assert len(manager.get_active_recoveries()) == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_concurrent_recovery_operations(self):
        """Test multiple concurrent recovery operations."""
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        # Create multiple contexts
        context1 = ErrorContext(operation_name="operation_1")
        context2 = ErrorContext(operation_name="operation_2")
        context3 = ErrorContext(operation_name="operation_3")

        # Use events to synchronize and detect concurrency
        running_events = [asyncio.Event() for _ in range(3)]

        async def sync_func(index, result):
            """Function that synchronizes with other operations to ensure concurrency."""
            # Signal that this operation is running
            running_events[index].set()

            # Wait for all operations to be running
            for event in running_events:
                await event.wait()

            # Now all operations are confirmed to be running concurrently
            return result

        # Mock functions with different behaviors but synchronized starts
        async def mock_func1():
            return await sync_func(0, "success_1")

        async def mock_func2():
            return await sync_func(1, "success_2")

        async def mock_func3():
            return await sync_func(2, "success_3")

        # Run operations concurrently
        tasks = [
            manager.execute_with_retry(mock_func1, context1),
            manager.execute_with_retry(mock_func2, context2),
            manager.execute_with_retry(mock_func3, context3),
        ]

        results = await asyncio.gather(*tasks)

        assert results == ["success_1", "success_2", "success_3"]
        # Verify that all operations completed (implicit concurrency test)
        assert len(manager.get_active_recoveries()) == 0  # All cleaned up

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_service_handler_exception_handling(self):
        """Test error handling when service handler raises exceptions."""
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()

        # Mock service handler that raises an exception
        service_handler = AsyncMock()
        service_handler.handle_error.side_effect = RuntimeError("Handler failed")

        manager = ErrorRecoveryManager(strategy, reporter, service_handler)
        context = ErrorContext(operation_name="test_handler_exception")

        # Mock function that fails
        mock_func = AsyncMock(side_effect=ValueError("original error"))

        # Should propagate the original error, not handler error
        with pytest.raises(ValueError, match="original error"):
            await manager.execute_with_retry(mock_func, context)

        # Verify service handler was called despite exception
        assert service_handler.handle_error.called
        assert len(manager.get_active_recoveries()) == 0  # Cleaned up

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_retry_config_none_uses_default(self):
        """Test that None retry_config uses default configuration."""
        strategy = ExponentialBackoffStrategy(RetryConfig())
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(operation_name="test_default_config")

        # Mock function that fails twice then succeeds
        mock_func = AsyncMock(
            side_effect=[ValueError("fail"), ValueError("fail"), "success"]
        )

        # Pass None for retry_config to test default behavior
        result = await manager.execute_with_retry(mock_func, context, retry_config=None)

        assert result == "success"
        assert mock_func.call_count == 3


class TestAdvancedEdgeCases:
    """Advanced edge case tests for error recovery system robustness."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalid_retry_config_negative_max_attempts(self):
        """Test handling of invalid negative max_attempts."""
        # Invalid config should raise ValueError during creation
        with pytest.raises(ValueError, match="greater than 0"):
            RetryConfig(max_attempts=-1)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalid_retry_config_zero_max_attempts(self):
        """Test handling of zero max_attempts."""
        with pytest.raises(ValueError, match="greater than 0"):
            RetryConfig(max_attempts=0)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalid_retry_config_negative_base_delay(self):
        """Test handling of negative base_delay."""
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            RetryConfig(base_delay=-1.0)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalid_retry_config_max_delay_smaller_than_base(self):
        """Test handling of max_delay smaller than base_delay."""
        with pytest.raises(
            ValueError, match="max_delay must be greater than or equal to base_delay"
        ):
            RetryConfig(base_delay=5.0, max_delay=2.0)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_network_timeout_during_retry_delay(self):
        """Test handling of network timeout during retry delay period."""
        config = RetryConfig(max_attempts=3, base_delay=0.1)  # Short base delay
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(operation_name="test_timeout_during_delay")

        # Mock function that fails first time
        mock_func = AsyncMock(side_effect=[ValueError("fail"), "success"])

        # Track sleep calls and raise CancelledError on first sleep call
        sleep_call_count = 0
        original_sleep = asyncio.sleep

        async def mock_sleep_with_timeout(delay):
            nonlocal sleep_call_count
            sleep_call_count += 1
            if sleep_call_count == 1:
                # Simulate network timeout during first retry delay
                raise asyncio.CancelledError("Network timeout during delay")
            else:
                # Allow other sleeps to proceed normally
                return await original_sleep(delay)

        with patch("asyncio.sleep", side_effect=mock_sleep_with_timeout):
            with pytest.raises(
                asyncio.CancelledError, match="Network timeout during delay"
            ):
                await manager.execute_with_retry(mock_func, context)

        # Verify cleanup happened
        assert len(manager.get_active_recoveries()) == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_task_cancellation_during_retry_operation(self):
        """Test handling of task cancellation during retry operation."""
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(operation_name="test_task_cancellation")

        # Event to control when to cancel
        cancel_event = asyncio.Event()

        async def mock_func():
            # Wait for cancellation signal
            await cancel_event.wait()
            return "should_not_reach"

        # Start the retry operation
        task = asyncio.create_task(manager.execute_with_retry(mock_func, context))

        # Give task time to start
        await asyncio.sleep(0.01)

        # Verify task is running and tracked
        assert len(manager.get_active_recoveries()) == 1

        # Cancel the task
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Verify cleanup happened even with cancellation
        assert len(manager.get_active_recoveries()) == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_exception_in_error_reporter(self):
        """Test handling of exceptions in error reporter."""
        config = RetryConfig(max_attempts=2, base_delay=0.01)
        strategy = ExponentialBackoffStrategy(config)

        # Mock error reporter that raises exception
        reporter = AsyncMock()
        reporter.report_error.side_effect = RuntimeError("Reporter failed")

        manager = ErrorRecoveryManager(strategy, reporter)
        context = ErrorContext(operation_name="test_reporter_exception")

        # Mock function that always fails
        mock_func = AsyncMock(side_effect=ValueError("always fails"))

        # Should still propagate original error even if reporter fails
        with pytest.raises(ValueError, match="always fails"):
            await manager.execute_with_retry(mock_func, context)

        # Verify reporter was called despite failure
        assert reporter.report_error.called
        assert len(manager.get_active_recoveries()) == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_exception_in_retry_strategy_should_retry(self):
        """Test handling of exceptions in retry strategy should_retry method."""
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()

        # Mock should_retry to raise exception
        strategy.should_retry = AsyncMock(
            side_effect=RuntimeError("should_retry failed")
        )

        manager = ErrorRecoveryManager(strategy, reporter)
        context = ErrorContext(operation_name="test_strategy_exception")

        # Mock function that fails
        mock_func = AsyncMock(side_effect=ValueError("original error"))

        # Should propagate the strategy exception
        with pytest.raises(RuntimeError, match="should_retry failed"):
            await manager.execute_with_retry(mock_func, context)

        assert len(manager.get_active_recoveries()) == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_exception_in_retry_strategy_get_delay(self):
        """Test handling of exceptions in retry strategy get_delay method."""
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()

        # Mock get_delay to raise exception after first failure
        call_count = 0

        async def mock_get_delay(attempt, reason):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("get_delay failed")
            return 0.01

        strategy.get_delay = mock_get_delay

        manager = ErrorRecoveryManager(strategy, reporter)
        context = ErrorContext(operation_name="test_get_delay_exception")

        # Mock function that fails
        mock_func = AsyncMock(side_effect=ValueError("original error"))

        # Should propagate the get_delay exception
        with pytest.raises(RuntimeError, match="get_delay failed"):
            await manager.execute_with_retry(mock_func, context)

        assert len(manager.get_active_recoveries()) == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_exception_in_retry_strategy_record_attempt(self):
        """Test handling of exceptions in retry strategy record_attempt method."""
        config = RetryConfig(max_attempts=2, base_delay=0.01)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()

        # Mock record_attempt to raise exception on failure recording
        original_record = strategy.record_attempt

        def mock_record_attempt(success, reason=None):
            if not success:
                raise RuntimeError("record_attempt failed for failure")
            return original_record(success, reason)

        strategy.record_attempt = mock_record_attempt

        manager = ErrorRecoveryManager(strategy, reporter)
        context = ErrorContext(operation_name="test_record_attempt_exception")

        # Mock function that fails
        mock_func = AsyncMock(side_effect=ValueError("original error"))

        # Should propagate the record_attempt exception
        with pytest.raises(RuntimeError, match="record_attempt failed for failure"):
            await manager.execute_with_retry(mock_func, context)

        assert len(manager.get_active_recoveries()) == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_complex_exception_chaining(self):
        """Test complex scenario with multiple cascading exceptions."""
        config = RetryConfig(max_attempts=2, base_delay=0.01)
        strategy = ExponentialBackoffStrategy(config)

        # Mock reporter that fails
        reporter = AsyncMock()
        reporter.report_error.side_effect = RuntimeError("Reporter cascade failure")

        # Mock service handler that fails
        service_handler = AsyncMock()
        service_handler.handle_error.side_effect = RuntimeError(
            "Handler cascade failure"
        )

        manager = ErrorRecoveryManager(strategy, reporter, service_handler)
        context = ErrorContext(operation_name="test_exception_cascade")

        # Mock function that always fails
        mock_func = AsyncMock(side_effect=ValueError("original cascade error"))

        # The service handler exception should not propagate due to try-catch
        # The original error should propagate (reporter exception is not caught)
        with pytest.raises(ValueError, match="original cascade error"):
            await manager.execute_with_retry(mock_func, context)

        # Verify both service handler and reporter were called
        assert service_handler.handle_error.called
        assert reporter.report_error.called
        assert len(manager.get_active_recoveries()) == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_memory_cleanup_under_stress(self):
        """Test memory cleanup under rapid operation creation/destruction."""
        config = RetryConfig(max_attempts=2, base_delay=0.001)  # Very fast
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        # Run many rapid operations to test memory cleanup
        tasks = []
        for i in range(50):  # Create many operations
            context = ErrorContext(operation_name=f"stress_test_{i}")

            # Mix of success and failure scenarios
            if i % 3 == 0:
                mock_func = AsyncMock(return_value=f"success_{i}")
            else:
                mock_func = AsyncMock(side_effect=ValueError(f"fail_{i}"))

            # Create task but don't await immediately
            task = asyncio.create_task(manager.execute_with_retry(mock_func, context))
            tasks.append((task, i % 3 == 0))  # Track if should succeed

        # Wait for all operations to complete
        results = []
        for task, should_succeed in tasks:
            try:
                result = await task
                results.append(("success", result))
                assert should_succeed, "Unexpected success"
            except ValueError as e:
                results.append(("failure", str(e)))
                assert not should_succeed, "Unexpected failure"

        # Verify all operations completed and no memory leaks
        assert len(results) == 50
        assert len(manager.get_active_recoveries()) == 0  # All cleaned up

        # Count successful vs failed operations
        successes = sum(1 for r in results if r[0] == "success")
        failures = sum(1 for r in results if r[0] == "failure")

        # Should have ~17 successes (every 3rd) and ~33 failures
        assert 15 <= successes <= 20  # Allow some variance
        assert 30 <= failures <= 35


class TestIntegration:
    """Integration tests for the complete error recovery system."""

    @pytest.mark.integration
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
            operation_name="download_video",
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
