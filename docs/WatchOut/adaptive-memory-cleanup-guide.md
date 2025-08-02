# Adaptive Memory Cleanup Guide

**Status**: ✅ COMPLETE - Based on memory leak analysis during retry strategy development
**Date**: 2025-01-31
**Context**: Long-Running Operation Memory Growth in AdaptiveStrategy

## Overview

This guide addresses memory accumulation patterns in long-running operations, particularly in sliding window-based adaptive retry strategies. The core issue is that metrics collection and sliding window data structures can grow unbounded during extended retry sequences, leading to memory leaks in production.

## 🚨 The Core Problem: Unbounded Sliding Window Growth

### Issue Description

Adaptive retry strategies use sliding windows to track success/failure patterns over time. Without proper cleanup, these windows accumulate:
- Historical retry attempt records
- Metrics data points
- Timing information
- Error context objects

### Manifestation

```python
# ❌ PROBLEMATIC PATTERN: Unbounded sliding window
class AdaptiveStrategy:
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.recent_attempts = []  # Grows indefinitely!
        self.metrics_history = []  # Accumulates without cleanup!

    async def should_retry(self, error: Exception) -> bool:
        # Add to history without cleanup
        self.recent_attempts.append({
            'timestamp': datetime.now(),
            'error': error,  # Holds reference to potentially large objects
            'context': get_error_context(error)
        })

        # Window size not enforced!
        if len(self.recent_attempts) > self.window_size:
            # ❌ WRONG: No cleanup happens
            pass
```

**Result**: Memory grows linearly with retry attempts, never being reclaimed.

## 🎯 **Solution Patterns**

### Pattern 1: Proactive Window Trimming (Recommended)

Enforce sliding window size limits at every insertion:

```python
# ✅ SOLUTION: Proactive window management
class AdaptiveStrategy:
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.recent_attempts = deque(maxlen=window_size)  # Built-in size limit
        self.metrics_history = deque(maxlen=window_size)

    async def should_retry(self, error: Exception) -> bool:
        # Add to history with automatic cleanup
        attempt_record = {
            'timestamp': datetime.now(),
            'error_type': type(error).__name__,  # Store type, not object
            'error_message': str(error)[:200],   # Truncate long messages
        }

        self.recent_attempts.append(attempt_record)
        # deque automatically removes oldest when maxlen exceeded

        return self._calculate_retry_decision()
```

### Pattern 2: Periodic Cleanup with Time-Based Expiry

For more complex scenarios, implement time-based expiry:

```python
# ✅ SOLUTION: Time-based cleanup
class AdaptiveStrategy:
    def __init__(self, window_duration: timedelta = timedelta(minutes=30)):
        self.window_duration = window_duration
        self.recent_attempts = []
        self.last_cleanup = datetime.now()

    def _cleanup_expired_entries(self):
        """Remove entries older than window_duration."""
        now = datetime.now()
        cutoff_time = now - self.window_duration

        # Remove expired entries
        self.recent_attempts = [
            attempt for attempt in self.recent_attempts
            if attempt['timestamp'] > cutoff_time
        ]

        self.last_cleanup = now

    async def should_retry(self, error: Exception) -> bool:
        # Periodic cleanup (every 100 attempts or 5 minutes)
        if (len(self.recent_attempts) % 100 == 0 or
            datetime.now() - self.last_cleanup > timedelta(minutes=5)):
            self._cleanup_expired_entries()

        # Add new attempt
        self.recent_attempts.append({
            'timestamp': datetime.now(),
            'error_type': type(error).__name__,
            'success_rate': self._calculate_recent_success_rate()
        })

        return self._calculate_retry_decision()
```

### Pattern 3: Resource-Aware Cleanup

Monitor memory usage and trigger aggressive cleanup when needed:

```python
# ✅ SOLUTION: Resource-aware cleanup
import psutil
from typing import Optional

class AdaptiveStrategy:
    def __init__(self, memory_threshold_mb: int = 100):
        self.memory_threshold_mb = memory_threshold_mb
        self.recent_attempts = []
        self.aggressive_cleanup_triggered = False

    def _get_memory_usage_mb(self) -> float:
        """Get current process memory usage in MB."""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024

    def _aggressive_cleanup(self):
        """Perform aggressive cleanup when memory threshold exceeded."""
        # Keep only the most recent 100 entries
        if len(self.recent_attempts) > 100:
            self.recent_attempts = self.recent_attempts[-100:]

        # Clear large objects
        for attempt in self.recent_attempts:
            if 'error_context' in attempt:
                del attempt['error_context']

        self.aggressive_cleanup_triggered = True

    async def should_retry(self, error: Exception) -> bool:
        # Check memory usage
        current_memory = self._get_memory_usage_mb()

        if current_memory > self.memory_threshold_mb:
            self._aggressive_cleanup()

        # Simplified attempt record for memory efficiency
        attempt_record = {
            'timestamp': datetime.now(),
            'error_type': type(error).__name__,
        }

        self.recent_attempts.append(attempt_record)
        return self._calculate_retry_decision()
```

## 🔧 **Testing Memory Cleanup**

### Memory Leak Test Pattern

```python
# ✅ CORRECT: Memory leak test for adaptive strategies
import pytest
from tests.memory.memory_leak_detection import MemoryProfiler

@pytest.mark.memory
async def test_adaptive_strategy_memory_cleanup():
    """Test that AdaptiveStrategy doesn't leak memory during long sequences."""

    profiler = MemoryProfiler()
    strategy = AdaptiveStrategy(window_size=100)

    # Capture baseline
    profiler.start()

    # Simulate 1000 retry attempts (10x window size)
    for i in range(1000):
        await strategy.should_retry(Exception(f"Test error {i}"))

        # Check memory every 100 attempts
        if i % 100 == 0:
            current_memory = profiler.get_current_memory_mb()
            assert current_memory < 50, f"Memory exceeded threshold at attempt {i}"

    # Final memory should be stable
    final_memory = profiler.get_current_memory_mb()
    assert final_memory < 20, "Final memory usage too high"

    # Window should be properly bounded
    assert len(strategy.recent_attempts) <= strategy.window_size
```

## 🚨 **Anti-Patterns to Avoid**

### Anti-Pattern 1: No Cleanup Logic

```python
# ❌ ANTI-PATTERN: Unbounded growth
class AdaptiveStrategy:
    def __init__(self):
        self.history = []

    async def should_retry(self, error):
        self.history.append(error)  # Never cleaned up!
        return len(self.history) < 100
```

### Anti-Pattern 2: Holding Large Object References

```python
# ❌ ANTI-PATTERN: Retaining large objects
attempt_record = {
    'error': error,           # Holds entire exception object
    'request': large_request, # Holds large request data
    'response': response,     # Holds response data
}
```

### Anti-Pattern 3: Infrequent Cleanup

```python
# ❌ ANTI-PATTERN: Cleanup only on explicit calls
class AdaptiveStrategy:
    def cleanup(self):  # ❌ Requires manual calls
        self.history = self.history[-100:]

    async def should_retry(self, error):
        # No automatic cleanup!
        return self._decide()
```

## 🎯 **Best Practices**

### 1. Choose Appropriate Data Structures
- Use `collections.deque(maxlen=N)` for fixed-size windows
- Use `weakref` for object references that can be garbage collected
- Store minimal data (types, messages) rather than full objects

### 2. Implement Automatic Cleanup
- Cleanup on every operation (preferred)
- Periodic cleanup based on time or operation count
- Resource-aware cleanup based on memory thresholds

### 3. Monitor and Test
- Include memory leak tests for all adaptive strategies
- Set up monitoring for production memory usage
- Use memory profiling during development

### 4. Configuration
```python
# ✅ GOOD: Configurable cleanup behavior
@dataclass
class AdaptiveConfig:
    window_size: int = 1000
    cleanup_frequency: int = 100  # Cleanup every N operations
    memory_threshold_mb: int = 100
    max_error_message_length: int = 200
```

## 🚀 **Quick Fix Checklist**

When implementing sliding window adaptive strategies:

- [ ] **Use bounded data structures**: `deque(maxlen=N)` or manual size enforcement
- [ ] **Store minimal data**: Error types and messages, not full objects
- [ ] **Implement automatic cleanup**: Don't rely on manual cleanup calls
- [ ] **Add memory leak tests**: Test with 10x+ window size operations
- [ ] **Monitor memory usage**: Set up alerts for memory growth
- [ ] **Configure cleanup behavior**: Make thresholds configurable
- [ ] **Document cleanup logic**: Clear comments about when/how cleanup occurs

## 📚 **Related Patterns**

- **Memory Testing**: See `memory-leak-testing-guide.md` for testing techniques
- **Error Recovery**: See `error-recovery-patterns-guide.md` for strategy patterns
- **Circuit Breaker**: See `circuit-breaker-guide.md` for related state management

---

**Key Insight**: Sliding windows in production systems require active memory management. Automatic cleanup should be built into the data structure design, not added as an afterthought.
