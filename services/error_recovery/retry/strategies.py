"""Concrete retry strategy implementations."""

import random
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from ..contracts import RetryStrategy
from ..types import RetryConfig, RetryReason


class ExponentialBackoffStrategy(RetryStrategy):
    """Exponential backoff retry strategy."""

    def __init__(self, config: RetryConfig):
        self.config = config
        self.total_attempts = 0
        self.successful_attempts = 0
        self.failed_attempts = 0

    async def should_retry(
        self, attempt: int, exception: Exception, reason: RetryReason
    ) -> bool:
        """Check if retry should be attempted."""
        if attempt >= self.config.max_attempts:
            return False

        # Don't retry certain errors
        non_retryable_reasons = {
            RetryReason.QUALITY_NOT_AVAILABLE,  # Quality issue won't resolve
        }

        return reason not in non_retryable_reasons

    async def get_delay(self, attempt: int, reason: RetryReason) -> float:
        """Calculate exponential backoff delay."""
        delay = self.config.base_delay * (self.config.exponential_base**attempt)
        delay = min(delay, self.config.max_delay)

        if self.config.jitter:
            jitter_amount = delay * 0.1
            delay += random.uniform(-jitter_amount, jitter_amount)

        return max(0, delay)

    def record_attempt(self, success: bool, reason: Optional[RetryReason] = None):
        """Record metrics for an attempt."""
        self.total_attempts += 1
        if success:
            self.successful_attempts += 1
        else:
            self.failed_attempts += 1


class CircuitBreakerStrategy(RetryStrategy):
    """Circuit breaker retry strategy."""

    def __init__(self, config: RetryConfig):
        self.config = config
        self.state = "closed"  # closed, open, half_open
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None

        # Metrics
        self.total_attempts = 0
        self.successful_attempts = 0
        self.failed_attempts = 0

    async def should_retry(
        self, attempt: int, exception: Exception, reason: RetryReason
    ) -> bool:
        """Check retry with circuit breaker logic."""
        if self.state == "open":
            # Check if recovery timeout has passed
            if self.last_failure_time and datetime.now(
                timezone.utc
            ) - self.last_failure_time > timedelta(
                seconds=self.config.recovery_timeout
            ):
                self.state = "half_open"
                return attempt < self.config.max_attempts
            return False

        return attempt < self.config.max_attempts

    async def get_delay(self, attempt: int, reason: RetryReason) -> float:
        """Get delay considering circuit breaker state."""
        if self.state == "open":
            # Circuit is open, longer delay
            return self.config.recovery_timeout

        # Normal exponential backoff when circuit is closed/half-open
        delay = self.config.base_delay * (self.config.exponential_base**attempt)
        return min(delay, self.config.max_delay)

    def record_attempt(self, success: bool, reason: Optional[RetryReason] = None):
        """Record attempt and update circuit breaker state."""
        self.total_attempts += 1

        if success:
            self.successful_attempts += 1
            self.failure_count = 0
            if self.state == "half_open":
                self.state = "closed"
        else:
            self.failed_attempts += 1
            self.failure_count += 1
            self.last_failure_time = datetime.now(timezone.utc)

            if self.failure_count >= self.config.failure_threshold:
                self.state = "open"


class AdaptiveStrategy(RetryStrategy):
    """Adaptive retry strategy that adjusts based on recent success rate."""

    def __init__(self, config: RetryConfig, window_size: int = 10):
        self.config = config
        self.recent_attempts: List[bool] = []  # Track recent success/failure
        self.adaptation_window = window_size

        # Metrics
        self.total_attempts = 0
        self.successful_attempts = 0
        self.failed_attempts = 0

    async def should_retry(
        self, attempt: int, exception: Exception, reason: RetryReason
    ) -> bool:
        """Check if retry should be attempted with adaptive logic."""
        if attempt >= self.config.max_attempts:
            return False

        # Be more conservative with retries if success rate is very low
        success_rate = self._calculate_success_rate()
        if success_rate < 0.3 and attempt >= 2:
            return False

        return True

    async def get_delay(self, attempt: int, reason: RetryReason) -> float:
        """Calculate adaptive delay based on recent success rate."""
        success_rate = self._calculate_success_rate()

        # Adjust delay based on success rate
        if success_rate < 0.7:  # Lower success rate = longer delays
            multiplier = 2.0
        else:  # Higher success rate = shorter delays
            multiplier = 0.5

        base_delay = self.config.base_delay * (self.config.exponential_base**attempt)
        delay = base_delay * multiplier
        delay = min(delay, self.config.max_delay)

        if self.config.jitter:
            jitter_amount = delay * 0.1
            delay += random.uniform(-jitter_amount, jitter_amount)

        return max(0, delay)

    def record_attempt(self, success: bool, reason: Optional[RetryReason] = None):
        """Record attempt and maintain sliding window."""
        self.total_attempts += 1
        if success:
            self.successful_attempts += 1
        else:
            self.failed_attempts += 1

        self.recent_attempts.append(success)
        if len(self.recent_attempts) > self.adaptation_window:
            self.recent_attempts.pop(0)

    def _calculate_success_rate(self) -> float:
        """Calculate recent success rate."""
        if not self.recent_attempts:
            return 1.0

        return sum(self.recent_attempts) / len(self.recent_attempts)


class FixedDelayStrategy(RetryStrategy):
    """Fixed delay retry strategy."""

    def __init__(self, config: RetryConfig):
        self.config = config
        self.total_attempts = 0
        self.successful_attempts = 0
        self.failed_attempts = 0

    async def should_retry(
        self, attempt: int, exception: Exception, reason: RetryReason
    ) -> bool:
        """Check if retry should be attempted."""
        return attempt < self.config.max_attempts

    async def get_delay(self, attempt: int, reason: RetryReason) -> float:
        """Return fixed delay."""
        delay = self.config.base_delay

        if self.config.jitter:
            jitter_amount = delay * 0.1
            delay += random.uniform(-jitter_amount, jitter_amount)

        return max(0, delay)

    def record_attempt(self, success: bool, reason: Optional[RetryReason] = None):
        """Record metrics for an attempt."""
        self.total_attempts += 1
        if success:
            self.successful_attempts += 1
        else:
            self.failed_attempts += 1
