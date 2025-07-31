# CLI Test Hanging Issues Guide

This guide addresses the common issue of CLI tests hanging indefinitely during execution, particularly those involving monitoring loops and job status checking.

## Problem Overview

### Symptoms
- Tests never complete execution
- Tests appear to "hang" without timeout
- Infinite loop behavior in CLI monitoring functions
- Tests that work individually but hang in test suites

### Root Causes
1. **Infinite monitoring loops** with `while True:` that never exit
2. **Missing exit conditions** in job status mocking
3. **Async context manager** mocking issues
4. **Rich formatting** causing assertion failures that prevent loop exit

## Technical Pattern Analysis

### The Monitoring Loop Pattern
YTArchive CLI commands often use monitoring patterns like:

```python
async def _monitor_playlist_progress(api, job_id):
    """Monitor playlist job progress - THIS CAN HANG!"""
    while True:  # ⚠️ DANGER: Infinite loop without proper exit
        response = await api.get_job(job_id)
        job_data = response["data"]

        # Display progress...
        console.print(progress_info)

        # ✅ CRITICAL: Loop only exits on these specific statuses
        if job_data.get("status") in ["COMPLETED", "FAILED", "CANCELLED"]:
            break

        await asyncio.sleep(3)  # Wait before next check
```

### Why Tests Hang
```python
# ❌ WRONG - This mock will cause infinite loop
mock_api.get_job.return_value = {
    "success": True,
    "data": {"job_id": "test-123", "status": "RUNNING"}  # Never exits!
}

# ✅ RIGHT - This mock allows loop to exit
mock_api.get_job.return_value = {
    "success": True,
    "data": {"job_id": "test-123", "status": "COMPLETED"}  # Loop exits!
}
```

## Solution Patterns

### 1. Proper Job Status Mocking

```python
@pytest.mark.asyncio
async def test_playlist_download_success():
    """Example of proper job status mocking."""
    mock_api = AsyncMock()

    # Set up async context manager (see AsyncMock guide)
    mock_api.__aenter__.return_value = mock_api
    mock_api.__aexit__.return_value = None

    # ✅ CRITICAL: Mock job status to return completion status
    mock_api.get_job.return_value = {
        "success": True,
        "data": {
            "job_id": "test-123",
            "status": "COMPLETED",  # This allows loop to exit
            "progress": 100,
            "message": "Download completed"
        }
    }

    # Mock job creation
    mock_api.create_job.return_value = {
        "success": True,
        "data": {"job_id": "test-123", "status": "PENDING"}
    }

    with patch('cli.main.YTArchiveAPI', return_value=mock_api):
        # Test will complete instead of hanging
        await _download_playlist("test-playlist-id", "720p", Path("/tmp"))
```

### 2. Progressive Status Mocking

For more realistic testing, mock status progression:

```python
@pytest.mark.asyncio
async def test_playlist_download_with_progress():
    """Test with realistic status progression."""
    mock_api = AsyncMock()
    mock_api.__aenter__.return_value = mock_api
    mock_api.__aexit__.return_value = None

    # Mock progressive status updates
    status_responses = [
        {"success": True, "data": {"job_id": "test-123", "status": "PENDING"}},
        {"success": True, "data": {"job_id": "test-123", "status": "RUNNING", "progress": 25}},
        {"success": True, "data": {"job_id": "test-123", "status": "RUNNING", "progress": 50}},
        {"success": True, "data": {"job_id": "test-123", "status": "RUNNING", "progress": 75}},
        {"success": True, "data": {"job_id": "test-123", "status": "COMPLETED", "progress": 100}}
    ]

    mock_api.get_job.side_effect = status_responses

    # Test will progress through statuses and complete
    # ... rest of test
```

### 3. Handling Rich Formatting

CLI output often includes Rich formatting that can cause test assertion issues:

```python
@pytest.mark.asyncio
async def test_playlist_download_output():
    """Handle Rich formatting in CLI output."""
    mock_api = AsyncMock()
    mock_api.__aenter__.return_value = mock_api
    mock_api.__aexit__.return_value = None

    mock_api.get_job.return_value = {
        "success": True,
        "data": {"job_id": "test-123", "status": "COMPLETED"}
    }

    with patch('cli.main.YTArchiveAPI', return_value=mock_api):
        with patch('cli.main.console.print') as mock_print:
            await _download_playlist("test-playlist-id", "720p", Path("/tmp"))

            # ✅ Flexible assertion for Rich formatting
            mock_print.assert_called()

            # Check for specific content in any print call
            print_calls = [call.args[0] for call in mock_print.call_args_list]
            assert any("completed" in str(call).lower() for call in print_calls)
```

### 4. Error Handling in Monitoring Loops

```python
@pytest.mark.asyncio
async def test_playlist_download_with_failure():
    """Test error handling that exits monitoring loop."""
    mock_api = AsyncMock()
    mock_api.__aenter__.return_value = mock_api
    mock_api.__aexit__.return_value = None

    # Mock failure response that exits loop
    mock_api.get_job.return_value = {
        "success": True,
        "data": {
            "job_id": "test-123",
            "status": "FAILED",  # This exits the loop
            "error": "Download failed"
        }
    }

    with patch('cli.main.YTArchiveAPI', return_value=mock_api):
        with patch('cli.main.console.print') as mock_print:
            await _download_playlist("test-playlist-id", "720p", Path("/tmp"))

            # Verify error handling
            print_calls = [str(call.args[0]) for call in mock_print.call_args_list]
            assert any("failed" in call.lower() for call in print_calls)
```

## Common Pitfalls and Solutions

### Pitfall 1: Missing Execute Job Mock
```python
# ❌ WRONG - Missing execute_job mock can cause hanging
mock_api.get_job.return_value = {...}

# ✅ RIGHT - Include all necessary mocks
mock_api.execute_job.return_value = {"success": True}
mock_api.get_job.return_value = {...}
```

### Pitfall 2: Inconsistent Status Values
```python
# ❌ WRONG - Status doesn't match expected values
"data": {"status": "FINISHED"}  # CLI expects "COMPLETED"

# ✅ RIGHT - Use exact status values CLI expects
"data": {"status": "COMPLETED"}  # Matches CLI exit condition
```

### Pitfall 3: Missing Watch Mode Handling
```python
# ❌ WRONG - Not handling watch parameter
async def _monitor_job(job_id, watch=False):
    while True:  # Always loops regardless of watch
        # ...

# ✅ RIGHT - Handle watch parameter
async def _monitor_job(job_id, watch=False):
    while True:
        # ...
        if not watch or status in ["COMPLETED", "FAILED"]:
            break
```

## Testing Strategy

### 1. Unit Test Individual Components
```python
@pytest.mark.asyncio
async def test_job_status_checking():
    """Test job status checking logic separately."""
    mock_api = AsyncMock()
    mock_api.get_job.return_value = {
        "success": True,
        "data": {"job_id": "test-123", "status": "COMPLETED"}
    }

    # Test just the status checking logic
    result = await _get_job_status_once(mock_api, "test-123")
    assert result["status"] == "COMPLETED"
```

### 2. Integration Test with Timeouts
```python
@pytest.mark.asyncio
async def test_playlist_download_with_timeout():
    """Use timeout as safety net for hanging tests."""
    mock_api = AsyncMock()
    mock_api.__aenter__.return_value = mock_api
    mock_api.__aexit__.return_value = None

    mock_api.get_job.return_value = {
        "success": True,
        "data": {"job_id": "test-123", "status": "COMPLETED"}
    }

    # Use asyncio.wait_for as safety net
    with patch('cli.main.YTArchiveAPI', return_value=mock_api):
        try:
            await asyncio.wait_for(
                _download_playlist("test-playlist-id", "720p", Path("/tmp")),
                timeout=10.0  # 10 second timeout
            )
        except asyncio.TimeoutError:
            pytest.fail("Test hung - monitoring loop didn't exit properly")
```

## Debugging Hanging Tests

### 1. Add Debug Logging
```python
import logging

async def _monitor_playlist_progress(api, job_id):
    while True:
        response = await api.get_job(job_id)
        job_data = response["data"]

        # Add debug logging
        logging.debug(f"Job status: {job_data.get('status')}")

        if job_data.get("status") in ["COMPLETED", "FAILED", "CANCELLED"]:
            logging.debug("Exiting monitoring loop")
            break
```

### 2. Use Print Statements
```python
# Temporary debugging in tests
mock_api.get_job.return_value = {
    "success": True,
    "data": {"job_id": "test-123", "status": "COMPLETED"}
}

print(f"Mock return value: {mock_api.get_job.return_value}")  # Debug
```

### 3. Verify Mock Call Counts
```python
# After test (if it completes)
print(f"get_job called {mock_api.get_job.call_count} times")
assert mock_api.get_job.call_count >= 1
```

## Best Practices Summary

1. **Always Mock Exit Conditions**: Ensure job status mocks return "COMPLETED", "FAILED", or "CANCELLED"
2. **Set Up Async Context Managers**: Use proper `__aenter__` and `__aexit__` setup
3. **Include All Required Mocks**: Don't forget `execute_job`, `create_job`, etc.
4. **Handle Rich Formatting**: Use flexible assertions for formatted output
5. **Use Timeouts as Safety Nets**: Add timeout protection for integration tests
6. **Test Status Progression**: Mock realistic status transitions
7. **Debug with Logging**: Add temporary logging to understand loop behavior

## Quick Fix Checklist

When encountering hanging CLI tests:

- [ ] Mock job status returns completion status ("COMPLETED", "FAILED", "CANCELLED")
- [ ] Set up async context manager (`__aenter__`, `__aexit__`)
- [ ] Include all required API method mocks
- [ ] Check for `while True:` loops in CLI functions
- [ ] Verify exit conditions match expected status values
- [ ] Add timeout protection for safety
- [ ] Use flexible assertions for Rich formatting

---

This guide should resolve most CLI test hanging issues. For the AsyncMock context manager setup, also refer to `docs/testing-asyncmock-guide.md`.
