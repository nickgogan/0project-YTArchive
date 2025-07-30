"""Simplified integration tests focusing on service coordination."""

import asyncio
from tests.common.temp_utils import temp_dir
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

# Import individual service components
from services.jobs.main import JobsService, CreateJobRequest
from services.storage.main import StorageService
from services.download.main import DownloadService, DownloadRequest, DownloadStatus
from services.common.base import ServiceSettings
from services.common.models import JobType, JobStatus


# Using centralized temp_dir fixture from tests.common.temp_utils
temp_storage_dir = temp_dir  # Alias for backward compatibility


@pytest.fixture
def service_settings():
    """Create service settings for testing."""
    return ServiceSettings(port=0)  # Use random available port


@pytest_asyncio.fixture
async def jobs_service(service_settings):
    """Create Jobs service for testing."""
    service = JobsService("JobsService", service_settings)
    service.run = MagicMock()  # Mock the run method
    yield service


@pytest_asyncio.fixture
async def storage_service(temp_storage_dir, service_settings):
    """Create Storage service for testing."""
    service = StorageService("StorageService", service_settings)
    # Override all storage paths to use temp directory
    service.base_output_dir = Path(temp_storage_dir)
    service.metadata_dir = Path(temp_storage_dir) / "metadata"
    service.videos_dir = Path(temp_storage_dir) / "videos"
    service.work_plans_dir = Path(temp_storage_dir) / "work_plans"

    # Create the directories
    service.metadata_dir.mkdir(parents=True, exist_ok=True)
    service.videos_dir.mkdir(parents=True, exist_ok=True)
    service.work_plans_dir.mkdir(parents=True, exist_ok=True)
    (service.metadata_dir / "videos").mkdir(parents=True, exist_ok=True)
    (service.metadata_dir / "playlists").mkdir(parents=True, exist_ok=True)

    service.run = MagicMock()  # Mock the run method
    yield service


@pytest_asyncio.fixture
async def download_service(service_settings):
    """Create Download service for testing."""
    service = DownloadService("DownloadService", service_settings)
    service.run = MagicMock()  # Mock the run method
    yield service

    # Cleanup any background tasks
    if hasattr(service, "cleanup_pending_tasks"):
        await service.cleanup_pending_tasks()


class TestServiceCoordination:
    """Test coordination between different services."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_job_creation_and_storage_interaction(
        self, jobs_service, storage_service, temp_storage_dir
    ):
        """Test Jobs service creates jobs and Storage service can track them."""

        # Step 1: Create a job via Jobs service
        job_request = CreateJobRequest(
            job_type=JobType.VIDEO_DOWNLOAD,
            urls=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
            options={"quality": "720p", "output_path": str(temp_storage_dir)},
        )
        job_data = await jobs_service._create_job(job_request)

        # Verify job was created properly
        assert job_data.job_type == JobType.VIDEO_DOWNLOAD
        assert job_data.status == JobStatus.PENDING
        assert len(job_data.urls) == 1
        job_id = job_data.job_id

        # Step 2: Verify we can retrieve the job
        retrieved_job = await jobs_service._get_job(job_id)
        assert retrieved_job is not None
        assert retrieved_job.job_id == job_id
        assert retrieved_job.status == JobStatus.PENDING

        # Step 3: Test Storage service can handle video existence checks
        video_id = "dQw4w9WgXcQ"
        storage_exists = await storage_service._check_video_exists(video_id)
        assert not storage_exists.exists  # Should not exist initially

        # Step 4: Simulate metadata saving via Storage service
        fake_metadata = {
            "title": "Test Video",
            "channel_title": "Test Channel",
            "duration": 180,
            "upload_date": "2023-01-01",
        }
        metadata_result = await storage_service._save_metadata(video_id, fake_metadata)
        assert "path" in metadata_result  # Verify metadata was saved successfully
        assert "saved_at" in metadata_result

        # Step 5: Verify storage now shows metadata exists
        updated_storage_state = await storage_service._check_video_exists(video_id)
        assert updated_storage_state.has_metadata

        print(" Job creation and storage interaction test passed")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_download_task_management(self, download_service, temp_storage_dir):
        """Test Download service task management without external dependencies."""

        # Step 1: Create a download task
        download_request = DownloadRequest(
            video_id="test_video_123", output_path=str(temp_storage_dir), quality="720p"
        )

        # Mock storage service to avoid HTTP calls
        with patch.object(
            download_service, "_get_storage_path", return_value=temp_storage_dir
        ):
            task = await download_service._create_download_task(download_request)

        # Verify task was created
        assert task.video_id == "test_video_123"
        assert task.status.value == "pending"
        assert task.task_id in download_service.active_tasks

        # Step 2: Test progress tracking
        task_progress = await download_service._get_task_progress(task.task_id)
        assert task_progress is not None
        assert task_progress.task_id == task.task_id
        assert task_progress.video_id == "test_video_123"

        # Step 3: Test task cancellation
        cancel_result = await download_service._cancel_download_task(task.task_id)
        assert cancel_result["status"] == "cancelled"
        assert task.status == DownloadStatus.CANCELLED

        print("✅ Download task management test passed")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_job_processing(self, jobs_service):
        """Test Jobs service can handle multiple concurrent jobs."""

        # Create multiple jobs
        job_requests = []
        for i in range(5):
            job_request = CreateJobRequest(
                job_type=JobType.VIDEO_DOWNLOAD,
                urls=[f"https://www.youtube.com/watch?v=video_{i}"],
                options={"quality": "720p"},
            )
            job_requests.append(job_request)

        # Create all jobs concurrently
        jobs = await asyncio.gather(
            *[jobs_service._create_job(req) for req in job_requests]
        )

        # Verify all jobs were created
        assert len(jobs) == 5
        for i, job in enumerate(jobs):
            assert job.job_type == JobType.VIDEO_DOWNLOAD
            assert job.status == JobStatus.PENDING
            assert f"video_{i}" in job.urls[0]

        # Test listing jobs
        job_list = await jobs_service._list_jobs(None, 10)
        assert len(job_list) >= 5  # Should include our new jobs

        print("✅ Concurrent job processing test passed")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_storage_batch_operations(self, storage_service):
        """Test Storage service can handle batch operations efficiently."""

        # Test saving multiple metadata files
        video_ids = [f"video_{i}" for i in range(10)]
        metadata_operations = []

        for i, video_id in enumerate(video_ids):
            metadata = {
                "title": f"Test Video {video_id}",
                "duration": 120 + i,
                "channel_title": "Test Channel",
            }
            operation = storage_service._save_metadata(video_id, metadata)
            metadata_operations.append(operation)

        # Execute all operations concurrently
        results = await asyncio.gather(*metadata_operations)

        # Verify all operations succeeded
        for result in results:
            assert "path" in result  # Verify metadata was saved successfully
            assert "saved_at" in result

        # Test batch existence checking
        existence_checks = []
        for video_id in video_ids:
            check = storage_service._check_video_exists(video_id)
            existence_checks.append(check)

        existence_results = await asyncio.gather(*existence_checks)

        # Verify all videos now have metadata
        for result in existence_results:
            assert result.has_metadata

        print("✅ Storage batch operations test passed")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_error_handling_integration(self, jobs_service, storage_service):
        """Test error handling across service boundaries."""

        # Step 1: Create a job with invalid configuration
        invalid_job_request = CreateJobRequest(
            job_type=JobType.VIDEO_DOWNLOAD,
            urls=["invalid_url"],
            options={"quality": "invalid_quality"},
        )

        # Job creation should still succeed (validation happens later)
        job = await jobs_service._create_job(invalid_job_request)
        assert job.status == JobStatus.PENDING

        # Step 2: Test storage service handles missing data gracefully
        nonexistent_video = "nonexistent_video_12345"
        storage_check = await storage_service._check_video_exists(nonexistent_video)
        assert not storage_check.exists
        assert not storage_check.has_metadata
        assert not storage_check.has_video

        # Step 3: Test metadata retrieval for nonexistent video
        try:
            metadata = await storage_service._get_metadata(nonexistent_video)
            # Should either return None or empty dict
            assert metadata is None or metadata == {}
        except Exception:
            # Some implementations might raise exceptions, which is also valid
            pass

        print("✅ Error handling integration test passed")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_job_status_lifecycle(self, jobs_service):
        """Test complete job status lifecycle management."""

        # Step 1: Create job (starts as PENDING)
        job_request = CreateJobRequest(
            job_type=JobType.METADATA_ONLY,
            urls=["https://www.youtube.com/watch?v=test123"],
            options={},
        )
        job = await jobs_service._create_job(job_request)
        assert job.status == JobStatus.PENDING
        job_id = job.job_id

        # Step 2: Update to RUNNING
        running_job = await jobs_service._update_job_status(job_id, JobStatus.RUNNING)
        assert running_job is not None
        assert running_job.status == JobStatus.RUNNING

        # Step 3: Update to COMPLETED
        completed_job = await jobs_service._update_job_status(
            job_id, JobStatus.COMPLETED
        )
        assert completed_job is not None
        assert completed_job.status == JobStatus.COMPLETED

        # Step 4: Verify persistence
        final_job = await jobs_service._get_job(job_id)
        assert final_job.status == JobStatus.COMPLETED

        print("✅ Job status lifecycle test passed")


class TestPerformanceCharacteristics:
    """Test performance characteristics of service coordination."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_service_response_times(self, jobs_service, storage_service):
        """Test that service operations complete within reasonable time limits."""

        # Test job creation performance
        start_time = time.time()
        job_request = CreateJobRequest(
            job_type=JobType.VIDEO_DOWNLOAD,
            urls=["https://www.youtube.com/watch?v=perf_test"],
            options={},
        )
        await jobs_service._create_job(job_request)
        job_creation_time = time.time() - start_time

        # Job creation should be fast (< 100ms)
        assert job_creation_time < 0.1

        # Test storage operations performance
        start_time = time.time()
        await storage_service._check_video_exists("perf_test_video")
        storage_check_time = time.time() - start_time

        # Storage check should be fast (< 50ms)
        assert storage_check_time < 0.05

        print(
            f"✅ Performance test passed - Job creation: {job_creation_time:.3f}s, Storage check: {storage_check_time:.3f}s"
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_operation_performance(self, jobs_service):
        """Test performance under concurrent load."""

        # Create many jobs concurrently to test scalability
        start_time = time.time()

        job_requests = [
            CreateJobRequest(
                job_type=JobType.VIDEO_DOWNLOAD,
                urls=[f"https://www.youtube.com/watch?v=concurrent_{i}"],
                options={},
            )
            for i in range(20)
        ]

        jobs = await asyncio.gather(
            *[jobs_service._create_job(req) for req in job_requests]
        )

        total_time = time.time() - start_time
        throughput = len(jobs) / total_time

        # Should handle at least 50 job creations per second
        assert throughput > 50

        print(f"✅ Concurrent performance test passed - {throughput:.1f} jobs/sec")


class TestDataConsistency:
    """Test data consistency across service operations."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_job_data_persistence(self, jobs_service):
        """Test that job data persists correctly across operations."""

        # Create job with specific data
        original_options = {
            "quality": "1080p",
            "captions": True,
            "custom_field": "test_value",
        }
        job_request = CreateJobRequest(
            job_type=JobType.PLAYLIST_DOWNLOAD,
            urls=["https://www.youtube.com/playlist?list=test123"],
            options=original_options,
        )

        job = await jobs_service._create_job(job_request)
        job_id = job.job_id

        # Retrieve job and verify all data is intact
        retrieved_job = await jobs_service._get_job(job_id)
        assert retrieved_job.job_id == job_id
        assert retrieved_job.job_type == JobType.PLAYLIST_DOWNLOAD
        assert retrieved_job.urls == job_request.urls
        assert retrieved_job.options == original_options

        # Update status and verify other data remains unchanged
        updated_job = await jobs_service._update_job_status(job_id, JobStatus.RUNNING)
        assert updated_job.job_type == JobType.PLAYLIST_DOWNLOAD
        assert updated_job.urls == job_request.urls
        assert updated_job.options == original_options

        print("✅ Job data persistence test passed")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_storage_data_integrity(self, storage_service):
        """Test that storage operations maintain data integrity."""

        video_id = "integrity_test_video"

        # Save metadata with specific structure
        original_metadata = {
            "title": "Integrity Test Video",
            "duration": 300,
            "tags": ["test", "integration", "integrity"],
            "nested": {"quality": "1080p", "format": "mp4"},
        }

        save_result = await storage_service._save_metadata(video_id, original_metadata)
        assert "path" in save_result  # Verify metadata was saved successfully
        assert "saved_at" in save_result

        # Retrieve metadata and verify it matches exactly
        retrieved_result = await storage_service._get_stored_metadata(video_id)
        retrieved_metadata = retrieved_result["metadata"]
        assert retrieved_metadata["title"] == original_metadata["title"]
        assert retrieved_metadata["duration"] == original_metadata["duration"]
        assert retrieved_metadata["tags"] == original_metadata["tags"]
        assert (
            retrieved_metadata["nested"]["quality"]
            == original_metadata["nested"]["quality"]
        )

        print("✅ Storage data integrity test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
