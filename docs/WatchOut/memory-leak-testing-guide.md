# Memory Leak Testing Guidelines

This guide provides standards and best practices for writing and interpreting memory leak tests in the YTArchive project. Our goal is to ensure that long-running services and complex operations do not lead to unbounded memory growth, which is critical for production stability.

## 1. The Memory Testing Framework

Our memory testing framework is built around a few key components located in `tests/memory/memory_leak_detection.py`:

*   **`MemorySnapshot`**: A data class that captures a detailed snapshot of the process's memory state at a specific moment. It includes:
    *   Resident Set Size (RSS) and Virtual Memory Size (VMS).
    *   CPU percentage.
    *   Number of open file handles.
    *   A list of the top memory-allocating lines of code (via `tracemalloc`).
    *   A dictionary counting all Python objects by type (via `gc`).
*   **`MemoryLeakReport`**: A data class that analyzes the difference between a start and end `MemorySnapshot` to detect potential leaks. It checks for:
    *   Excessive RSS memory growth against predefined thresholds.
    *   Growth in open file handles.
    *   Significant growth in the number of specific Python objects.
*   **`MemoryProfiler`**: A simple utility class used within tests to capture memory usage at key points.
*   **`@memory_leak_test` decorator**: A (to be implemented) decorator to standardize the setup and teardown of memory tests.

## 2. How to Write a Memory Test

Memory tests are crucial for operations that are expected to run for a long time or handle large amounts of data. This includes retry sequences, large playlist processing, and concurrent downloads.

### Step 1: Place the Test in the Correct Location

All memory tests must be placed in the `tests/memory/` directory. This keeps them separate from functional tests, as they are often slower and more resource-intensive.

### Step 2: Use the `MemoryProfiler`

The `MemoryProfiler` is the primary tool for writing a memory test. It handles garbage collection and captures memory usage consistently.

```python
# From tests/memory/test_retry_memory_leaks.py
import pytest
from .memory_leak_detection import MemoryProfiler

@pytest.mark.memory
@pytest.mark.slow
@pytest.mark.asyncio
async def test_long_running_retry_sequence_memory():
    # 1. Initialize the profiler
    profiler = MemoryProfiler()

    # 2. Start profiling to get a baseline
    initial_memory = profiler.start_profiling()
    print(f"Initial memory: {initial_memory:.1f} MB")

    # 3. Setup the long-running operation
    # (e.g., an ErrorRecoveryManager with an AdaptiveStrategy)
    strategy = AdaptiveStrategy(config=RetryConfig(max_attempts=1000))
    manager = ErrorRecoveryManager(strategy, ...)

    # 4. Run the operation that you suspect might leak memory
    for i in range(1000):
        try:
            await manager.execute_with_retry(failing_operation, ...)
        except Exception:
            pass # We expect failures in this test

        # Optionally, take intermediate measurements
        if i % 200 == 0:
            profiler.measure(f"After {i+1} iterations")

    # 5. Take the final measurement
    final_memory = profiler.measure("Final")

    # 6. Assert against memory growth thresholds
    growth = final_memory - initial_memory
    peak_memory = max(profiler.measurements)

    # Check that the final memory usage is close to the initial usage
    assert growth < 5.0, f"Memory grew by {growth:.1f} MB, which is too high."

    # Check that the peak memory usage did not exceed a reasonable limit
    assert peak_memory < 50.0, f"Peak memory reached {peak_memory:.1f} MB."
```

## 3. Interpreting Memory Test Results

### Understanding Thresholds

Our `MemoryLeakReport` class uses a set of predefined thresholds. However, for test assertions, we often use more context-specific values.

*   **Final Growth Threshold**: This is the most important metric. After an operation is complete and all objects should have been garbage collected, the final memory usage should be very close to the initial usage. A small growth is acceptable (e.g., **< 5-10 MB**), as some objects might be cached globally.
*   **Peak Memory Threshold**: During an operation, it's normal for memory usage to spike. This threshold ensures that the spike is not excessive. For example, a long retry sequence should not cause memory to grow to hundreds of megabytes. A reasonable peak might be **< 50-100 MB**, depending on the operation.

### Common Causes of Memory Leaks

1.  **Circular References**: The most common cause. Object A holds a reference to B, and B holds a reference to A. If nothing external holds a reference to A or B, they should be garbage collected, but historically Python's GC has had issues with this. Modern Python is better, but it's still a potential problem.
2.  **Global Collections**: Appending objects to a global list, dictionary, or other collection that never gets cleared. Our `ErrorRecoveryManager`'s `active_recoveries` dictionary was a potential source of this, but was fixed to clean up after itself.
3.  **Unclosed Resources**: File handles, network connections, or other system resources that are not properly closed. The `open_files` metric in `MemorySnapshot` helps detect this.
4.  **Logging Accumulation**: Storing large numbers of log records in memory.

## 4. Best Practices for Writing Leak-Free Code

1.  **Use Context Managers**: For files and network connections, always use `with` (or `async with`) statements to ensure resources are automatically closed.

    ```python
    # ✅ CORRECT
    async with httpx.AsyncClient() as client:
        response = await client.get(...)

    with open("file.txt", "r") as f:
        content = f.read()
    ```

2.  **Manage Object Lifecycles**: Ensure that objects created during an operation are eligible for garbage collection after the operation is complete. Avoid storing them in long-lived collections unless absolutely necessary.

3.  **Use Weak References**: If you need to cache objects but don't want to prevent them from being garbage collected, use `weakref.WeakValueDictionary` or `weakref.ref`.

4.  **Cleanup in `finally` blocks**: For resources that don't support context managers, use a `try...finally` block to guarantee cleanup.

    ```python
    resource = acquire_resource()
    try:
        # use resource
    finally:
        release_resource(resource)
    ```

By following these guidelines, we can proactively write code that is less prone to memory leaks and use our testing framework to catch any regressions early.
