"""
Memory leak tests for retry system components.

This module contains comprehensive tests to detect memory leaks and excessive
memory usage during long retry sequences, particularly focusing on:
- AdaptiveStrategy sliding window management
- ErrorRecoveryManager active recovery tracking
- Circuit breaker state management
- Long-running retry sequences
"""

import asyncio
import gc
import os
import psutil
import pytest

from services.error_recovery.base import ErrorRecoveryManager
from services.error_recovery.retry.strategies import (
    AdaptiveStrategy,
    CircuitBreakerStrategy,
    ExponentialBackoffStrategy,
    FixedDelayStrategy,
)
from services.error_recovery.types import ErrorContext, RetryConfig, RetryReason
from services.error_recovery.reporting import BasicErrorReporter


class MemoryProfiler:
    """Simple memory profiler for tracking memory usage during tests."""

    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.initial_memory = None
        self.measurements = []

    def start_profiling(self):
        """Start memory profiling."""
        gc.collect()  # Force garbage collection
        self.initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.measurements = [self.initial_memory]
        return self.initial_memory

    def measure(self, label: str = ""):
        """Take a memory measurement."""
        gc.collect()  # Force garbage collection
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.measurements.append(current_memory)
        growth = current_memory - self.initial_memory
        print(f"Memory {label}: {current_memory:.1f} MB (growth: {growth:+.1f} MB)")
        return current_memory

    def get_peak_growth(self) -> float:
        """Get peak memory growth during profiling."""
        if not self.measurements:
            return 0.0
        return max(self.measurements) - self.initial_memory

    def get_final_growth(self) -> float:
        """Get final memory growth after cleanup."""
        if len(self.measurements) < 2:
            return 0.0
        return self.measurements[-1] - self.initial_memory


@pytest.fixture
def memory_profiler():
    """Create memory profiler for tests."""
    return MemoryProfiler()


class TestAdaptiveStrategyMemoryLeaks:
    """Test memory leaks in AdaptiveStrategy during long retry sequences."""

    @pytest.mark.memory
    @pytest.mark.asyncio
    async def test_sliding_window_memory_usage(self, memory_profiler: MemoryProfiler):
        """Test memory usage during extended retry sequences with large sliding windows."""
        profiler = memory_profiler
        profiler.start_profiling()

        # Create adaptive strategy with large sliding window
        config = RetryConfig(
            max_attempts=1000,
            base_delay=0.001,  # Very small delay for fast testing
            max_delay=10.0,  # Keep delays reasonable for testing
        )
        strategy = AdaptiveStrategy(config)

        profiler.measure("after_strategy_creation")

        # Simulate long retry sequence with varying success/failure patterns
        for cycle in range(10):  # 10 cycles of 100 operations each
            profiler.measure(f"cycle_{cycle}_start")

            # Simulate mixed success/failure pattern
            for i in range(100):
                attempt = cycle * 100 + i

                # Create varying error patterns
                error: Exception
                if i % 3 == 0:
                    error = ConnectionError(f"Connection failed #{attempt}")
                elif i % 5 == 0:
                    error = TimeoutError(f"Timeout #{attempt}")
                else:
                    error = RuntimeError(f"Runtime error #{attempt}")

                # Test should_retry (this updates sliding window)
                await strategy.should_retry(attempt, error, RetryReason.NETWORK_ERROR)

                # Simulate success rate variations
                if i % 4 == 0:  # 25% success rate
                    strategy.record_attempt(success=True)

                # Get delay (exercises delay calculation)
                await strategy.get_delay(attempt, RetryReason.NETWORK_ERROR)

            profiler.measure(f"cycle_{cycle}_end")

        # Force cleanup
        del strategy
        gc.collect()

        profiler.measure("final_cleanup")

        # Verify memory usage is reasonable
        peak_growth = profiler.get_peak_growth()
        final_growth = profiler.get_final_growth()

        print(f"Peak memory growth: {peak_growth:.1f} MB")
        print(f"Final memory growth: {final_growth:.1f} MB")

        # Memory thresholds for large sliding window operations
        assert peak_growth < 50.0, f"Peak memory growth too high: {peak_growth:.1f} MB"
        assert final_growth < 10.0, f"Memory leak detected: {final_growth:.1f} MB"

    @pytest.mark.memory
    @pytest.mark.asyncio
    async def test_success_rate_calculation_memory(
        self, memory_profiler: MemoryProfiler
    ):
        """Test memory usage during extensive success rate calculations."""
        profiler = memory_profiler
        profiler.start_profiling()

        config = RetryConfig(
            max_attempts=2000,
            base_delay=0.001,
            window_size=1000,  # Very large window
        )
        strategy = AdaptiveStrategy(config)

        profiler.measure("after_strategy_creation")

        # Simulate many success/failure recordings
        for batch in range(20):  # 20 batches of 100 operations
            profiler.measure(f"batch_{batch}_start")

            for i in range(100):
                # Alternating success/failure pattern
                if i % 2 == 0:
                    strategy.record_attempt(success=True)
                else:
                    strategy.record_attempt(success=False)

                # Calculate success rate for this window
                strategy._calculate_success_rate()

                # Test should_retry method (exercises termination logic)
                await strategy.should_retry(
                    batch * 100 + i, RuntimeError("test"), RetryReason.NETWORK_ERROR
                )

            profiler.measure(f"batch_{batch}_end")

        # Cleanup
        del strategy
        gc.collect()

        profiler.measure("final_cleanup")

        # Verify memory usage
        peak_growth = profiler.get_peak_growth()
        final_growth = profiler.get_final_growth()

        print(f"Success rate calculation - Peak growth: {peak_growth:.1f} MB")
        print(f"Success rate calculation - Final growth: {final_growth:.1f} MB")

        assert peak_growth < 30.0, f"Peak memory growth too high: {peak_growth:.1f} MB"
        assert final_growth < 5.0, f"Memory leak detected: {final_growth:.1f} MB"


class TestErrorRecoveryManagerMemoryLeaks:
    """Test memory leaks in ErrorRecoveryManager during long-running operations."""

    @pytest.mark.memory
    @pytest.mark.asyncio
    async def test_active_recovery_tracking_memory(
        self, memory_profiler: MemoryProfiler
    ):
        """Test memory usage during extensive active recovery tracking."""
        profiler = memory_profiler
        profiler.start_profiling()

        # Create error recovery manager
        strategy = ExponentialBackoffStrategy(RetryConfig(max_attempts=50))
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        profiler.measure("after_manager_creation")

        # Simulate many concurrent recovery operations
        async def failing_operation(
            operation_id: int, recovery_manager: ErrorRecoveryManager
        ):
            """Simulate a failing operation that gets retried."""
            call_count = 0

            async def mock_operation():
                nonlocal call_count
                call_count += 1
                if call_count < 5:  # Fail first 4 times
                    raise ConnectionError(
                        f"Failed operation {operation_id}, attempt {call_count}"
                    )
                return f"success_{operation_id}"

            context = ErrorContext(
                operation_name=f"test_operation_{operation_id}",
                video_id=f"video_{operation_id}",
                operation_context={"batch": operation_id // 10},
            )

            result = await recovery_manager.execute_with_retry(
                mock_operation, context, RetryConfig(max_attempts=10)
            )
            return result

        # Run multiple batches of concurrent operations
        for batch in range(5):  # 5 batches
            profiler.measure(f"batch_{batch}_start")

            # Create 20 concurrent operations per batch
            tasks = [failing_operation(batch * 20 + i, manager) for i in range(20)]

            # Execute batch concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify results
            successful_results = [
                r for r in results if isinstance(r, str) and r.startswith("success_")
            ]
            assert (
                len(successful_results) == 20
            ), f"Batch {batch}: Expected 20 successes, got {len(successful_results)}"

            profiler.measure(f"batch_{batch}_end")

        # Force cleanup
        del manager, strategy, reporter
        gc.collect()

        profiler.measure("final_cleanup")

        # Verify memory usage
        peak_growth = profiler.get_peak_growth()
        final_growth = profiler.get_final_growth()

        print(f"Active recovery tracking - Peak growth: {peak_growth:.1f} MB")
        print(f"Active recovery tracking - Final growth: {final_growth:.1f} MB")

        assert peak_growth < 40.0, f"Peak memory growth too high: {peak_growth:.1f} MB"
        assert final_growth < 8.0, f"Memory leak detected: {final_growth:.1f} MB"

    @pytest.mark.memory
    @pytest.mark.asyncio
    async def test_error_context_cleanup_memory(self, memory_profiler: MemoryProfiler):
        """Test memory cleanup of error contexts during long operations."""
        profiler = memory_profiler
        profiler.start_profiling()

        strategy = FixedDelayStrategy(RetryConfig(max_attempts=20, base_delay=0.001))
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        profiler.measure("after_manager_creation")

        # Create many error contexts with large data
        contexts_created = 0

        for batch in range(10):
            profiler.measure(f"context_batch_{batch}_start")

            for i in range(50):
                contexts_created += 1

                # Create error context with substantial data
                large_context_data = {
                    "batch_id": batch,
                    "operation_id": i,
                    "metadata": {
                        "video_data": "x" * 1000,  # 1KB of dummy data
                        "processing_info": [j for j in range(100)],
                        "retry_history": [f"attempt_{k}" for k in range(20)],
                    },
                }

                context = ErrorContext(
                    operation_name=f"large_context_op_{contexts_created}",
                    video_id=f"video_{contexts_created}",
                    operation_context=large_context_data,
                )

                # Use context in recovery operation
                async def mock_operation():
                    # Access context data to ensure it's retained during operation
                    data_size = len(str(context.operation_context))
                    if contexts_created % 10 == 0:
                        raise RuntimeError(f"Simulated failure {contexts_created}")
                    return f"processed_{data_size}_bytes"

                try:
                    await manager.execute_with_retry(
                        mock_operation, context, RetryConfig(max_attempts=3)
                    )
                except Exception:
                    pass  # Some operations are expected to fail

            profiler.measure(f"context_batch_{batch}_end")

        # Force cleanup
        del manager, strategy, reporter
        gc.collect()

        profiler.measure("final_cleanup")

        # Verify memory usage
        peak_growth = profiler.get_peak_growth()
        final_growth = profiler.get_final_growth()

        print(f"Error context cleanup - Peak growth: {peak_growth:.1f} MB")
        print(f"Error context cleanup - Final growth: {final_growth:.1f} MB")
        print(f"Total contexts created: {contexts_created}")

        assert peak_growth < 60.0, f"Peak memory growth too high: {peak_growth:.1f} MB"
        assert final_growth < 15.0, f"Memory leak detected: {final_growth:.1f} MB"


class TestCircuitBreakerMemoryLeaks:
    """Test memory leaks in CircuitBreakerStrategy during state transitions."""

    @pytest.mark.memory
    @pytest.mark.asyncio
    async def test_state_transition_memory(self, memory_profiler: MemoryProfiler):
        """Test memory usage during extensive state transitions."""
        profiler = memory_profiler
        profiler.start_profiling()

        config = RetryConfig(
            max_attempts=100,
            failure_threshold=5,
            recovery_timeout=0.01,  # Very short for fast testing
        )
        strategy = CircuitBreakerStrategy(config)

        profiler.measure("after_circuit_breaker_creation")

        # Simulate many state transitions
        for cycle in range(20):
            profiler.measure(f"transition_cycle_{cycle}_start")

            # Accumulate failures to open circuit
            for i in range(6):  # Exceed failure threshold
                await strategy.should_retry(
                    i,
                    ConnectionError(f"Failure {cycle}-{i}"),
                    RetryReason.NETWORK_ERROR,
                )
                # Record the failure to trigger state transition
                strategy.record_attempt(success=False, reason=RetryReason.NETWORK_ERROR)

            # Circuit should be open now
            assert strategy.state == "open"

            # Wait for recovery timeout
            await asyncio.sleep(0.02)  # Slightly longer than recovery_timeout

            # Test transition to half_open
            await strategy.should_retry(
                0, ConnectionError("Test"), RetryReason.NETWORK_ERROR
            )

            # Simulate success to close circuit
            strategy.record_attempt(success=True)

            # Circuit should be closed now
            assert strategy.state == "closed"

            profiler.measure(f"transition_cycle_{cycle}_end")

        # Cleanup
        del strategy
        gc.collect()

        profiler.measure("final_cleanup")

        # Verify memory usage
        peak_growth = profiler.get_peak_growth()
        final_growth = profiler.get_final_growth()

        print(f"Circuit breaker transitions - Peak growth: {peak_growth:.1f} MB")
        print(f"Circuit breaker transitions - Final growth: {final_growth:.1f} MB")

        assert peak_growth < 25.0, f"Peak memory growth too high: {peak_growth:.1f} MB"
        assert final_growth < 3.0, f"Memory leak detected: {final_growth:.1f} MB"


class TestLongRunningRetrySequences:
    """Test memory usage during very long retry sequences."""

    @pytest.mark.memory
    @pytest.mark.asyncio
    async def test_extended_retry_sequence_memory(
        self, memory_profiler: MemoryProfiler
    ):
        """Test memory usage during very long retry sequences (1000+ attempts)."""
        profiler = memory_profiler
        profiler.start_profiling()

        # Create multiple strategies for comprehensive testing
        strategies = {
            "adaptive": AdaptiveStrategy(
                RetryConfig(max_attempts=1000, window_size=100)
            ),
            "exponential": ExponentialBackoffStrategy(RetryConfig(max_attempts=1000)),
            "fixed": FixedDelayStrategy(
                RetryConfig(max_attempts=1000, base_delay=0.001)
            ),
            "circuit": CircuitBreakerStrategy(
                RetryConfig(max_attempts=1000, failure_threshold=50)
            ),
        }

        profiler.measure("after_strategies_creation")

        # Test each strategy with extended sequences
        for strategy_name, strategy in strategies.items():
            profiler.measure(f"{strategy_name}_start")

            # Simulate long retry sequence
            for attempt in range(500):  # 500 attempts per strategy
                error = ConnectionError(f"{strategy_name}_error_{attempt}")

                should_retry = await strategy.should_retry(
                    attempt, error, RetryReason.NETWORK_ERROR
                )

                if should_retry:
                    await strategy.get_delay(attempt, RetryReason.NETWORK_ERROR)
                    # Don't actually sleep, just calculate delay

                # Occasionally record success to keep adaptive strategy active
                if attempt % 20 == 0 and hasattr(strategy, "record_attempt"):
                    strategy.record_attempt(success=True)

            profiler.measure(f"{strategy_name}_end")

        # Cleanup all strategies
        for strategy in strategies.values():
            del strategy
        gc.collect()

        profiler.measure("final_cleanup")

        # Verify memory usage
        peak_growth = profiler.get_peak_growth()
        final_growth = profiler.get_final_growth()

        print(f"Extended retry sequences - Peak growth: {peak_growth:.1f} MB")
        print(f"Extended retry sequences - Final growth: {final_growth:.1f} MB")

        assert peak_growth < 80.0, f"Peak memory growth too high: {peak_growth:.1f} MB"
        assert final_growth < 20.0, f"Memory leak detected: {final_growth:.1f} MB"

    @pytest.mark.memory
    @pytest.mark.asyncio
    async def test_concurrent_long_sequences_memory(
        self, memory_profiler: MemoryProfiler
    ):
        """Test memory usage during concurrent long retry sequences."""
        profiler = memory_profiler
        profiler.start_profiling()

        # Create error recovery managers for concurrent operations
        managers = []
        for i in range(10):  # 10 concurrent managers
            strategy = AdaptiveStrategy(RetryConfig(max_attempts=200, window_size=50))
            reporter = BasicErrorReporter()
            manager = ErrorRecoveryManager(strategy, reporter)
            managers.append(manager)

        profiler.measure("after_managers_creation")

        async def long_retry_operation(manager_id: int, manager: ErrorRecoveryManager):
            """Simulate long retry operation."""
            call_count = 0

            async def failing_operation():
                nonlocal call_count
                call_count += 1

                # Fail most of the time, succeed occasionally
                if call_count % 25 == 0:  # Success every 25th attempt
                    return f"success_after_{call_count}_attempts"

                raise ConnectionError(f"Manager {manager_id} failure #{call_count}")

            context = ErrorContext(
                operation_name=f"long_operation_{manager_id}",
                video_id=f"video_long_{manager_id}",
                operation_context={"manager_id": manager_id},
            )

            try:
                result = await manager.execute_with_retry(
                    failing_operation, context, RetryConfig(max_attempts=100)
                )
                return result
            except Exception:
                return f"failed_after_max_attempts_{manager_id}"

        # Run all operations concurrently
        profiler.measure("before_concurrent_execution")

        tasks = [long_retry_operation(i, manager) for i, manager in enumerate(managers)]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        profiler.measure("after_concurrent_execution")

        # Verify results
        completed_operations = len([r for r in results if isinstance(r, str)])
        assert (
            completed_operations == 10
        ), f"Expected 10 completed operations, got {completed_operations}"

        # Cleanup
        for manager in managers:
            del manager
        gc.collect()

        profiler.measure("final_cleanup")

        # Verify memory usage
        peak_growth = profiler.get_peak_growth()
        final_growth = profiler.get_final_growth()

        print(f"Concurrent long sequences - Peak growth: {peak_growth:.1f} MB")
        print(f"Concurrent long sequences - Final growth: {final_growth:.1f} MB")

        assert peak_growth < 100.0, f"Peak memory growth too high: {peak_growth:.1f} MB"
        assert final_growth < 25.0, f"Memory leak detected: {final_growth:.1f} MB"
