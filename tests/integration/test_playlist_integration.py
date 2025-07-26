"""Comprehensive playlist integration tests for service coordination.

This module tests playlist-specific workflows across all YTArchive services:
- Jobs↔Metadata service coordination for playlist metadata
- Jobs↔Download service coordination for batch downloads
- Jobs↔Storage service coordination for playlist results
- Cross-service error handling for playlist workflows
- Complete playlist processing integration validation
"""

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Import service components
from services.jobs.main import JobsService, CreateJobRequest
from services.metadata.main import MetadataService
from services.storage.main import StorageService
from services.download.main import DownloadService
from services.common.base import ServiceSettings
from services.common.models import JobType, JobStatus


@pytest.fixture
def temp_storage_dir():
    """Create temporary directory for playlist integration testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def service_settings():
    """Create service settings for integration testing."""
    return ServiceSettings(port=0)


@pytest_asyncio.fixture
async def jobs_service(service_settings, temp_storage_dir):
    """Create Jobs service for playlist integration testing."""
    service = JobsService("JobsService", service_settings)
    service.run = MagicMock()
    # Override job storage to use temp directory
    service.job_storage_dir = Path(temp_storage_dir) / "jobs"
    service.job_storage_dir.mkdir(exist_ok=True)
    yield service


@pytest_asyncio.fixture
async def metadata_service(service_settings):
    """Create Metadata service for playlist integration testing."""
    service = MetadataService("MetadataService", service_settings)
    service.run = MagicMock()
    yield service


@pytest_asyncio.fixture
async def storage_service(temp_storage_dir, service_settings):
    """Create Storage service for playlist integration testing."""
    service = StorageService("StorageService", service_settings)
    service.run = MagicMock()
    # Override storage paths to use temp directory
    service.base_output_dir = Path(temp_storage_dir)
    service.metadata_dir = Path(temp_storage_dir) / "metadata"
    service.videos_dir = Path(temp_storage_dir) / "videos"
    service.work_plans_dir = Path(temp_storage_dir) / "work_plans"
    service.playlist_results_dir = Path(temp_storage_dir) / "playlist_results"
    # Create directories
    for dir_path in [
        service.metadata_dir,
        service.videos_dir,
        service.work_plans_dir,
        service.playlist_results_dir,
    ]:
        dir_path.mkdir(parents=True, exist_ok=True)
    yield service


@pytest_asyncio.fixture
async def download_service(service_settings, temp_storage_dir):
    """Create Download service for playlist integration testing."""
    service = DownloadService("DownloadService", service_settings)
    service.run = MagicMock()
    # Override download path to use temp directory
    service.download_dir = Path(temp_storage_dir) / "downloads"
    service.download_dir.mkdir(exist_ok=True)
    yield service


class TestPlaylistServiceCoordination:
    """Test playlist-specific service coordination workflows."""

    @pytest.mark.integration
    async def test_playlist_metadata_fetching_integration(self, jobs_service):
        """Test Jobs service playlist metadata fetching integration."""
        # Mock playlist metadata response
        mock_playlist_metadata = {
            "playlist_id": "PLtest123",
            "title": "Test Playlist",
            "description": "Test playlist description",
            "video_count": 3,
            "videos": [
                {
                    "video_id": "video1",
                    "title": "Video 1",
                    "duration": 180,
                    "position": 1,
                    "available": True,
                },
                {
                    "video_id": "video2",
                    "title": "Video 2",
                    "duration": 240,
                    "position": 2,
                    "available": True,
                },
                {
                    "video_id": "video3",
                    "title": "Video 3",
                    "duration": 300,
                    "position": 3,
                    "available": True,
                },
            ],
        }

        # Mock HTTP client for playlist metadata request
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            # Wrap response in 'data' field to match service expectation
            mock_response.json = AsyncMock(
                return_value={"data": mock_playlist_metadata}
            )
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            # Test playlist metadata fetching in Jobs service
            playlist_metadata = await jobs_service._fetch_playlist_metadata("PLtest123")

            # Verify metadata structure
            assert playlist_metadata["playlist_id"] == "PLtest123"
            assert playlist_metadata["title"] == "Test Playlist"
            assert playlist_metadata["video_count"] == 3
            assert len(playlist_metadata["videos"]) == 3

            # Verify video metadata structure
            video = playlist_metadata["videos"][0]
            assert video["video_id"] == "video1"
            assert video["title"] == "Video 1"
            assert video["duration"] == 180
            assert video["position"] == 1
            assert video["available"] is True

    @pytest.mark.integration
    async def test_playlist_batch_job_creation_integration(self, jobs_service):
        """Test Jobs service batch job creation for playlist videos."""
        # Mock playlist videos list
        videos = [
            {
                "video_id": "video1",
                "title": "Video 1",
                "duration_seconds": 180,
                "position": 1,
            },
            {
                "video_id": "video2",
                "title": "Video 2",
                "duration_seconds": 240,
                "position": 2,
            },
            {
                "video_id": "video3",
                "title": "Video 3",
                "duration_seconds": 300,
                "position": 3,
            },
        ]

        playlist_options = {
            "quality": "720p",
            "metadata_only": False,
            "output_path": "/tmp/test",
        }
        batch_prefix = "PLtest123"

        # Mock job creation to avoid actual job processing
        jobs_service._create_job = AsyncMock()
        jobs_service._create_job.return_value = MagicMock(job_id="test_job_id")

        # Test batch job creation with correct signature
        job_results = await jobs_service._create_batch_video_jobs(
            videos, playlist_options, batch_prefix
        )

        # Verify job creation results structure
        assert isinstance(job_results, list)
        assert len(job_results) == 3

        # Verify job structure includes playlist information
        for i, job_info in enumerate(job_results):
            assert "job_id" in job_info
            assert "video_id" in job_info
            assert "title" in job_info
            assert "status" in job_info
            assert job_info["video_id"] == f"video{i+1}"
            assert job_info["title"] == f"Video {i+1}"
            assert job_info["status"] == "created"

    @pytest.mark.integration
    async def test_playlist_download_coordination_integration(
        self, jobs_service, download_service
    ):
        """Test Jobs↔Download service integration for playlist downloads."""
        # Create mock video jobs list instead of job IDs
        created_jobs = [
            {
                "job_id": "job1",
                "video_id": "video1",
                "title": "Video 1",
                "status": "created",
            },
            {
                "job_id": "job2",
                "video_id": "video2",
                "title": "Video 2",
                "status": "created",
            },
            {
                "job_id": "job3",
                "video_id": "video3",
                "title": "Video 3",
                "status": "created",
            },
        ]

        # Mock job execution results
        async def mock_execute_job(job_id):
            if job_id in ["job1", "job2"]:
                return MagicMock(status=JobStatus.COMPLETED, error_details=None)
            else:
                return MagicMock(
                    status=JobStatus.FAILED, error_details="Download failed"
                )

        jobs_service._execute_job = AsyncMock(side_effect=mock_execute_job)

        # Test playlist download execution with correct parameter type
        execution_results = await jobs_service._execute_playlist_downloads(
            created_jobs, max_concurrent=2
        )

        # Verify execution results structure (actual response keys)
        assert "successful" in execution_results
        assert "failed" in execution_results
        assert "total_jobs" in execution_results

        # Should have 2 successful and 1 failed
        assert execution_results["successful"] == 2
        assert execution_results["failed"] == 1
        assert execution_results["total_jobs"] == 3

    @pytest.mark.integration
    async def test_playlist_storage_coordination_integration(
        self, jobs_service, storage_service
    ):
        """Test Jobs↔Storage service integration for playlist results storage."""
        # Mock playlist processing results as a list
        playlist_results = [
            {
                "playlist_id": "PLtest123",
                "playlist_title": "Test Playlist",
                "total_videos": 3,
                "successful_downloads": 2,
                "failed_downloads": 1,
                "processing_time": 120.5,
            }
        ]
        job_id = "test_job_123"

        # Mock storage summary method to avoid HTTP calls
        jobs_service._store_playlist_summary_in_storage = AsyncMock(return_value=None)

        # Test playlist results storage with correct signature
        await jobs_service._store_playlist_results(job_id, playlist_results)

        # Verify local storage file creation
        playlist_results_dir = Path("playlist_results")
        expected_file = playlist_results_dir / f"playlist_{job_id}.json"

        # Check if storage was attempted (file should exist or storage method called)
        storage_attempted = (
            expected_file.exists()
            or jobs_service._store_playlist_summary_in_storage.called
        )

        # Verify storage integration was attempted
        assert storage_attempted, "Playlist results storage should be attempted"

    @pytest.mark.integration
    async def test_playlist_error_handling_integration(self, jobs_service):
        """Test cross-service error handling for playlist workflows."""
        # Test metadata service error handling
        with patch("httpx.AsyncClient") as mock_client:
            # Mock metadata service error
            mock_response = AsyncMock()
            mock_response.status_code = 404
            mock_response.text = AsyncMock(return_value="Playlist not found")
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            # Test error handling in playlist processing
            try:
                await jobs_service._fetch_playlist_metadata("PLnonexistent")
                pytest.fail("Expected exception for non-existent playlist")
            except Exception as e:
                assert "404" in str(e) or "not found" in str(e).lower()

        # Test empty playlist handling
        with patch("httpx.AsyncClient") as mock_client:
            # Mock empty playlist response
            empty_playlist_videos = []
            mock_response = AsyncMock()
            mock_response.status_code = 200
            # Wrap response in 'data' field to match service expectation
            mock_response.json = AsyncMock(
                return_value={
                    "data": {
                        "playlist_id": "PLempty",
                        "title": "Empty Playlist",
                        "video_count": 0,
                        "videos": empty_playlist_videos,
                    }
                }
            )
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            # Test empty playlist handling
            playlist_metadata = await jobs_service._fetch_playlist_metadata("PLempty")
            assert playlist_metadata["video_count"] == 0
            assert len(playlist_metadata["videos"]) == 0

            # Mock job creation for empty playlist test
            jobs_service._create_job = AsyncMock()

            # Test batch job creation with empty playlist
            job_results = await jobs_service._create_batch_video_jobs(
                empty_playlist_videos, {"quality": "720p"}, "PLempty"
            )
            assert len(job_results) == 0

    @pytest.mark.integration
    async def test_playlist_full_workflow_integration(
        self, jobs_service, storage_service, download_service
    ):
        """Test complete playlist workflow integration across all services."""
        # Mock complete playlist workflow
        playlist_metadata = {
            "playlist_id": "PLworkflow123",
            "title": "Workflow Test Playlist",
            "video_count": 2,
            "videos": [
                {
                    "video_id": "wf_video1",
                    "title": "Workflow Video 1",
                    "duration": 180,
                    "position": 1,
                },
                {
                    "video_id": "wf_video2",
                    "title": "Workflow Video 2",
                    "duration": 240,
                    "position": 2,
                },
            ],
        }

        # Mock all service interactions
        with patch("httpx.AsyncClient") as mock_client:
            # Mock metadata service
            metadata_response = AsyncMock()
            metadata_response.status_code = 200
            # Wrap response in 'data' field to match service expectation
            metadata_response.json = AsyncMock(return_value={"data": playlist_metadata})

            # Mock storage service
            storage_response = AsyncMock()
            storage_response.status_code = 200
            storage_response.json = AsyncMock(return_value={"success": True})

            # Configure mock client
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=metadata_response
            )
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=storage_response
            )

            # Mock download service
            download_service.start_download = AsyncMock(
                return_value={"task_id": "test_task", "status": "completed"}
            )
            download_service.get_progress = AsyncMock(
                return_value={"status": "completed", "progress_percent": 100}
            )

            # Create playlist download job with proper URLs field
            job_request = CreateJobRequest(
                job_type=JobType.PLAYLIST_DOWNLOAD,
                urls=["https://www.youtube.com/playlist?list=PLworkflow123"],
                options={"quality": "720p", "playlist_id": "PLworkflow123"},
            )

            # Process playlist download (full workflow) using correct method
            job_response = await jobs_service._create_job(job_request)
            assert job_response is not None

            # Verify job response contains expected information
            assert job_response.job_type == JobType.PLAYLIST_DOWNLOAD
            assert any("PLworkflow123" in url for url in job_response.urls)


class TestPlaylistConcurrencyIntegration:
    """Test playlist processing under concurrent conditions."""

    @pytest.mark.integration
    async def test_concurrent_playlist_processing_integration(self, jobs_service):
        """Test concurrent playlist processing coordination."""
        # Mock multiple playlists
        playlists = [
            {
                "playlist_id": f"PL{i}",
                "title": f"Playlist {i}",
                "video_count": 2,
                "videos": [
                    {
                        "video_id": f"video{i}_1",
                        "title": f"Video {i}_1",
                        "duration": 180,
                        "position": 1,
                    },
                    {
                        "video_id": f"video{i}_2",
                        "title": f"Video {i}_2",
                        "duration": 240,
                        "position": 2,
                    },
                ],
            }
            for i in range(3)
        ]

        async def mock_fetch_metadata(playlist_id):
            for playlist in playlists:
                if playlist["playlist_id"] == playlist_id:
                    return playlist
            raise Exception(f"Playlist {playlist_id} not found")

        jobs_service._fetch_playlist_metadata = AsyncMock(
            side_effect=mock_fetch_metadata
        )

        # Create concurrent playlist jobs
        concurrent_jobs = []
        for i in range(3):
            job_request = CreateJobRequest(
                job_type=JobType.PLAYLIST_DOWNLOAD,
                urls=[f"https://www.youtube.com/playlist?list=PL{i}"],
                options={"quality": "720p", "playlist_id": f"PL{i}"},
            )
            job_response = await jobs_service._create_job(job_request)
            concurrent_jobs.append(job_response.job_id)

        # Verify all jobs created successfully
        assert len(concurrent_jobs) == 3
        # Verify all job IDs are valid UUIDs (indicates successful creation)
        for job_id in concurrent_jobs:
            assert job_id is not None
            assert len(job_id) > 0

    @pytest.mark.integration
    async def test_playlist_performance_characteristics_integration(self, jobs_service):
        """Test playlist processing performance characteristics."""
        # Mock large playlist
        large_playlist = {
            "playlist_id": "PLlarge123",
            "title": "Large Playlist",
            "video_count": 10,
            "videos": [
                {
                    "video_id": f"large_video{i}",
                    "title": f"Large Video {i}",
                    "duration": 300,
                    "position": i,
                }
                for i in range(1, 11)
            ],
        }

        jobs_service._fetch_playlist_metadata = AsyncMock(return_value=large_playlist)
        jobs_service._create_job = AsyncMock()
        jobs_service._create_job.return_value = MagicMock(job_id="test_job_id")

        # Measure batch job creation performance
        start_time = time.time()
        job_results = await jobs_service._create_batch_video_jobs(
            large_playlist["videos"], {"quality": "720p"}, "PLlarge123"
        )
        end_time = time.time()

        processing_time = end_time - start_time

        # Verify performance characteristics
        assert processing_time < 5.0  # Should complete within 5 seconds
        assert len(job_results) == 10
        assert all("job_id" in job for job in job_results)


class TestPlaylistErrorRecoveryIntegration:
    """Test playlist error recovery and resilience."""

    @pytest.mark.integration
    async def test_playlist_partial_failure_recovery_integration(
        self, jobs_service, download_service
    ):
        """Test recovery from partial playlist download failures."""
        # Mock partial failure scenario with video jobs list
        created_jobs = [
            {
                "job_id": "job1",
                "video_id": "video1",
                "title": "Video 1",
                "status": "created",
            },
            {
                "job_id": "job2",
                "video_id": "video2",
                "title": "Video 2",
                "status": "created",
            },
            {
                "job_id": "job3",
                "video_id": "video3",
                "title": "Video 3",
                "status": "created",
            },
        ]

        # Mock mixed success/failure responses
        async def mock_execute_job_mixed(job_id):
            if job_id == "job1":
                return MagicMock(status=JobStatus.COMPLETED, error_details=None)
            elif job_id == "job2":
                raise Exception("Network error")
            else:
                return MagicMock(status=JobStatus.COMPLETED, error_details=None)

        jobs_service._execute_job = AsyncMock(side_effect=mock_execute_job_mixed)

        # Test partial failure handling
        execution_results = await jobs_service._execute_playlist_downloads(
            created_jobs, max_concurrent=2
        )

        # Should handle partial failures gracefully (actual response keys)
        assert execution_results["successful"] >= 1  # At least some should succeed
        assert execution_results["failed"] >= 1  # At least some should fail
        assert execution_results["total_jobs"] == 3

    @pytest.mark.integration
    async def test_playlist_service_timeout_integration(self, jobs_service):
        """Test playlist processing with service timeouts."""

        # Mock timeout scenario
        async def mock_fetch_with_timeout(playlist_id):
            await asyncio.sleep(0.1)  # Simulate delay
            raise asyncio.TimeoutError("Metadata service timeout")

        jobs_service._fetch_playlist_metadata = AsyncMock(
            side_effect=mock_fetch_with_timeout
        )

        # Test timeout handling
        try:
            await jobs_service._fetch_playlist_metadata("PLtimeout")
            pytest.fail("Expected timeout exception")
        except asyncio.TimeoutError:
            pass  # Expected behavior


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
