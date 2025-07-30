"""Comprehensive tests for AdaptiveStrategy retry logic."""

import pytest
from services.error_recovery.retry.strategies import AdaptiveStrategy
from services.error_recovery.base import RetryConfig, RetryReason


class TestAdaptiveStrategy:
    """Test AdaptiveStrategy comprehensive functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = RetryConfig(
            max_attempts=5,
            base_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=False,  # Disable jitter for predictable tests
        )
        self.strategy = AdaptiveStrategy(self.config)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_initial_state(self):
        """Test initial strategy state."""
        assert self.strategy.total_attempts == 0
        assert self.strategy.successful_attempts == 0
        assert self.strategy.failed_attempts == 0
        assert self.strategy.recent_attempts == []
        assert self.strategy.adaptation_window == 10
        assert (
            self.strategy._calculate_success_rate() == 1.0
        )  # Default when no attempts

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_success_rate_calculation_empty(self):
        """Test success rate calculation with no attempts."""
        success_rate = self.strategy._calculate_success_rate()
        assert success_rate == 1.0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_success_rate_calculation_mixed_results(self):
        """Test success rate calculation with mixed success/failure results."""
        # Add some mixed results
        results = [True, False, True, True, False, True, False, True, True, True]
        for result in results:
            self.strategy.record_attempt(result)

        success_rate = self.strategy._calculate_success_rate()
        expected_rate = 7 / 10  # 7 successes out of 10
        assert success_rate == expected_rate

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_success_rate_calculation_all_failures(self):
        """Test success rate calculation with all failures."""
        # Add all failures
        for _ in range(5):
            self.strategy.record_attempt(False)

        success_rate = self.strategy._calculate_success_rate()
        assert success_rate == 0.0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_success_rate_calculation_all_successes(self):
        """Test success rate calculation with all successes."""
        # Add all successes
        for _ in range(5):
            self.strategy.record_attempt(True)

        success_rate = self.strategy._calculate_success_rate()
        assert success_rate == 1.0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sliding_window_management(self):
        """Test that sliding window maintains proper size."""
        # Fill up the window exactly
        for i in range(10):
            self.strategy.record_attempt(i % 2 == 0)  # Alternate success/failure

        assert len(self.strategy.recent_attempts) == 10

        # Add one more - should maintain window size
        self.strategy.record_attempt(True)
        assert len(self.strategy.recent_attempts) == 10

        # Add several more - should still maintain window size
        for _ in range(5):
            self.strategy.record_attempt(False)

        assert len(self.strategy.recent_attempts) == 10

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sliding_window_fifo_behavior(self):
        """Test that sliding window follows FIFO (first in, first out) behavior."""
        # Add known sequence
        sequence = [True, False, True, False, True]
        for result in sequence:
            self.strategy.record_attempt(result)

        assert self.strategy.recent_attempts == sequence

        # Fill up to window size
        for _ in range(5):
            self.strategy.record_attempt(False)

        # Now add a distinctive value that should push out the first element
        self.strategy.record_attempt(True)

        # First element (True) should be gone, and new True should be at the end
        assert self.strategy.recent_attempts[0] is False  # Was second element
        assert self.strategy.recent_attempts[-1] is True  # Newly added

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_early_retry_termination_low_success_rate(self):
        """Test early retry termination when success rate < 30%."""
        # Create a scenario with low success rate (2 successes out of 10 = 20%)
        attempts = [False] * 8 + [True] * 2  # 20% success rate
        for result in attempts:
            self.strategy.record_attempt(result)

        # should_retry should return False due to low success rate
        exception = Exception("test error")
        should_retry = await self.strategy.should_retry(
            2, exception, RetryReason.NETWORK_ERROR
        )
        assert should_retry is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_no_early_termination_good_success_rate(self):
        """Test no early termination when success rate >= 30%."""
        # Create a scenario with acceptable success rate (4 successes out of 10 = 40%)
        attempts = [False] * 6 + [True] * 4  # 40% success rate
        for result in attempts:
            self.strategy.record_attempt(result)

        # should_retry should check normal attempt limits
        exception = Exception("test error")
        should_retry = await self.strategy.should_retry(
            2, exception, RetryReason.NETWORK_ERROR
        )
        assert should_retry is True  # Attempt 2 < max_attempts 5

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_should_retry_max_attempts(self):
        """Test should_retry respects max_attempts limit."""
        exception = Exception("test error")

        # Should retry for attempts below max
        for attempt in range(self.config.max_attempts):
            should_retry = await self.strategy.should_retry(
                attempt, exception, RetryReason.NETWORK_ERROR
            )
            assert should_retry is True

        # Should not retry when at max attempts
        should_retry = await self.strategy.should_retry(
            self.config.max_attempts, exception, RetryReason.NETWORK_ERROR
        )
        assert should_retry is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_dynamic_delay_adjustment_high_success_rate(self):
        """Test delay reduction for high success rate (>= 70%)."""
        # Create high success rate scenario (8 successes out of 10 = 80%)
        attempts = [True] * 8 + [False] * 2
        for result in attempts:
            self.strategy.record_attempt(result)

        delay = await self.strategy.get_delay(1, RetryReason.NETWORK_ERROR)

        # Expected: base_delay * exponential_base^attempt * 0.5 (high success multiplier)
        expected_base = self.config.base_delay * (self.config.exponential_base**1)
        expected_delay = expected_base * 0.5
        expected_delay = min(expected_delay, self.config.max_delay)

        assert delay == expected_delay

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_dynamic_delay_adjustment_medium_success_rate(self):
        """Test increased delay for medium success rate (< 70%)."""
        # Create medium success rate scenario (5 successes out of 10 = 50%)
        attempts = [True] * 5 + [False] * 5
        for result in attempts:
            self.strategy.record_attempt(result)

        delay = await self.strategy.get_delay(1, RetryReason.NETWORK_ERROR)

        # Expected: base_delay * exponential_base^attempt * 2.0 (low success multiplier)
        expected_base = self.config.base_delay * (self.config.exponential_base**1)
        expected_delay = expected_base * 2.0
        expected_delay = min(expected_delay, self.config.max_delay)

        assert delay == expected_delay

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_dynamic_delay_adjustment_low_success_rate(self):
        """Test delay increase for low success rate (< 70%)."""
        # Create low success rate scenario but not low enough for early termination
        # We'll test this without enough samples to trigger early termination
        attempts = [True] * 1 + [False] * 4  # 20% success rate, only 5 samples
        for result in attempts:
            self.strategy.record_attempt(result)

        delay = await self.strategy.get_delay(1, RetryReason.NETWORK_ERROR)

        # Expected: base_delay * exponential_base^attempt * 2.0 (low success multiplier)
        expected_base = self.config.base_delay * (self.config.exponential_base**1)
        expected_delay = expected_base * 2.0
        expected_delay = min(expected_delay, self.config.max_delay)

        assert delay == expected_delay

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delay_respects_max_delay(self):
        """Test that calculated delay never exceeds max_delay."""
        # Create scenario that would normally produce large delay
        attempts = [True] * 1 + [False] * 9  # Very low success rate
        for result in attempts:
            self.strategy.record_attempt(result)

        # Use high attempt number to test max_delay capping
        delay = await self.strategy.get_delay(10, RetryReason.NETWORK_ERROR)

        assert delay <= self.config.max_delay

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_metrics_tracking(self):
        """Test comprehensive metrics tracking."""
        # Record mixed attempts
        results = [True, False, True, True, False, False, True]
        for result in results:
            self.strategy.record_attempt(result)

        # Verify metrics
        assert self.strategy.total_attempts == 7
        assert self.strategy.successful_attempts == 4
        assert self.strategy.failed_attempts == 3

        # Verify recent_attempts tracking
        assert len(self.strategy.recent_attempts) == 7
        assert self.strategy.recent_attempts == results

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_jitter_when_enabled(self):
        """Test jitter behavior when enabled."""
        config_with_jitter = RetryConfig(
            max_attempts=5,
            base_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=True,
        )
        strategy_with_jitter = AdaptiveStrategy(config_with_jitter)

        # Get multiple delay values - they should vary due to jitter
        delays = []
        for _ in range(10):
            delay = await strategy_with_jitter.get_delay(1, RetryReason.NETWORK_ERROR)
            delays.append(delay)

        # With jitter, we should see some variation in delays
        # (not all exactly the same)
        unique_delays = set(delays)
        assert len(unique_delays) > 1, "Jitter should produce varying delays"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_edge_case_empty_window_early_termination_check(self):
        """Test edge case where success rate check happens with empty window."""
        # With empty window, success rate should be 1.0, so no early termination
        exception = Exception("test error")
        should_retry = await self.strategy.should_retry(
            1, exception, RetryReason.NETWORK_ERROR
        )
        assert should_retry is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_adaptation_window_boundary_conditions(self):
        """Test behavior at adaptation window boundaries."""
        # Test at exactly window size
        for i in range(10):
            self.strategy.record_attempt(i < 3)  # 3 successes, 7 failures = 30%

        success_rate = self.strategy._calculate_success_rate()
        assert success_rate == 0.3

        # Should not trigger early termination at exactly 30%
        exception = Exception("test error")
        should_retry = await self.strategy.should_retry(
            1, exception, RetryReason.NETWORK_ERROR
        )
        assert should_retry is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_different_retry_reasons(self):
        """Test strategy works with different retry reasons."""
        exception = Exception("test error")

        # Test different retry reasons
        reasons = [
            RetryReason.NETWORK_ERROR,
            RetryReason.SERVICE_UNAVAILABLE,
            RetryReason.RATE_LIMITED,
            RetryReason.TIMEOUT,
        ]

        for reason in reasons:
            should_retry = await self.strategy.should_retry(1, exception, reason)
            assert should_retry is True

            delay = await self.strategy.get_delay(1, reason)
            assert delay >= 0
