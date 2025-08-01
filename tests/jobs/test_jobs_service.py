"""Tests for the JobsService."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from services.common.base import ServiceSettings
from services.jobs.main import JobsService, JobResponse
from services.common.models import JobType, JobStatus


@pytest.fixture
def mock_service_responses():
    """Mock responses for all service integration calls."""
    return {
        "storage_exists": AsyncMock(status_code=200),
        "storage_save_video": AsyncMock(status_code=200),
        "storage_save_metadata": AsyncMock(status_code=200),
        "storage_work_plan": AsyncMock(status_code=200),
        "download_start": AsyncMock(
            status_code=200, json=AsyncMock(return_value={"task_id": "test-task-123"})
        ),
        "download_progress": AsyncMock(
            status_code=200,
            json=AsyncMock(
                return_value={"status": "completed", "progress_percent": 100.0}
            ),
        ),
        "metadata_fetch": AsyncMock(
            status_code=200,
            json=AsyncMock(
                return_value={"data": {"title": "Test Video", "duration": 123}}
            ),
        ),
    }


@pytest.fixture
def jobs_service():
    """Create a JobsService instance for testing."""
    settings = ServiceSettings(port=8000)
    return JobsService("TestJobsService", settings)


@pytest.mark.service
@pytest.mark.asyncio
async def test_create_job(jobs_service: JobsService):
    """Test creating a new job."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        job_data = {
            "job_type": "VIDEO_DOWNLOAD",
            "urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
            "options": {"quality": "1080p"},
        }

        response = await client.post("/api/v1/jobs", json=job_data)
        assert response.status_code == 200

        result = response.json()
        assert "job_id" in result
        assert result["job_type"] == "VIDEO_DOWNLOAD"
        assert result["status"] == "PENDING"
        assert result["urls"] == job_data["urls"]
        assert result["options"] == job_data["options"]
        assert "created_at" in result
        assert "updated_at" in result


@pytest.mark.service
@pytest.mark.asyncio
async def test_get_job(jobs_service: JobsService):
    """Test retrieving a job by ID."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        # First create a job
        job_data = {
            "job_type": "VIDEO_DOWNLOAD",
            "urls": ["https://www.youtube.com/watch?v=test"],
            "options": {},
        }

        create_response = await client.post("/api/v1/jobs", json=job_data)
        job_id = create_response.json()["job_id"]

        # Then retrieve it
        get_response = await client.get(f"/api/v1/jobs/{job_id}")
        assert get_response.status_code == 200

        result = get_response.json()
        assert result["job_id"] == job_id
        assert result["job_type"] == "VIDEO_DOWNLOAD"
        assert result["urls"] == job_data["urls"]


@pytest.mark.service
@pytest.mark.asyncio
async def test_get_nonexistent_job(jobs_service: JobsService):
    """Test retrieving a job that doesn't exist."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        response = await client.get("/api/v1/jobs/nonexistent-id")
        assert response.status_code == 404


@pytest.mark.service
@pytest.mark.asyncio
async def test_list_jobs(jobs_service: JobsService):
    """Test listing jobs."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        # Create a couple of jobs
        job_data_1 = {
            "job_type": "VIDEO_DOWNLOAD",
            "urls": ["https://www.youtube.com/watch?v=test1"],
            "options": {},
        }
        job_data_2 = {
            "job_type": "PLAYLIST_DOWNLOAD",
            "urls": ["https://www.youtube.com/playlist?list=test"],
            "options": {},
        }

        await client.post("/api/v1/jobs", json=job_data_1)
        await client.post("/api/v1/jobs", json=job_data_2)

        # List all jobs
        response = await client.get("/api/v1/jobs")
        assert response.status_code == 200

        result = response.json()
        assert "jobs" in result
        assert "count" in result
        assert result["count"] >= 2


@pytest.mark.service
@pytest.mark.asyncio
async def test_list_jobs_with_status_filter(jobs_service: JobsService):
    """Test listing jobs with status filtering."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        # Create a job
        job_data = {
            "job_type": "VIDEO_DOWNLOAD",
            "urls": ["https://www.youtube.com/watch?v=filter_test"],
            "options": {},
        }

        await client.post("/api/v1/jobs", json=job_data)

        # List jobs with PENDING status
        response = await client.get("/api/v1/jobs?status_filter=PENDING")
        assert response.status_code == 200

        result = response.json()
        assert result["count"] >= 1
        # All returned jobs should be PENDING
        for job in result["jobs"]:
            assert job["status"] == "PENDING"


@pytest.mark.service
@pytest.mark.asyncio
async def test_job_file_persistence(jobs_service: JobsService):
    """Test that jobs are properly persisted to files."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        job_data = {
            "job_type": "VIDEO_DOWNLOAD",
            "urls": ["https://www.youtube.com/watch?v=persistence_test"],
            "options": {"test": "value"},
        }

        response = await client.post("/api/v1/jobs", json=job_data)
        job_id = response.json()["job_id"]

        # Check that the job file was created
        job_file = Path("logs/jobs") / f"{job_id}.json"
        assert job_file.exists()

        # Verify the file contents
        with open(job_file, "r") as f:
            saved_data = json.load(f)

        assert saved_data["job_id"] == job_id
        assert saved_data["job_type"] == "VIDEO_DOWNLOAD"
        assert saved_data["urls"] == job_data["urls"]
        assert saved_data["options"] == job_data["options"]


@pytest.mark.service
@pytest.mark.asyncio
async def test_register_service(jobs_service: JobsService):
    """Test registering a service in the registry."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        registration_data = {
            "service_name": "test-service",
            "host": "localhost",
            "port": 8001,
            "health_endpoint": "/health",
            "description": "Test service",
            "tags": ["test", "microservice"],
        }

        response = await client.post(
            "/api/v1/registry/register", json=registration_data
        )
        assert response.status_code == 200

        result = response.json()
        assert result["message"] == "Service registered successfully"
        assert "service" in result
        service = result["service"]
        assert service["service_name"] == "test-service"
        assert service["host"] == "localhost"
        assert service["port"] == 8001
        assert service["is_healthy"] is True


@pytest.mark.service
@pytest.mark.asyncio
async def test_list_services(jobs_service: JobsService):
    """Test listing registered services."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        # Register a service first
        registration_data = {
            "service_name": "list-test-service",
            "host": "localhost",
            "port": 8002,
            "description": "Service for list testing",
        }

        await client.post("/api/v1/registry/register", json=registration_data)

        # List services
        response = await client.get("/api/v1/registry/services")
        assert response.status_code == 200

        result = response.json()
        assert "services" in result
        assert "count" in result
        assert result["count"] >= 1

        # Check that our service is in the list
        service_names = [s["service_name"] for s in result["services"]]
        assert "list-test-service" in service_names


@pytest.mark.service
@pytest.mark.asyncio
async def test_unregister_service(jobs_service: JobsService):
    """Test unregistering a service from the registry."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        # Register a service first
        registration_data = {
            "service_name": "unregister-test-service",
            "host": "localhost",
            "port": 8003,
        }

        await client.post("/api/v1/registry/register", json=registration_data)

        # Unregister the service
        response = await client.delete(
            "/api/v1/registry/services/unregister-test-service"
        )
        assert response.status_code == 200

        result = response.json()
        assert "unregistered successfully" in result["message"]

        # Verify the service is no longer in the list
        list_response = await client.get("/api/v1/registry/services")
        service_names = [s["service_name"] for s in list_response.json()["services"]]
        assert "unregister-test-service" not in service_names


@pytest.mark.service
@pytest.mark.asyncio
async def test_unregister_nonexistent_service(jobs_service: JobsService):
    """Test unregistering a service that doesn't exist."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        response = await client.delete("/api/v1/registry/services/nonexistent-service")
        assert response.status_code == 404


@pytest.mark.service
@pytest.mark.asyncio
async def test_service_registry_file_persistence(jobs_service: JobsService):
    """Test that services are properly persisted to files."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        registration_data = {
            "service_name": "persistence-test",
            "host": "localhost",
            "port": 8004,
            "tags": ["persistence", "test"],
        }

        response = await client.post(
            "/api/v1/registry/register", json=registration_data
        )
        service_name = response.json()["service"]["service_name"]

        # Check that the service file was created
        service_file = Path("registry") / f"{service_name}.json"
        assert service_file.exists()

        # Verify the file contents
        with open(service_file, "r") as f:
            saved_data = json.load(f)

        assert saved_data["service_name"] == "persistence-test"
        assert saved_data["host"] == "localhost"
        assert saved_data["port"] == 8004
        assert saved_data["tags"] == ["persistence", "test"]


@pytest.mark.service
@pytest.mark.asyncio
async def test_execute_job(jobs_service: JobsService):
    """Test executing a job."""
    # Mock the service integration methods directly on the JobsService instance
    with patch.object(
        jobs_service, "_get_storage_path", return_value="/tmp/test"
    ), patch.object(
        jobs_service, "_start_download", return_value={"task_id": "test-task-123"}
    ), patch.object(
        jobs_service, "_monitor_download", return_value=None
    ), patch.object(
        jobs_service, "_notify_storage_video_saved", return_value=None
    ):
        async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
            # Create a job first
            job_data = {
                "job_type": "VIDEO_DOWNLOAD",
                "urls": ["https://www.youtube.com/watch?v=execute_test"],
                "options": {},
            }

            create_response = await client.post("/api/v1/jobs", json=job_data)
            job_id = create_response.json()["job_id"]

            # Execute the job
            execute_response = await client.put(f"/api/v1/jobs/{job_id}/execute")
            assert execute_response.status_code == 200

            result = execute_response.json()
            assert result["job_id"] == job_id
            assert (
                result["status"] == "COMPLETED"
            )  # Should be completed after execution
            assert "updated_at" in result


@pytest.mark.service
@pytest.mark.asyncio
async def test_execute_nonexistent_job(jobs_service: JobsService):
    """Test executing a job that doesn't exist."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        response = await client.put("/api/v1/jobs/nonexistent-id/execute")
        assert response.status_code == 404


@pytest.mark.service
@pytest.mark.asyncio
async def test_job_status_updates(jobs_service: JobsService):
    """Test that job status is properly updated during execution."""
    # Mock the service integration methods for METADATA_ONLY job
    with patch.object(
        jobs_service,
        "_fetch_metadata",
        return_value={"title": "Test Video", "duration": 123},
    ), patch.object(jobs_service, "_store_metadata", return_value=None):
        async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
            # Create a job
            job_data = {
                "job_type": "METADATA_ONLY",
                "urls": ["https://www.youtube.com/watch?v=status_test"],
                "options": {},
            }

            create_response = await client.post("/api/v1/jobs", json=job_data)
            job_id = create_response.json()["job_id"]

            # Initial status should be PENDING
            get_response = await client.get(f"/api/v1/jobs/{job_id}")
            assert get_response.json()["status"] == "PENDING"

            # Execute the job
            execute_response = await client.put(f"/api/v1/jobs/{job_id}/execute")
            assert execute_response.status_code == 200

            # Final status should be COMPLETED
            final_response = await client.get(f"/api/v1/jobs/{job_id}")
            assert final_response.json()["status"] == "COMPLETED"


@pytest.mark.service
@pytest.mark.asyncio
async def test_execute_already_completed_job(jobs_service: JobsService):
    """Test executing a job that's already completed."""
    # Mock the service integration methods for VIDEO_DOWNLOAD job
    with patch.object(
        jobs_service, "_get_storage_path", return_value="/tmp/test"
    ), patch.object(
        jobs_service, "_start_download", return_value={"task_id": "test-task-123"}
    ), patch.object(
        jobs_service, "_monitor_download", return_value=None
    ), patch.object(
        jobs_service, "_notify_storage_video_saved", return_value=None
    ):
        async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
            # Create and execute a job
            job_data = {
                "job_type": "VIDEO_DOWNLOAD",
                "urls": ["https://www.youtube.com/watch?v=already_completed"],
                "options": {},
            }

            create_response = await client.post("/api/v1/jobs", json=job_data)
            job_id = create_response.json()["job_id"]

            # Execute the job first time
            first_execute = await client.put(f"/api/v1/jobs/{job_id}/execute")
            assert first_execute.status_code == 200
            assert first_execute.json()["status"] == "COMPLETED"

            # Execute the job again - should return the same result without re-processing
            second_execute = await client.put(f"/api/v1/jobs/{job_id}/execute")
            assert second_execute.status_code == 200
            assert second_execute.json()["status"] == "COMPLETED"


@pytest.mark.service
@pytest.mark.asyncio
async def test_job_failure_adds_to_work_plan(jobs_service: JobsService):
    """Test that failed jobs are automatically added to work plans."""
    from services.common.models import JobStatus

    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        # Create a job
        job_data = {
            "job_type": "VIDEO_DOWNLOAD",
            "urls": ["https://www.youtube.com/watch?v=test123"],
            "options": {"quality": "1080p"},
        }

        create_response = await client.post("/api/v1/jobs", json=job_data)
        assert create_response.status_code == 200
        job_id = create_response.json()["job_id"]

        # Mock httpx.AsyncClient for work plan API call
        from unittest.mock import AsyncMock, Mock, patch

        with patch("httpx.AsyncClient") as mock_client:
            # Use Mock for non-async response properties and methods
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True, "plan_id": "test_plan"}
            mock_response.raise_for_status = Mock()

            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            # Test _update_job_status with failure
            await jobs_service._update_job_status(
                job_id, JobStatus.FAILED, "Test error"
            )

            # Verify the work plan API was called
            mock_client_instance.post.assert_called_once()
            call_args = mock_client_instance.post.call_args
            assert "work-plan" in call_args[0][0]  # URL contains work-plan

            # Verify the payload contains failed download info
            payload = call_args[1]["json"]
            assert "failed_downloads" in payload
            assert len(payload["failed_downloads"]) == 1
            assert payload["failed_downloads"][0]["video_id"] == "test123"
            assert payload["failed_downloads"][0]["errors"] == ["Test error"]


@pytest.mark.service
@pytest.mark.asyncio
async def test_video_id_extraction_from_urls(jobs_service: JobsService):
    """Test video ID extraction from different YouTube URL formats."""
    from services.common.models import JobStatus

    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        # Test various URL formats
        test_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=abc123&t=30s",
            "https://youtu.be/xyz789?t=60",
        ]

        job_data = {
            "job_type": "VIDEO_DOWNLOAD",
            "urls": test_urls,
            "options": {"quality": "1080p"},
        }

        create_response = await client.post("/api/v1/jobs", json=job_data)
        assert create_response.status_code == 200
        job_id = create_response.json()["job_id"]

        # Mock httpx.AsyncClient for work plan API call
        from unittest.mock import AsyncMock, Mock, patch

        with patch("httpx.AsyncClient") as mock_client:
            # Use Mock for non-async response properties and methods
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True, "plan_id": "test_plan"}
            mock_response.raise_for_status = Mock()

            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            # Test _update_job_status with failure
            await jobs_service._update_job_status(
                job_id, JobStatus.FAILED, "Test error"
            )

            # Verify the work plan API was called
            mock_client_instance.post.assert_called_once()
            call_args = mock_client_instance.post.call_args

            # Verify the payload contains all extracted video IDs
            payload = call_args[1]["json"]
            assert "failed_downloads" in payload
            assert len(payload["failed_downloads"]) == 4

            # Check extracted video IDs
            video_ids = [item["video_id"] for item in payload["failed_downloads"]]
            assert "dQw4w9WgXcQ" in video_ids  # From both formats
            assert "abc123" in video_ids
            assert "xyz789" in video_ids


@pytest.mark.service
@pytest.mark.asyncio
async def test_work_plan_integration_error_handling(jobs_service: JobsService):
    """Test error handling when work plan API fails."""
    from services.common.models import JobStatus

    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        # Create a job
        job_data = {
            "job_type": "VIDEO_DOWNLOAD",
            "urls": ["https://www.youtube.com/watch?v=test123"],
            "options": {"quality": "1080p"},
        }

        create_response = await client.post("/api/v1/jobs", json=job_data)
        assert create_response.status_code == 200
        job_id = create_response.json()["job_id"]

        # Mock httpx.AsyncClient to raise an exception
        from unittest.mock import AsyncMock, patch

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(side_effect=Exception("API Error"))
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            # Test _update_job_status with failure - should not raise exception
            result = await jobs_service._update_job_status(
                job_id, JobStatus.FAILED, "Test error"
            )

            # Job should still be updated despite work plan API failure
            assert result is not None
            assert result.status == "FAILED"
            assert result.error_details == "Test error"


# =============================================================================
# COMPREHENSIVE PLAYLIST TESTS
# =============================================================================


@pytest.mark.service
@pytest.mark.asyncio
async def test_extract_playlist_id_standard_url(jobs_service: JobsService):
    """Test playlist ID extraction from standard playlist URLs."""
    # Standard playlist URL
    playlist_url = (
        "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
    )
    playlist_id = jobs_service._extract_playlist_id(playlist_url)
    assert playlist_id == "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"

    # Playlist URL with additional parameters
    playlist_url_with_params = (
        "https://www.youtube.com/playlist?list=PLtest123&index=1&t=10s"
    )
    playlist_id = jobs_service._extract_playlist_id(playlist_url_with_params)
    assert playlist_id == "PLtest123"


@pytest.mark.service
@pytest.mark.asyncio
async def test_extract_playlist_id_mixed_url(jobs_service: JobsService):
    """Test playlist ID extraction from mixed video/playlist URLs."""
    # Mixed URL with video ID and playlist ID
    mixed_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf&index=2"
    playlist_id = jobs_service._extract_playlist_id(mixed_url)
    assert playlist_id == "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"

    # Another mixed URL format
    mixed_url2 = "https://www.youtube.com/watch?v=test123&list=PLtest456&t=30s"
    playlist_id = jobs_service._extract_playlist_id(mixed_url2)
    assert playlist_id == "PLtest456"


@pytest.mark.service
@pytest.mark.asyncio
async def test_extract_playlist_id_invalid_urls(jobs_service: JobsService):
    """Test playlist ID extraction from invalid URLs."""
    # Regular video URL without playlist
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    playlist_id = jobs_service._extract_playlist_id(video_url)
    assert playlist_id is None

    # Invalid URL format
    invalid_url = "https://example.com/not-a-youtube-url"
    playlist_id = jobs_service._extract_playlist_id(invalid_url)
    assert playlist_id is None

    # Empty string
    playlist_id = jobs_service._extract_playlist_id("")
    assert playlist_id is None


@pytest.mark.service
@pytest.mark.asyncio
async def test_fetch_playlist_metadata_success(
    jobs_service: JobsService, mock_service_responses
):
    """Test successful playlist metadata fetching."""
    # Mock successful playlist metadata response
    mock_playlist_data = {
        "playlist_id": "PLtest123",
        "title": "Test Playlist",
        "description": "A test playlist",
        "video_count": 3,
        "videos": [
            {"video_id": "vid1", "title": "Video 1", "duration_seconds": 180},
            {"video_id": "vid2", "title": "Video 2", "duration_seconds": 240},
            {"video_id": "vid3", "title": "Video 3", "duration_seconds": 300},
        ],
    }

    # Configure the mock response properly
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": mock_playlist_data}

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get.return_value = (
            mock_response
        )

        result = await jobs_service._fetch_playlist_metadata("PLtest123")

        assert result["playlist_id"] == "PLtest123"
        assert result["title"] == "Test Playlist"
        assert len(result["videos"]) == 3
        assert result["videos"][0]["video_id"] == "vid1"


@pytest.mark.service
@pytest.mark.asyncio
async def test_fetch_playlist_metadata_service_error(jobs_service: JobsService):
    """Test playlist metadata fetching with service error."""
    with patch("httpx.AsyncClient") as mock_client:
        # Mock service error response
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_response.text.return_value = "Playlist not found"
        mock_client.return_value.__aenter__.return_value.get.return_value = (
            mock_response
        )

        with pytest.raises(Exception) as exc_info:
            await jobs_service._fetch_playlist_metadata("PLnonexistent")

        assert "Playlist metadata service error: 404" in str(exc_info.value)


@pytest.mark.service
@pytest.mark.asyncio
async def test_create_batch_video_jobs_success(jobs_service: JobsService):
    """Test successful batch video job creation."""
    # Mock video data from playlist
    videos = [
        {"video_id": "vid1", "title": "Video 1", "duration_seconds": 180},
        {"video_id": "vid2", "title": "Video 2", "duration_seconds": 240},
        {"video_id": "vid3", "title": "Video 3", "duration_seconds": 300},
    ]

    playlist_options = {"quality": "1080p", "max_concurrent": 2}
    batch_prefix = "playlist-PLtest123"

    # Create temporary jobs directory for testing
    jobs_service.jobs_dir.mkdir(exist_ok=True)

    result = await jobs_service._create_batch_video_jobs(
        videos, playlist_options, batch_prefix
    )

    # Should create 3 video jobs
    assert len(result) == 3

    # Check first job details
    job1 = result[0]
    assert job1["video_id"] == "vid1"
    assert job1["title"] == "Video 1"
    assert job1["duration"] == 180
    assert job1["status"] == "created"
    assert "job_id" in job1
    assert job1["video_url"] == "https://www.youtube.com/watch?v=vid1"

    # Check playlist context in job options
    assert "options" in job1
    assert "playlist_context" in job1["options"]
    playlist_context = job1["options"]["playlist_context"]
    assert playlist_context["batch_prefix"] == batch_prefix
    assert playlist_context["video_index"] == 1
    assert playlist_context["total_videos"] == 3
    assert playlist_context["video_title"] == "Video 1"

    # Check inherited options
    assert job1["options"]["quality"] == "1080p"
    assert job1["options"]["max_concurrent"] == 2


@pytest.mark.service
@pytest.mark.asyncio
async def test_create_batch_video_jobs_missing_video_id(jobs_service: JobsService):
    """Test batch video job creation with missing video IDs."""
    # Include a video without video_id
    videos = [
        {"video_id": "vid1", "title": "Video 1", "duration_seconds": 180},
        {"title": "Video without ID", "duration_seconds": 240},  # Missing video_id
        {"video_id": "vid3", "title": "Video 3", "duration_seconds": 300},
    ]

    jobs_service.jobs_dir.mkdir(exist_ok=True)

    result = await jobs_service._create_batch_video_jobs(videos, {}, "test-batch")

    # Should create 2 valid jobs (skipping the one without video_id)
    valid_jobs = [job for job in result if job.get("job_id")]
    assert len(valid_jobs) == 2
    assert valid_jobs[0]["video_id"] == "vid1"
    assert valid_jobs[1]["video_id"] == "vid3"


@pytest.mark.service
@pytest.mark.asyncio
async def test_execute_playlist_downloads_success(
    jobs_service: JobsService, mock_service_responses
):
    """Test successful concurrent playlist downloads execution."""
    # Create mock video jobs with successful execution results
    mock_completed_job = AsyncMock()
    mock_completed_job.status = "COMPLETED"
    mock_completed_job.error_details = None

    with patch.object(jobs_service, "_execute_job", return_value=mock_completed_job):
        video_jobs = [
            {
                "job_id": "job1",
                "video_id": "vid1",
                "title": "Video 1",
                "duration": 180,
                "status": "created",
            },
            {
                "job_id": "job2",
                "video_id": "vid2",
                "title": "Video 2",
                "duration": 240,
                "status": "created",
            },
            {
                "job_id": "job3",
                "video_id": "vid3",
                "title": "Video 3",
                "duration": 300,
                "status": "created",
            },
        ]

        result = await jobs_service._execute_playlist_downloads(
            video_jobs, max_concurrent=2
        )

        assert result["successful"] == 3
        assert result["failed"] == 0
        assert result["total_jobs"] == 3

        # Check that all jobs are marked as completed
        for job in video_jobs:
            assert job["status"] == "completed"
            assert "result" in job


@pytest.mark.service
@pytest.mark.asyncio
async def test_execute_playlist_downloads_mixed_results(jobs_service: JobsService):
    """Test playlist downloads with mixed success/failure results."""

    # Mock execution results - some successful, some failed
    def mock_execute_job(job_id):
        if job_id == "job2":
            # Simulate failed job
            failed_job = AsyncMock()
            failed_job.status = "FAILED"
            failed_job.error_details = "Download failed"
            return failed_job
        else:
            # Simulate successful job
            success_job = AsyncMock()
            success_job.status = "COMPLETED"
            success_job.error_details = None
            return success_job

    with patch.object(jobs_service, "_execute_job", side_effect=mock_execute_job):
        video_jobs = [
            {
                "job_id": "job1",
                "video_id": "vid1",
                "title": "Video 1",
                "status": "created",
            },
            {
                "job_id": "job2",
                "video_id": "vid2",
                "title": "Video 2",
                "status": "created",
            },
            {
                "job_id": "job3",
                "video_id": "vid3",
                "title": "Video 3",
                "status": "created",
            },
        ]

        result = await jobs_service._execute_playlist_downloads(
            video_jobs, max_concurrent=1
        )

        assert result["successful"] == 2
        assert result["failed"] == 1
        assert result["total_jobs"] == 3

        # Check job statuses
        completed_jobs = [job for job in video_jobs if job["status"] == "completed"]
        failed_jobs = [job for job in video_jobs if job["status"] == "failed"]

        assert len(completed_jobs) == 2
        assert len(failed_jobs) == 1
        assert failed_jobs[0]["job_id"] == "job2"
        assert "error" in failed_jobs[0]


@pytest.mark.service
@pytest.mark.asyncio
async def test_execute_playlist_downloads_failed_creation_jobs(
    jobs_service: JobsService,
):
    """Test playlist downloads with jobs that failed during creation."""
    video_jobs = [
        {"job_id": "job1", "video_id": "vid1", "title": "Video 1", "status": "created"},
        {
            "video_id": "vid2",
            "title": "Video 2",
            "status": "failed_creation",
            "error": "Job creation failed",
        },
        {"job_id": "job3", "video_id": "vid3", "title": "Video 3", "status": "created"},
    ]

    # Mock successful execution for valid jobs
    mock_job = AsyncMock()
    mock_job.status = "COMPLETED"

    with patch.object(jobs_service, "_execute_job", return_value=mock_job):
        result = await jobs_service._execute_playlist_downloads(
            video_jobs, max_concurrent=2
        )

        assert result["successful"] == 2  # job1 and job3
        assert result["failed"] == 1  # job2 (failed creation)
        assert result["total_jobs"] == 3


@pytest.mark.service
@pytest.mark.asyncio
async def test_execute_playlist_downloads_no_executable_jobs(jobs_service: JobsService):
    """Test playlist downloads when no jobs are executable."""
    video_jobs = [
        {
            "video_id": "vid1",
            "title": "Video 1",
            "status": "failed_creation",
            "error": "No video ID",
        },
        {
            "video_id": "vid2",
            "title": "Video 2",
            "status": "failed_creation",
            "error": "Invalid URL",
        },
    ]

    result = await jobs_service._execute_playlist_downloads(
        video_jobs, max_concurrent=2
    )

    assert result["successful"] == 0
    assert result["failed"] == 2
    assert result["total_jobs"] == 2


@pytest.mark.service
@pytest.mark.asyncio
async def test_store_playlist_results_success(
    jobs_service: JobsService, mock_service_responses
):
    """Test successful playlist results storage."""
    job_id = "test-playlist-job-123"
    playlist_results = [
        {
            "playlist_id": "PLtest123",
            "title": "Test Playlist 1",
            "total_videos": 3,
            "successful_downloads": 2,
            "failed_downloads": 1,
            "video_jobs": [],
        },
        {
            "playlist_id": "PLtest456",
            "title": "Test Playlist 2",
            "total_videos": 2,
            "successful_downloads": 2,
            "failed_downloads": 0,
            "video_jobs": [],
        },
    ]

    # Mock Storage service response
    mock_service_responses["storage_save_metadata"].status_code = 200

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = mock_service_responses[
            "storage_save_metadata"
        ]

        await jobs_service._store_playlist_results(job_id, playlist_results)

        # Check that results file was created
        results_dir = Path("logs/playlist_results")
        results_file = results_dir / f"playlist_{job_id}.json"

        assert results_file.exists()

        # Verify file contents
        with open(results_file, "r") as f:
            stored_data = json.load(f)

        assert stored_data["job_id"] == job_id
        assert stored_data["summary"]["total_playlists"] == 2
        assert stored_data["summary"]["successful_playlists"] == 2
        assert stored_data["summary"]["total_videos"] == 5
        assert stored_data["summary"]["total_successful_downloads"] == 4
        assert stored_data["summary"]["total_failed_downloads"] == 1
        assert stored_data["summary"]["overall_success_rate"] == 80.0

        # Cleanup
        results_file.unlink()
        if results_dir.exists():
            import shutil

            shutil.rmtree(results_dir)


@pytest.mark.service
@pytest.mark.asyncio
async def test_store_playlist_results_with_errors(jobs_service: JobsService):
    """Test playlist results storage with playlist processing errors."""
    job_id = "test-error-job-456"
    playlist_results = [
        {
            "playlist_id": "PLtest123",
            "title": "Successful Playlist",
            "total_videos": 2,
            "successful_downloads": 2,
            "failed_downloads": 0,
        },
        {
            "playlist_url": "https://www.youtube.com/playlist?list=PLfailed",
            "error": "Playlist not found",
            "total_videos": 0,
            "successful_downloads": 0,
            "failed_downloads": 0,
        },
    ]

    await jobs_service._store_playlist_results(job_id, playlist_results)

    # Check stored results
    results_file = Path("logs/playlist_results") / f"playlist_{job_id}.json"
    assert results_file.exists()

    with open(results_file, "r") as f:
        stored_data = json.load(f)

    # Should count failed playlists correctly
    assert stored_data["summary"]["successful_playlists"] == 1
    assert stored_data["summary"]["failed_playlists"] == 1
    assert (
        stored_data["summary"]["overall_success_rate"] == 100.0
    )  # 2/2 successful from valid playlist

    # Cleanup
    results_file.unlink()
    import shutil

    if Path("logs/playlist_results").exists():
        shutil.rmtree(Path("logs/playlist_results"))


@pytest.mark.service
@pytest.mark.asyncio
async def test_process_playlist_download_full_workflow(
    jobs_service: JobsService, mock_service_responses
):
    """Test complete playlist download workflow integration."""
    # Create test job
    jobs_service.jobs_dir.mkdir(exist_ok=True)

    # Create JobResponse with proper enum types
    playlist_job = JobResponse(
        job_id="playlist-test-job",
        job_type=JobType.PLAYLIST_DOWNLOAD,
        status=JobStatus.PENDING,
        urls=["https://www.youtube.com/playlist?list=PLtest123"],
        created_at="2025-07-26T12:00:00Z",
        updated_at="2025-07-26T12:00:00Z",
        options={"quality": "720p", "max_concurrent": 2},
    )

    # Mock playlist metadata response
    mock_playlist_metadata = {
        "playlist_id": "PLtest123",
        "title": "Integration Test Playlist",
        "videos": [
            {"video_id": "vid1", "title": "Test Video 1", "duration_seconds": 180},
            {"video_id": "vid2", "title": "Test Video 2", "duration_seconds": 240},
        ],
    }

    # Mock successful job execution
    # Create a proper JobResponse mock
    mock_completed_job = JobResponse(
        job_id="mock-job-id",
        job_type=JobType.VIDEO_DOWNLOAD,
        status=JobStatus.COMPLETED,
        urls=["https://example.com/video"],
        created_at="2025-07-26T12:00:00Z",
        updated_at="2025-07-26T12:00:00Z",
        options={},
    )

    # Configure proper mock responses
    mock_metadata_response = AsyncMock()
    mock_metadata_response.status_code = 200
    mock_metadata_response.json.return_value = {"data": mock_playlist_metadata}

    mock_storage_response = AsyncMock()
    mock_storage_response.status_code = 200

    with patch("httpx.AsyncClient") as mock_client, patch.object(
        jobs_service, "_execute_job", return_value=mock_completed_job
    ):
        mock_client.return_value.__aenter__.return_value.get.return_value = (
            mock_metadata_response
        )
        mock_client.return_value.__aenter__.return_value.post.return_value = (
            mock_storage_response
        )

        # Execute playlist download
        await jobs_service._process_playlist_download(playlist_job)

        # Verify playlist results file was created
        results_file = Path("logs/playlist_results") / "playlist_playlist-test-job.json"
        assert results_file.exists()

        with open(results_file, "r") as f:
            results = json.load(f)

        assert results["summary"]["total_playlists"] == 1
        assert results["summary"]["total_videos"] == 2
        assert results["summary"]["total_successful_downloads"] == 2

        # Cleanup
        results_file.unlink()
        Path("logs/playlist_results").rmdir()
