"""Comprehensive tests for FixedDelayStrategy retry logic."""

import pytest
from services.error_recovery.retry.strategies import FixedDelayStrategy
from services.error_recovery.base import RetryConfig, RetryReason


class TestFixedDelayStrategy:
    """Test FixedDelayStrategy comprehensive functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=10.0,  # Not used by FixedDelayStrategy
            exponential_base=2.0,  # Not used by FixedDelayStrategy
            jitter=False,  # Disable jitter for predictable tests
        )
        self.strategy = FixedDelayStrategy(self.config)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_initial_state(self):
        """Test initial strategy state."""
        assert self.strategy.total_attempts == 0
        assert self.strategy.successful_attempts == 0
        assert self.strategy.failed_attempts == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fixed_delay_without_jitter(self):
        """Test that delay is always base_delay when jitter is disabled."""
        expected_delay = self.config.base_delay

        # Test multiple attempts - should always return same delay
        for attempt in range(5):
            for reason in [
                RetryReason.NETWORK_ERROR,
                RetryReason.TIMEOUT,
                RetryReason.RATE_LIMITED,
            ]:
                delay = await self.strategy.get_delay(attempt, reason)
                assert delay == expected_delay

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fixed_delay_with_jitter(self):
        """Test that delay varies when jitter is enabled."""
        config_with_jitter = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=True,
        )
        strategy_with_jitter = FixedDelayStrategy(config_with_jitter)

        # Get multiple delay values - they should vary due to jitter
        delays = []
        for _ in range(20):  # More samples to increase chance of variation
            delay = await strategy_with_jitter.get_delay(1, RetryReason.NETWORK_ERROR)
            delays.append(delay)

        # With jitter, we should see some variation in delays
        unique_delays = set(delays)
        assert len(unique_delays) > 1, "Jitter should produce varying delays"

        # All delays should be around base_delay (within jitter range)
        base_delay = config_with_jitter.base_delay
        jitter_range = base_delay * 0.1
        min_expected = base_delay - jitter_range
        max_expected = base_delay + jitter_range

        for delay in delays:
            assert (
                min_expected <= delay <= max_expected
            ), f"Delay {delay} outside expected jitter range"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_jitter_range_calculation(self):
        """Test that jitter produces delays within expected range."""
        config_with_jitter = RetryConfig(max_attempts=5, base_delay=5.0, jitter=True)
        strategy_with_jitter = FixedDelayStrategy(config_with_jitter)

        # Expected jitter range: base_delay ± (base_delay * 0.1)
        base_delay = 5.0
        jitter_amount = base_delay * 0.1  # 0.5
        min_expected = base_delay - jitter_amount  # 4.5
        max_expected = base_delay + jitter_amount  # 5.5

        # Test multiple delays to ensure they're in range
        for _ in range(50):
            delay = await strategy_with_jitter.get_delay(1, RetryReason.NETWORK_ERROR)
            assert (
                min_expected <= delay <= max_expected
            ), f"Delay {delay} outside jitter range [{min_expected}, {max_expected}]"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delay_never_negative(self):
        """Test that delay is never negative (max(0, delay) constraint)."""
        # This shouldn't normally happen with FixedDelayStrategy, but test the constraint
        config = RetryConfig(
            max_attempts=5, base_delay=0.1, jitter=True  # Small base delay
        )
        strategy = FixedDelayStrategy(config)

        # Even with jitter, delay should never be negative
        for _ in range(100):
            delay = await strategy.get_delay(1, RetryReason.NETWORK_ERROR)
            assert delay >= 0, f"Delay should never be negative, got {delay}"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_should_retry_within_max_attempts(self):
        """Test should_retry returns True when within max_attempts."""
        exception = Exception("test error")

        # Should retry for attempts below max
        for attempt in range(self.config.max_attempts):
            should_retry = await self.strategy.should_retry(
                attempt, exception, RetryReason.NETWORK_ERROR
            )
            assert (
                should_retry is True
            ), f"Should retry for attempt {attempt} (max: {self.config.max_attempts})"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_should_retry_at_max_attempts(self):
        """Test should_retry returns False when at max_attempts."""
        exception = Exception("test error")

        # Should not retry when at max attempts
        should_retry = await self.strategy.should_retry(
            self.config.max_attempts, exception, RetryReason.NETWORK_ERROR
        )
        assert should_retry is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_should_retry_beyond_max_attempts(self):
        """Test should_retry returns False when beyond max_attempts."""
        exception = Exception("test error")

        # Should not retry when beyond max attempts
        for attempt in range(
            self.config.max_attempts + 1, self.config.max_attempts + 5
        ):
            should_retry = await self.strategy.should_retry(
                attempt, exception, RetryReason.NETWORK_ERROR
            )
            assert (
                should_retry is False
            ), f"Should not retry for attempt {attempt} (max: {self.config.max_attempts})"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_should_retry_different_exceptions(self):
        """Test should_retry works with different exception types."""
        exceptions = [
            Exception("generic error"),
            ValueError("value error"),
            ConnectionError("connection error"),
            TimeoutError("timeout error"),
        ]

        for exception in exceptions:
            should_retry = await self.strategy.should_retry(
                1, exception, RetryReason.NETWORK_ERROR
            )
            assert (
                should_retry is True
            ), f"Should retry regardless of exception type: {type(exception)}"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_should_retry_different_retry_reasons(self):
        """Test should_retry works with different retry reasons."""
        exception = Exception("test error")
        reasons = [
            RetryReason.NETWORK_ERROR,
            RetryReason.SERVICE_UNAVAILABLE,
            RetryReason.RATE_LIMITED,
            RetryReason.TIMEOUT,
        ]

        for reason in reasons:
            should_retry = await self.strategy.should_retry(1, exception, reason)
            assert (
                should_retry is True
            ), f"Should retry regardless of retry reason: {reason}"

    @pytest.mark.unit
    def test_record_attempt_success_metrics(self):
        """Test metrics tracking for successful attempts."""
        # Record several successful attempts
        for _ in range(3):
            self.strategy.record_attempt(True)

        assert self.strategy.total_attempts == 3
        assert self.strategy.successful_attempts == 3
        assert self.strategy.failed_attempts == 0

    @pytest.mark.unit
    def test_record_attempt_failure_metrics(self):
        """Test metrics tracking for failed attempts."""
        # Record several failed attempts
        for _ in range(4):
            self.strategy.record_attempt(False)

        assert self.strategy.total_attempts == 4
        assert self.strategy.successful_attempts == 0
        assert self.strategy.failed_attempts == 4

    @pytest.mark.unit
    def test_record_attempt_mixed_metrics(self):
        """Test metrics tracking for mixed success/failure attempts."""
        # Record mixed attempts: success, failure, success, failure, success
        attempts = [True, False, True, False, True]
        for success in attempts:
            self.strategy.record_attempt(success)

        assert self.strategy.total_attempts == 5
        assert self.strategy.successful_attempts == 3
        assert self.strategy.failed_attempts == 2

    @pytest.mark.unit
    def test_record_attempt_with_retry_reasons(self):
        """Test that retry reasons don't affect metrics (FixedDelayStrategy ignores them)."""
        reasons = [RetryReason.NETWORK_ERROR, RetryReason.TIMEOUT, None]

        for i, reason in enumerate(reasons):
            self.strategy.record_attempt(True, reason)

        # Metrics should be tracked regardless of retry reason
        assert self.strategy.total_attempts == len(reasons)
        assert self.strategy.successful_attempts == len(reasons)
        assert self.strategy.failed_attempts == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_attempt_independence(self):
        """Test that attempt number doesn't affect delay calculation."""
        # Unlike exponential backoff, fixed delay should be same for all attempts
        expected_delay = self.config.base_delay

        attempt_numbers = [0, 1, 5, 10, 100]
        for attempt in attempt_numbers:
            delay = await self.strategy.get_delay(attempt, RetryReason.NETWORK_ERROR)
            assert (
                delay == expected_delay
            ), f"Delay should be fixed regardless of attempt number {attempt}"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reason_independence(self):
        """Test that retry reason doesn't affect delay calculation."""
        expected_delay = self.config.base_delay

        reasons = [
            RetryReason.NETWORK_ERROR,
            RetryReason.SERVICE_UNAVAILABLE,
            RetryReason.RATE_LIMITED,
            RetryReason.TIMEOUT,
        ]

        for reason in reasons:
            delay = await self.strategy.get_delay(1, reason)
            assert (
                delay == expected_delay
            ), f"Delay should be fixed regardless of retry reason {reason}"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_concurrent_usage(self):
        """Test strategy can be used concurrently without interference."""
        import asyncio

        async def get_delay_multiple_times():
            delays = []
            for _ in range(10):
                delay = await self.strategy.get_delay(1, RetryReason.NETWORK_ERROR)
                delays.append(delay)
            return delays

        # Run multiple concurrent tasks
        tasks = [get_delay_multiple_times() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # All delays should be the same (base_delay) since jitter is disabled
        expected_delay = self.config.base_delay
        for delay_list in results:
            for delay in delay_list:
                assert delay == expected_delay

    @pytest.mark.unit
    def test_config_independence(self):
        """Test that multiple strategies with different configs work independently."""
        config1 = RetryConfig(max_attempts=3, base_delay=1.0)
        config2 = RetryConfig(max_attempts=7, base_delay=3.0)

        strategy1 = FixedDelayStrategy(config1)
        strategy2 = FixedDelayStrategy(config2)

        # Record different attempts on each strategy
        strategy1.record_attempt(True)
        strategy1.record_attempt(False)

        strategy2.record_attempt(False)
        strategy2.record_attempt(False)
        strategy2.record_attempt(True)

        # Verify they maintain separate state
        assert strategy1.total_attempts == 2
        assert strategy1.successful_attempts == 1
        assert strategy1.failed_attempts == 1

        assert strategy2.total_attempts == 3
        assert strategy2.successful_attempts == 1
        assert strategy2.failed_attempts == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_edge_case_zero_base_delay(self):
        """Test behavior with zero base delay."""
        config = RetryConfig(max_attempts=3, base_delay=0.0, jitter=False)
        strategy = FixedDelayStrategy(config)

        delay = await strategy.get_delay(1, RetryReason.NETWORK_ERROR)
        assert delay == 0.0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_edge_case_very_large_base_delay(self):
        """Test behavior with very large base delay."""
        config = RetryConfig(
            max_attempts=3, base_delay=1000.0, max_delay=2000.0, jitter=False
        )
        strategy = FixedDelayStrategy(config)

        delay = await strategy.get_delay(1, RetryReason.NETWORK_ERROR)
        assert delay == 1000.0
