# Integration Test Mocking Standards Guide

---

### 🚨 Pitfall: Local Imports Defeating Mocks

A subtle but critical issue that caused persistent, hard-to-debug failures in the `health` command tests was the use of a **local import** within a function. This practice completely bypasses `unittest.mock.patch` and should be avoided.

#### The Problem

When you patch an object (e.g., `@patch('cli.main.psutil')`), the patch is applied to the module object that has already been imported at the top level. If a function contains its own local `import psutil`, it re-imports the **real, un-patched** module into its local scope. Any subsequent calls use the real module, ignoring your mock entirely.

**The Bad Pattern (That Caused Our Failures):**

```python
# cli/main.py

# ... top-level imports ...

async def _check_system_health(detailed: bool):
    # ...
    if detailed:
        import psutil  # <--- THIS IS THE BUG!
        # This call uses the real psutil, not the mocked one.
        cpu = psutil.cpu_percent()
```

```python
# tests/cli/test_health_command.py

@patch('cli.main.psutil') # This patch is applied to the module-level object
async def test_health_check(mock_psutil):
    mock_psutil.cpu_percent.return_value = 99.9
    # This test will FAIL because the local import in the function
    # bypasses the mock.
    await _check_system_health(detailed=True)
```

#### The Solution: Use Top-Level Imports

The solution is simple and aligns with Python best practices: **always place imports at the top of the file.** This ensures that both the application code and the test code are referring to the exact same module object, allowing the patch to work as expected.

**The Correct Pattern:**

```python
# cli/main.py

import psutil # <--- Correct: Import at the top level
# ... other top-level imports ...

async def _check_system_health(detailed: bool):
    # ...
    if detailed:
        # This call now correctly uses the (potentially patched) module-level object.
        cpu = psutil.cpu_percent()
```

By moving the import to the top of `cli/main.py`, our `psutil` tests were finally able to pass reliably.

This guide establishes standards for mocking in YTArchive integration tests, ensuring consistency, reliability, and maintainability across the test suite.

## Core Principles

1.  **Mock at the Boundary**: Only mock external systems (YouTube API, filesystem) or the direct interface of a service you are not testing. Do not mock internal methods of the service *under test*.
2.  **Be Consistent**: Use standardized helper functions and fixtures for common mocks (e.g., YouTube API responses, service clients).
3.  **Be Realistic**: Mocks should return data that closely resembles the real service's response, including both success and error structures.
4.  **Don't Over-Mock**: Avoid mocking so much that the test becomes a trivial check of the mock itself. The goal is to test the *coordination* between services.

## Standard Mocking Patterns

### 1. Mocking External APIs (e.g., YouTube API)

This is the most critical area for standardization.

**Problem**: Inconsistent, deeply nested `MagicMock` setups for the YouTube API client across different tests.

**Solution**: Use a centralized fixture or helper function to generate standard, reusable YouTube API mock objects.

```python
# In tests/common/mock_utils.py (NEW FILE TO BE CREATED)
from unittest.mock import MagicMock

def create_youtube_api_mock(video_details: dict):
    """Creates a standardized mock for the YouTube Data API client."""
    mock_youtube = MagicMock()
    mock_videos_resource = MagicMock()
    mock_youtube.videos.return_value = mock_videos_resource

    # Default video details
    default_details = {
        "id": "test_video_id",
        "snippet": {
            "title": "Default Test Video",
            "description": "A default description.",
            "publishedAt": "2025-01-01T00:00:00Z",
            "channelId": "UC_test_channel",
            "channelTitle": "Test Channel",
            "thumbnails": {
                "default": {"url": "http://example.com/default.jpg"},
                "medium": {"url": "http://example.com/medium.jpg"},
                "high": {"url": "http://example.com/high.jpg"},
            },
        },
        "contentDetails": {"duration": "PT5M30S"}, # 5 minutes 30 seconds
        "statistics": {"viewCount": "1000", "likeCount": "100"},
    }
    # Merge provided details with defaults
    default_details.update(video_details)

    mock_videos_resource.list.return_value.execute.return_value = {
        "items": [default_details]
    }
    return mock_youtube

# In tests/integration/test_e2e_workflows.py
from tests.common.mock_utils import create_youtube_api_mock

@pytest_asyncio.fixture
async def running_services(temp_storage_dir, service_settings):
    # Use the standardized helper
    mock_youtube_client = create_youtube_api_mock({"id": "e2e_video"})

    with patch("googleapiclient.discovery.build", return_value=mock_youtube_client):
        # ... setup and yield services
        pass
```

### 2. Mocking Service-to-Service Communication

When testing how Service A coordinates with Service B, mock Service B's *client interface* or its specific API endpoints, not its internal logic.

**Pattern**: Use `patch` to replace the HTTP client (`httpx.AsyncClient`) or a specific API call method within the service client.

```python
# Testing how JobsService handles a response from DownloadService

@pytest.mark.asyncio
async def test_job_orchestration_on_download_completion():
    # Mock the response DownloadService would give
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "completed",
        "task_id": "dl-123",
        "details": "Download finished successfully."
    }

    # Patch the HTTP client used by the JobsService to call other services
    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        jobs_service = JobsService(...)
        await jobs_service.start_download_job("video_id")

        # Verify that the jobs service correctly called the download service
        mock_post.assert_called_with(
            "http://localhost:8002/api/v1/download/video", # Download service URL
            json={"video_id": "video_id", ...}
        )
```

### 3. Mocking Filesystem and I/O

**Problem**: Tests writing actual files to disk, leading to stateful and slow tests.

**Solution**: Use the centralized `temp_dir` fixture and patch any direct filesystem calls if necessary.

```python
# In tests/integration/test_storage_retry_integration.py
from tests.common.temp_utils import temp_dir

@pytest_asyncio.fixture
async def storage_service_with_retry(temp_dir, service_settings, retry_config):
    service = StorageService(...)
    # Point the service's base directory to the temporary one
    service.base_output_dir = Path(temp_dir)
    yield service

# If a service uses lower-level I/O, patch it
@pytest.mark.asyncio
async def test_disk_full_scenario(storage_service):
    # Simulate a disk full error
    with patch("os.path.getsize", return_value=LARGE_NUMBER):
        with patch("shutil.disk_usage", return_value=(0, 0, 0)): # No space left
            with pytest.raises(IOError):
                await storage_service.save_video(...)
```

### 4. Mocking Configuration and Environment

**Problem**: Tests relying on local `config.toml` or environment variables.

**Solution**: Use fixtures for settings and `patch.dict` for environment variables.

```python
# Fixture for service settings
@pytest.fixture
def service_settings():
    return ServiceSettings(port=0) # Use random port for isolation

# Mocking environment variables
@pytest.mark.asyncio
async def test_with_api_key():
    with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test_key_from_test"}):
        # This code will see the mocked environment variable
        metadata_service = MetadataService(...)
        assert metadata_service.api_key == "test_key_from_test"
```

## Common Pitfalls and Solutions

### Pitfall 1: Incomplete Mocks
**Symptom**: `AttributeError: 'MagicMock' object has no attribute '...'.`
**Cause**: The mock is not configured deeply enough. For example, `mock.list.return_value` was set, but the code calls `mock.list.return_value.execute()`.
**Solution**: Configure the full chain of calls. The helper function pattern (`create_youtube_api_mock`) helps prevent this.

### Pitfall 2: Mocking the Wrong Thing
**Symptom**: The mock is never called, and the real code runs instead.
**Cause**: The `patch` target is incorrect. For example, patching `services.A.B` when the code under test imports `B` directly with `from B import C`.
**Solution**: Patch where the object is *looked up*, not where it's defined. See the [official `patch` documentation](https://docs.python.org/3/library/unittest.mock.html#where-to-patch).

### Pitfall 3: Brittle Mocks
**Symptom**: Tests break after minor, unrelated refactoring of the implementation.
**Cause**: The test is mocking internal implementation details.
**Solution**: Only mock at the public boundaries of a service or module (its public functions, its client interface). Do not mock private methods (`_internal_method`).

## Full Example: Standardized Integration Test

```python
# In tests/integration/test_standardized_workflow.py
import pytest
from unittest.mock import patch, MagicMock
from tests.common.mock_utils import create_youtube_api_mock

@pytest.mark.integration
class TestStandardizedWorkflow:

    @pytest.fixture
    def mock_api_clients(self):
        """Central fixture for all external and service-to-service mocks."""
        # 1. Mock external YouTube API
        youtube_mock = create_youtube_api_mock({"id": "workflow_video"})

        # 2. Mock responses from other internal services
        storage_response = MagicMock(status_code=200, json=lambda: {"success": True, "path": "/tmp/video.mp4"})
        download_response = MagicMock(status_code=200, json=lambda: {"success": True, "task_id": "dl-abc"})

        # Use a side effect to handle different service calls
        def mock_post_side_effect(url, **kwargs):
            if "storage" in url:
                return storage_response
            if "download" in url:
                return download_response
            return MagicMock(status_code=404)

        mocks = {
            "youtube": youtube_mock,
            "service_post": mock_post_side_effect
        }
        return mocks

    @pytest.mark.asyncio
    async def test_full_orchestration_workflow(self, mock_api_clients, temp_dir):
        # Patch all external boundaries
        with patch("googleapiclient.discovery.build", return_value=mock_api_clients["youtube"]),
             patch("httpx.AsyncClient.post", side_effect=mock_api_clients["service_post"]):

            # Instantiate the service under test (JobsService)
            jobs_service = JobsService(...)

            # Run the integration scenario
            job_id = await jobs_service.start_video_archival("workflow_video")

            # Assertions
            # ... check that the correct calls were made to the mocks
            # ... check the final state of the jobs_service
            pass
```

This guide provides a framework for creating clean, consistent, and maintainable integration tests. Adhering to these standards will reduce test fragility and make the entire test suite easier to understand and extend.
