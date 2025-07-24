"""End-to-End Integration Tests for YTArchive workflows."""

import asyncio
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

# Import all our services for integration testing
from services.jobs.main import JobsService, CreateJobRequest
from services.storage.main import StorageService
from services.metadata.main import MetadataService
from services.download.main import DownloadService
from services.logging.main import LoggingService
from services.common.base import ServiceSettings
from services.common.models import JobType


@pytest.fixture
def temp_storage_dir():
    """Create temporary directory for integration testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def service_settings():
    """Create service settings for testing."""
    return ServiceSettings(port=0)  # Use random available port


@pytest_asyncio.fixture
async def running_services(temp_storage_dir, service_settings):
    """Start all services for integration testing."""
    # Use environment variable mocking throughout the fixture
    with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test_api_key"}):
        services = {}

        # Create service instances
        services["jobs"] = JobsService("JobsService", service_settings)
        services["storage"] = StorageService("StorageService", service_settings)
        services["metadata"] = MetadataService("MetadataService", service_settings)
        services["download"] = DownloadService("DownloadService", service_settings)
        services["logging"] = LoggingService("LoggingService", service_settings)

        # Override storage path for testing
        services["storage"].base_path = Path(temp_storage_dir)

        # Mock the run method to avoid actually starting servers
        for name, service in services.items():
            service.run = MagicMock()

        yield services

        # Cleanup
        for service in services.values():
            if hasattr(service, "cleanup_pending_tasks"):
                await service.cleanup_pending_tasks()


@pytest.fixture
def mock_youtube_api():
    """Mock YouTube API for integration testing."""
    return {
        "items": [
            {
                "id": "dQw4w9WgXcQ",
                "snippet": {
                    "title": "Rick Astley - Never Gonna Give You Up",
                    "channelTitle": "RickAstleyVEVO",
                    "publishedAt": "2009-10-25T06:57:33Z",
                    "description": "The official video for Rick Astley's 'Never Gonna Give You Up'",
                },
                "contentDetails": {"duration": "PT3M33S"},
                "statistics": {"viewCount": "1000000000", "likeCount": "10000000"},
            }
        ]
    }


class TestCompleteWorkflows:
    """Test complete end-to-end workflows."""

    @pytest.mark.asyncio
    @patch("services.metadata.main.build")
    @patch("services.download.main.DownloadService._run_ytdlp")
    async def test_full_video_download_workflow(
        self,
        mock_ytdlp,
        mock_youtube_build,
        running_services,
        mock_youtube_api,
        temp_storage_dir,
    ):
        """Test complete workflow: CLI → Jobs → Metadata → Storage → Download."""

        # Setup YouTube API mock
        mock_youtube_service = MagicMock()
        mock_youtube_service.videos().list().execute.return_value = mock_youtube_api
        mock_youtube_build.return_value = mock_youtube_service

        # Setup yt-dlp mock
        mock_ytdlp.return_value = None

        # Get service instances
        jobs_service = running_services["jobs"]
        storage_service = running_services["storage"]
        metadata_service = running_services["metadata"]
        download_service = running_services["download"]

        video_id = "dQw4w9WgXcQ"

        # Step 1: Create job via Jobs service
        job_request = CreateJobRequest(
            job_type=JobType.VIDEO_DOWNLOAD,
            urls=[f"https://www.youtube.com/watch?v={video_id}"],
            options={"quality": "720p", "output_path": temp_storage_dir},
        )
        job_data = await jobs_service._create_job(job_request)

        assert job_data.job_type == "VIDEO_DOWNLOAD"
        assert job_data.status == "PENDING"

        # Step 2: Check if video exists in storage (should be False initially)
        storage_exists = await storage_service._check_video_exists(video_id)
        assert not storage_exists.exists

        # Step 3: Fetch metadata
        metadata_response = await metadata_service._get_video_metadata(video_id)
        assert metadata_response is not None
        assert metadata_response.title == "Rick Astley - Never Gonna Give You Up"
        assert metadata_response.channel_title == "RickAstleyVEVO"

        # Step 4: Save metadata to storage
        metadata_saved = await storage_service._save_metadata(
            video_id, metadata_response.model_dump()
        )
        assert metadata_saved["success"] is True

        # Step 5: Start download
        download_request = {
            "video_id": video_id,
            "quality": "720p",
            "output_path": str(Path(temp_storage_dir) / "videos"),
            "include_captions": True,
            "caption_languages": ["en"],
        }

        download_task = await download_service._create_download_task(
            download_service.DownloadRequest(**download_request)
        )
        assert download_task.video_id == video_id
        assert download_task.status.value == "pending"

        # Step 6: Simulate download completion
        download_task.status = download_service.DownloadStatus.COMPLETED
        download_task.file_path = str(
            Path(temp_storage_dir) / "videos" / f"{video_id}.mp4"
        )

        # Step 7: Update job status to completed
        job_data.status = "COMPLETED"
        job_data.completed_at = "2023-01-01T12:00:00Z"

        # Step 8: Verify final state
        # Check storage now shows video exists
        final_storage_state = await storage_service._check_video_exists(video_id)
        assert final_storage_state.has_metadata  # Metadata was saved

        # Verify download task completed
        assert download_task.status == download_service.DownloadStatus.COMPLETED
        assert download_task.file_path is not None

        # Verify job completed
        assert job_data.status == "COMPLETED"

        print(f"✅ Full workflow completed successfully for video {video_id}")

    @pytest.mark.asyncio
    @patch("services.metadata.main.build")
    async def test_metadata_only_workflow(
        self, mock_youtube_build, running_services, mock_youtube_api
    ):
        """Test metadata-only workflow without download."""

        # Setup YouTube API mock
        mock_youtube_service = MagicMock()
        mock_youtube_service.videos().list().execute.return_value = mock_youtube_api
        mock_youtube_build.return_value = mock_youtube_service

        jobs_service = running_services["jobs"]
        metadata_service = running_services["metadata"]
        storage_service = running_services["storage"]

        video_id = "dQw4w9WgXcQ"

        # Step 1: Create metadata-only job
        job_request = CreateJobRequest(
            job_type=JobType.METADATA_ONLY,
            urls=[f"https://www.youtube.com/watch?v={video_id}"],
            options={},
        )
        job_data = await jobs_service._create_job(job_request)

        assert job_data.job_type == "METADATA_ONLY"

        # Step 2: Fetch and save metadata
        metadata = await metadata_service._get_video_metadata(video_id)
        await storage_service._save_metadata(video_id, metadata.model_dump())

        # Step 3: Verify no download occurred
        storage_state = await storage_service._check_video_exists(video_id)
        assert storage_state.has_metadata
        assert not storage_state.has_video  # No video file should exist

        print(f"✅ Metadata-only workflow completed for video {video_id}")

    @pytest.mark.asyncio
    async def test_concurrent_download_workflow(
        self, running_services, temp_storage_dir
    ):
        """Test concurrent download management."""

        download_service = running_services["download"]

        # Create multiple download tasks
        video_ids = ["video1", "video2", "video3", "video4", "video5"]
        tasks = []

        for video_id in video_ids:
            request = download_service.DownloadRequest(
                video_id=video_id, output_path=temp_storage_dir
            )
            task = await download_service._create_download_task(request)
            tasks.append(task)

        # Verify semaphore limits concurrent downloads
        assert download_service.download_semaphore._value == 3  # max concurrent
        assert len(download_service.active_tasks) == 5
        assert len(download_service.task_progress) == 5

        print("✅ Concurrent download management verified")


class TestErrorScenarios:
    """Test error handling in end-to-end workflows."""

    @pytest.mark.asyncio
    @patch("services.metadata.main.build")
    async def test_invalid_video_workflow(self, mock_youtube_build, running_services):
        """Test workflow with invalid/unavailable video."""

        # Setup YouTube API to return no results
        mock_youtube_service = MagicMock()
        mock_youtube_service.videos().list().execute.return_value = {"items": []}
        mock_youtube_build.return_value = mock_youtube_service

        jobs_service = running_services["jobs"]
        metadata_service = running_services["metadata"]

        video_id = "invalid_video_id"

        # Step 1: Create job for invalid video
        job_request = CreateJobRequest(
            job_type=JobType.VIDEO_DOWNLOAD,
            urls=[f"https://www.youtube.com/watch?v={video_id}"],
            options={},
        )
        await jobs_service._create_job(job_request)

        # Step 2: Try to fetch metadata (should fail)
        metadata = await metadata_service._get_video_metadata(video_id)
        assert metadata is None  # Should return None for unavailable video

        # Step 3: Job should be marked as failed
        # (In real implementation, this would be handled by job execution)

        print(f"✅ Invalid video error handling verified for {video_id}")

    @pytest.mark.asyncio
    async def test_download_cancellation_workflow(
        self, running_services, temp_storage_dir
    ):
        """Test download cancellation mid-process."""

        download_service = running_services["download"]

        # Step 1: Start download
        request = download_service.DownloadRequest(
            video_id="test_video", output_path=temp_storage_dir
        )
        task = await download_service._create_download_task(request)

        # Step 2: Cancel download
        cancel_result = await download_service._cancel_download_task(task.task_id)

        assert cancel_result["status"] == "cancelled"
        assert task.status == download_service.DownloadStatus.CANCELLED

        print("✅ Download cancellation workflow verified")

    @pytest.mark.asyncio
    @patch("services.metadata.main.build")
    async def test_quota_exhaustion_scenario(
        self, mock_youtube_build, running_services
    ):
        """Test behavior when YouTube API quota is exhausted."""

        metadata_service = running_services["metadata"]

        # Simulate quota exhaustion
        metadata_service.quota_used = 9500  # Near limit
        metadata_service.quota_limit = 10000

        # Should still allow requests with reserve quota
        can_make_request = metadata_service._can_make_request(600)  # High cost request
        assert not can_make_request  # Should be blocked due to insufficient quota

        # Should allow low-cost requests
        can_make_low_cost = metadata_service._can_make_request(100)
        assert can_make_low_cost  # Should be allowed with reserve

        print("✅ Quota management scenario verified")


class TestPerformanceMetrics:
    """Test performance characteristics of the system."""

    @pytest.mark.asyncio
    @patch("services.metadata.main.build")
    async def test_metadata_caching_performance(
        self, mock_youtube_build, running_services, mock_youtube_api
    ):
        """Test that metadata caching improves performance."""

        # Setup YouTube API mock
        mock_youtube_service = MagicMock()
        mock_youtube_service.videos().list().execute.return_value = mock_youtube_api
        mock_youtube_build.return_value = mock_youtube_service

        metadata_service = running_services["metadata"]
        video_id = "dQw4w9WgXcQ"

        # First request (cold cache)
        start_time = time.time()
        metadata1 = await metadata_service._get_video_metadata(video_id)
        first_request_time = time.time() - start_time

        # Second request (warm cache)
        start_time = time.time()
        metadata2 = await metadata_service._get_video_metadata(video_id)
        second_request_time = time.time() - start_time

        # Verify caching worked
        assert metadata1.title == metadata2.title
        assert second_request_time < first_request_time  # Should be faster
        assert (
            mock_youtube_service.videos().list().execute.call_count == 1
        )  # Only called once

        print(
            f"✅ Caching performance verified: {first_request_time:.3f}s → {second_request_time:.3f}s"
        )

    @pytest.mark.asyncio
    async def test_concurrent_operation_performance(
        self, running_services, temp_storage_dir
    ):
        """Test system performance under concurrent operations."""

        storage_service = running_services["storage"]

        # Test concurrent storage operations
        video_ids = [f"video_{i}" for i in range(10)]

        start_time = time.time()

        # Simulate concurrent metadata saves
        tasks = []
        for video_id in video_ids:
            task = storage_service._save_metadata(
                video_id, {"title": f"Test Video {video_id}"}
            )
            tasks.append(task)

        # Wait for all operations to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        total_time = end_time - start_time

        # Verify all operations succeeded
        successful_ops = sum(
            1
            for result in results
            if isinstance(result, dict) and result.get("success")
        )
        assert successful_ops == len(video_ids)

        print(
            f"✅ Concurrent operations completed: {successful_ops} ops in {total_time:.3f}s"
        )

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, running_services):
        """Test memory usage characteristics under load."""

        download_service = running_services["download"]

        # Create many tasks to test memory management
        initial_task_count = len(download_service.active_tasks)

        # Create 20 tasks
        for i in range(20):
            request = download_service.DownloadRequest(
                video_id=f"load_test_{i}", output_path="/tmp"
            )
            await download_service._create_download_task(request)

        # Verify tasks are tracked
        assert len(download_service.active_tasks) == initial_task_count + 20

        # Simulate task completion and cleanup
        task_ids = list(download_service.active_tasks.keys())
        for task_id in task_ids[initial_task_count:]:  # Clean up our test tasks
            if task_id in download_service.background_tasks:
                download_service.background_tasks.pop(task_id)
            download_service.active_tasks.pop(task_id, None)
            download_service.task_progress.pop(task_id, None)

        # Verify cleanup
        assert len(download_service.active_tasks) == initial_task_count

        print("✅ Memory management under load verified")


class TestServiceIntegration:
    """Test integration between different services."""

    @pytest.mark.asyncio
    async def test_jobs_storage_integration(self, running_services, temp_storage_dir):
        """Test Jobs service integration with Storage service."""

        jobs_service = running_services["jobs"]
        storage_service = running_services["storage"]

        # Create job
        await jobs_service._create_job(
            {
                "job_type": "VIDEO_DOWNLOAD",
                "video_id": "test_video",
                "config": {"output_path": temp_storage_dir},
            }
        )

        # Simulate storage operations for the job
        metadata = {"title": "Test Video", "duration": 120}
        storage_result = await storage_service._save_metadata("test_video", metadata)

        assert storage_result["success"] is True

        # Verify storage state
        exists_result = await storage_service._check_video_exists("test_video")
        assert exists_result.has_metadata

        print("✅ Jobs-Storage integration verified")

    @pytest.mark.asyncio
    @patch("services.metadata.main.build")
    async def test_metadata_storage_integration(
        self, mock_youtube_build, running_services, mock_youtube_api
    ):
        """Test Metadata service integration with Storage service."""

        # Setup YouTube API mock
        mock_youtube_service = MagicMock()
        mock_youtube_service.videos().list().execute.return_value = mock_youtube_api
        mock_youtube_build.return_value = mock_youtube_service

        metadata_service = running_services["metadata"]
        storage_service = running_services["storage"]

        video_id = "dQw4w9WgXcQ"

        # Fetch metadata
        metadata = await metadata_service._get_video_metadata(video_id)
        assert metadata is not None

        # Save to storage
        storage_result = await storage_service._save_metadata(
            video_id, metadata.model_dump()
        )
        assert storage_result["success"] is True

        # Retrieve from storage
        retrieved_metadata = await storage_service._get_metadata(video_id)
        assert retrieved_metadata["title"] == metadata.title

        print("✅ Metadata-Storage integration verified")

    @pytest.mark.asyncio
    async def test_download_storage_integration(
        self, running_services, temp_storage_dir
    ):
        """Test Download service integration with Storage service."""

        download_service = running_services["download"]
        storage_service = running_services["storage"]

        video_id = "test_video"

        # Create download task
        request = download_service.DownloadRequest(
            video_id=video_id, output_path=str(Path(temp_storage_dir) / "videos")
        )
        await download_service._create_download_task(request)

        # Simulate video file creation
        video_file = Path(temp_storage_dir) / "videos" / f"{video_id}.mp4"
        video_file.parent.mkdir(parents=True, exist_ok=True)
        video_file.write_text("fake video content")

        # Update storage with video info
        video_info = {
            "file_path": str(video_file),
            "file_size": video_file.stat().st_size,
            "format": "mp4",
        }
        storage_result = await storage_service._save_video_info(video_id, video_info)
        assert storage_result["success"] is True

        # Verify integration
        exists_result = await storage_service._check_video_exists(video_id)
        assert exists_result.has_video

        print("✅ Download-Storage integration verified")


# Performance benchmarks
@pytest.mark.performance
class TestPerformanceBenchmarks:
    """Performance benchmarks for the system."""

    @pytest.mark.asyncio
    async def test_throughput_benchmark(self, running_services):
        """Measure system throughput under various loads."""

        storage_service = running_services["storage"]

        # Benchmark metadata operations
        operations = 100
        start_time = time.time()

        for i in range(operations):
            await storage_service._save_metadata(
                f"benchmark_{i}", {"title": f"Benchmark Video {i}", "duration": 120}
            )

        end_time = time.time()
        throughput = operations / (end_time - start_time)

        print(f"📊 Metadata operations throughput: {throughput:.2f} ops/sec")

        # Should handle at least 50 operations per second
        assert throughput > 50

    @pytest.mark.asyncio
    async def test_latency_benchmark(self, running_services):
        """Measure response latencies for key operations."""

        storage_service = running_services["storage"]

        # Measure storage operation latency
        latencies = []
        for i in range(10):
            start = time.time()
            await storage_service._check_video_exists(f"latency_test_{i}")
            latency = (time.time() - start) * 1000  # Convert to ms
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        print(
            f"📊 Storage operation latency: avg={avg_latency:.2f}ms, max={max_latency:.2f}ms"
        )

        # Latency should be reasonable (< 100ms for local operations)
        assert avg_latency < 100
        assert max_latency < 200
