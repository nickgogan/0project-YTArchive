# AsyncMock Testing Guide

This guide covers best practices for using `AsyncMock` in YTArchive tests, particularly for async context managers and API clients.

## Table of Contents

- [Common AsyncMock Patterns](#common-asyncmock-patterns)
- [Async Context Manager Pattern](#async-context-manager-pattern)
- [API Client Mocking](#api-client-mocking)
- [Troubleshooting](#troubleshooting)
- [Examples](#examples)

## Common AsyncMock Patterns

### Basic AsyncMock Setup

```python
from unittest.mock import AsyncMock, MagicMock
import pytest

@pytest.fixture
def mock_api_client():
    """Basic AsyncMock setup for API client."""
    client = AsyncMock()
    client.get.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"status": "success"})
    )
    return client
```

### Async Method Mocking

```python
@pytest.mark.asyncio
async def test_async_method():
    mock_service = AsyncMock()
    mock_service.fetch_data.return_value = {"data": "test"}

    result = await mock_service.fetch_data()
    assert result == {"data": "test"}
```

## Async Context Manager Pattern

### The Problem

When testing code that uses `async with`, you may encounter errors like:
```
<AsyncMock name='mock.__aenter__().client.get().status_code' id='...'>
```

This happens because AsyncMock doesn't automatically set up the `__aenter__` and `__aexit__` methods properly.

### The Solution

Always set up the async context manager methods explicitly:

```python
@pytest.fixture
def mock_ytarchive_api():
    """Properly configured AsyncMock for YTArchiveAPI context manager."""
    api_mock = AsyncMock()

    # ✅ CRITICAL: Set up async context manager methods
    api_mock.__aenter__.return_value = api_mock
    api_mock.__aexit__.return_value = None

    # Set up the client mock
    api_mock.client = AsyncMock()
    return api_mock
```

### Example: YTArchive Health Check Test

```python
@pytest.mark.asyncio
async def test_health_check_with_service_failure(mock_ytarchive_api):
    """Test health check when one service fails."""
    # ✅ Set up async context manager properly
    mock_ytarchive_api.__aenter__.return_value = mock_ytarchive_api
    mock_ytarchive_api.__aexit__.return_value = None

    # Set up side effect for different services
    def mock_get_side_effect(url, **kwargs):
        if "8002" in url:  # metadata service
            raise ConnectionError("Connection refused")
        return MagicMock(
            status_code=200,
            elapsed=MagicMock(total_seconds=MagicMock(return_value=0.05)),
            json=MagicMock(return_value={"status": "healthy"})
        )

    mock_ytarchive_api.client.get.side_effect = mock_get_side_effect

    with patch('cli.main.YTArchiveAPI', return_value=mock_ytarchive_api):
        # Your test code here
        await _check_system_health(json_output=True, detailed=False)
```

## API Client Mocking

### HTTP Response Mocking

```python
def create_mock_response(status_code=200, json_data=None, elapsed_seconds=0.05):
    """Helper to create consistent mock HTTP responses."""
    response = MagicMock()
    response.status_code = status_code
    response.elapsed = MagicMock(total_seconds=MagicMock(return_value=elapsed_seconds))
    response.json = MagicMock(return_value=json_data or {"status": "success"})
    return response

@pytest.mark.asyncio
async def test_api_call():
    mock_api = AsyncMock()
    mock_api.__aenter__.return_value = mock_api
    mock_api.__aexit__.return_value = None

    # Use helper for consistent responses
    mock_api.client.get.return_value = create_mock_response(
        status_code=200,
        json_data={"data": "test"}
    )
```

### Multiple Service Endpoints

```python
@pytest.mark.asyncio
async def test_multiple_services():
    """Test calling multiple service endpoints."""
    mock_api = AsyncMock()
    mock_api.__aenter__.return_value = mock_api
    mock_api.__aexit__.return_value = None

    # Different responses for different URLs
    def mock_get_side_effect(url, **kwargs):
        if "jobs" in url:
            return create_mock_response(json_data={"service": "jobs", "status": "healthy"})
        elif "metadata" in url:
            return create_mock_response(json_data={"service": "metadata", "status": "healthy"})
        elif "storage" in url:
            return create_mock_response(json_data={"service": "storage", "status": "healthy"})
        else:
            return create_mock_response(status_code=404)

    mock_api.client.get.side_effect = mock_get_side_effect
```

## Troubleshooting

### Common Issues and Solutions

#### Issue: AsyncMock Objects in Output
```
Error: Expected string, got <AsyncMock name='mock.client.get().status_code' id='...'>
```

**Solution:** Always set up `__aenter__` and `__aexit__`:
```python
mock_api.__aenter__.return_value = mock_api
mock_api.__aexit__.return_value = None
```

#### Issue: Methods Not Called
```
AssertionError: Expected call not found
```

**Solution:** Ensure you're asserting on the right mock object:
```python
# ❌ Wrong - this might be the context manager mock
mock_api.client.get.assert_called_once()

# ✅ Right - this is the actual client after __aenter__
api_instance = await mock_api.__aenter__()
api_instance.client.get.assert_called_once()
```

#### Issue: Async Generator Mocking
```python
# For async generators/iterators
mock_async_gen = AsyncMock()
mock_async_gen.__aiter__.return_value = mock_async_gen
mock_async_gen.__anext__.side_effect = [item1, item2, StopAsyncIteration]
```

### Best Practices

1. **Always Set Up Context Managers**: For any `async with` usage, set up `__aenter__` and `__aexit__`
2. **Use Helpers**: Create helper functions like `create_mock_response()` for consistency
3. **Test Async Context**: Test both successful and error cases in async contexts
4. **Mock Side Effects**: Use `side_effect` for different behaviors based on parameters
5. **Verify Calls**: Assert on the correct mock objects after context manager setup

### YTArchive-Specific Patterns

```python
def setup_async_api_mock(mock_api):
    """Standard setup for YTArchiveAPI async context manager.

    Use this helper in all CLI tests that use YTArchiveAPI.
    """
    mock_api.__aenter__.return_value = mock_api
    mock_api.__aexit__.return_value = None
    return mock_api

# Usage in tests:
@pytest.fixture
def mock_ytarchive_api():
    api_mock = AsyncMock()
    api_mock.client = AsyncMock()
    return setup_async_api_mock(api_mock)
```

## Examples

### Complete CLI Test Example

```python
@pytest.mark.asyncio
async def test_download_command_with_api():
    """Complete example of CLI command testing with AsyncMock."""
    mock_api = AsyncMock()

    # ✅ Essential: Set up async context manager
    mock_api.__aenter__.return_value = mock_api
    mock_api.__aexit__.return_value = None

    # Mock API responses
    mock_api.create_job.return_value = {
        "success": True,
        "data": {"job_id": "test-123", "status": "PENDING"}
    }

    mock_api.get_job.return_value = {
        "success": True,
        "data": {"job_id": "test-123", "status": "COMPLETED"}
    }

    # Test the command
    with patch('cli.main.YTArchiveAPI', return_value=mock_api):
        with patch('cli.main.console.print') as mock_print:
            await _download_video("test-video-id", "720p", Path("/tmp"))

            # Verify API calls
            mock_api.create_job.assert_called_once()
            mock_api.get_job.assert_called_once()

            # Verify output
            mock_print.assert_called()
```

### Integration Test Example

```python
@pytest.mark.asyncio
async def test_service_integration():
    """Example of testing service integration with proper AsyncMock setup."""
    # Set up multiple service mocks
    jobs_mock = AsyncMock()
    jobs_mock.__aenter__.return_value = jobs_mock
    jobs_mock.__aexit__.return_value = None

    storage_mock = AsyncMock()
    storage_mock.__aenter__.return_value = storage_mock
    storage_mock.__aexit__.return_value = None

    # Configure responses
    jobs_mock.execute_job.return_value = {"success": True}
    storage_mock.save_video.return_value = {"success": True, "path": "/tmp/video.mp4"}

    # Run integration test
    with patch('services.jobs.JobsAPI', return_value=jobs_mock):
        with patch('services.storage.StorageAPI', return_value=storage_mock):
            # Your integration test code here
            pass
```

---

This guide should resolve most AsyncMock issues in YTArchive tests. For additional help, check the test files in `tests/cli/` for working examples.
