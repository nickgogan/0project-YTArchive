"""
Comprehensive integration tests for Storage Service retry behavior and coordination.

This module tests storage service retry patterns in isolation and coordination
with other services, focusing on:
- Storage operation retry patterns during filesystem issues
- Metadata persistence retry coordination
- Storage service integration with download and jobs services
- Multi-level retry coordination during storage failures
- Disk space and permission error recovery patterns
"""

import os
import time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, List, Optional, Any

import pytest
import pytest_asyncio

from tests.common.temp_utils import temp_dir
from services.storage.main import StorageService
from services.download.main import DownloadService
from services.jobs.main import JobsService
from services.common.base import ServiceSettings
from services.error_recovery.base import ErrorRecoveryManager
from services.error_recovery.retry.strategies import (
    ExponentialBackoffStrategy,
    CircuitBreakerStrategy,
    AdaptiveStrategy,
)
from services.error_recovery.types import RetryConfig, ErrorContext
from services.error_recovery.reporting import BasicErrorReporter

# Set required environment variables for testing
os.environ.setdefault("YOUTUBE_API_KEY", "test_api_key_for_testing")


# Using centralized temp_dir fixture from tests.common.temp_utils
temp_storage_dir = temp_dir  # Alias for backward compatibility


@pytest.fixture
def service_settings():
    """Create service settings for testing."""
    return ServiceSettings(port=0)  # Use random available port


@pytest.fixture
def retry_config():
    """Create retry configuration for testing."""
    return RetryConfig(
        max_attempts=5,
        base_delay=0.1,  # Fast retries for testing
        max_delay=2.0,
        failure_threshold=3,
        recovery_timeout=1.0,
    )


@pytest_asyncio.fixture
async def storage_service_with_retry(temp_storage_dir, service_settings, retry_config):
    """Create Storage service with retry capabilities for testing."""
    service = StorageService("StorageService", service_settings)

    # Override paths to use temp directory
    service.base_output_dir = Path(temp_storage_dir)
    service.metadata_dir = Path(temp_storage_dir) / "metadata"
    service.videos_dir = Path(temp_storage_dir) / "videos"
    service.work_plans_dir = Path(temp_storage_dir) / "work_plans"
    service.recovery_plans_dir = Path(temp_storage_dir) / "recovery_plans"

    # Create directories
    service.metadata_dir.mkdir(parents=True, exist_ok=True)
    service.videos_dir.mkdir(parents=True, exist_ok=True)
    service.work_plans_dir.mkdir(parents=True, exist_ok=True)
    service.recovery_plans_dir.mkdir(parents=True, exist_ok=True)

    # Setup retry manager
    strategy = ExponentialBackoffStrategy(retry_config)
    reporter = BasicErrorReporter()
    service.retry_manager = ErrorRecoveryManager(strategy, reporter)

    yield service


@pytest_asyncio.fixture
async def download_service_with_retry(service_settings, retry_config):
    """Create Download service with retry capabilities for testing."""
    service = DownloadService("DownloadService", service_settings)

    # Setup retry manager
    strategy = CircuitBreakerStrategy(retry_config)
    reporter = BasicErrorReporter()
    service.retry_manager = ErrorRecoveryManager(strategy, reporter)

    yield service


@pytest_asyncio.fixture
async def jobs_service_with_retry(service_settings, retry_config):
    """Create Jobs service with retry capabilities for testing."""
    service = JobsService("JobsService", service_settings)

    # Setup retry manager
    strategy = AdaptiveStrategy(retry_config)
    reporter = BasicErrorReporter()
    service.retry_manager = ErrorRecoveryManager(strategy, reporter)

    # Mock external methods
    service.run = MagicMock()
    service._start_server = AsyncMock()

    yield service


class StorageFailureSimulator:
    """Utility for simulating various storage failure patterns."""

    def __init__(self):
        self.call_counts: Dict[str, int] = {}
        self.failure_patterns: Dict[str, List[bool]] = {}
        self.error_types: Dict[str, List[Exception]] = {}

    def setup_failure_pattern(
        self,
        operation: str,
        pattern: List[bool],
        error_types: Optional[List[Exception]] = None,
    ):
        """Setup a failure pattern for a storage operation."""
        self.failure_patterns[operation] = pattern
        self.error_types[operation] = error_types or [
            OSError("Simulated storage failure")
        ] * len(pattern)
        self.call_counts[operation] = 0

    async def simulate_storage_operation(self, operation: str, **kwargs) -> Any:
        """Simulate a storage operation with configured failure pattern."""
        if operation not in self.failure_patterns:
            return f"success_{operation}_{kwargs.get('video_id', 'unknown')}"

        call_index = self.call_counts[operation]
        pattern = self.failure_patterns[operation]

        # Cycle through pattern if we exceed its length
        pattern_index = call_index % len(pattern)
        should_succeed = pattern[pattern_index]

        self.call_counts[operation] += 1

        if should_succeed:
            return (
                f"success_{operation}_{kwargs.get('video_id', 'unknown')}_{call_index}"
            )
        else:
            error = (
                self.error_types[operation][pattern_index]
                if self.error_types[operation]
                else OSError("Storage failure")
            )
            raise error


class TestStorageServiceRetryIntegration:
    """Test Storage service retry patterns in isolation and coordination."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_metadata_save_retry_patterns(self, storage_service_with_retry):
        """Test storage service retry patterns during metadata save failures."""
        failure_sim = StorageFailureSimulator()

        # Setup failure patterns for metadata operations
        failure_sim.setup_failure_pattern(
            "save_metadata",
            [False, False, True, True],  # Fail twice, then succeed
            [
                PermissionError("Permission denied writing metadata"),
                OSError("Disk full"),
                None,
                None,
            ],
        )

        storage_service = storage_service_with_retry

        async def mock_metadata_save(video_id: str, metadata: Dict[str, Any]):
            """Mock metadata save operation with failure simulation."""
            return await failure_sim.simulate_storage_operation(
                "save_metadata", video_id=video_id, metadata=metadata
            )

        # Test metadata save with retries
        test_metadata = {
            "title": "Test Video",
            "duration": 300,
            "upload_date": "2025-01-29",
            "description": "Test video for retry integration",
        }

        context = ErrorContext(
            operation_name="metadata_save_retry",
            video_id="test_video_storage",
            operation_context={"operation": "save_metadata"},
        )

        start_time = time.time()
        result = await storage_service.retry_manager.execute_with_retry(
            lambda: mock_metadata_save("test_video_storage", test_metadata), context
        )
        execution_time = time.time() - start_time

        # Verify successful completion after retries
        assert result.startswith("success_save_metadata_test_video_storage")

        # Verify retry behavior
        print(f"Metadata save retries: {failure_sim.call_counts['save_metadata']}")
        print(f"Execution time: {execution_time:.2f}s")

        assert (
            failure_sim.call_counts["save_metadata"] >= 3
        ), "Should have retried failed operations"
        assert (
            execution_time < 5.0
        ), f"Retry coordination took too long: {execution_time:.2f}s"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_video_info_save_retry_coordination(self, storage_service_with_retry):
        """Test video info save retry coordination with different error types."""
        failure_sim = StorageFailureSimulator()

        # Setup complex failure patterns for video info operations
        failure_sim.setup_failure_pattern(
            "save_video_info",
            [False, False, False, True],  # Multiple failures before success
            [
                OSError("No space left on device"),
                PermissionError("Permission denied"),
                IOError("I/O error occurred"),
                None,
            ],
        )

        storage_service = storage_service_with_retry

        async def mock_video_info_save(video_id: str, video_info: Dict[str, Any]):
            """Mock video info save with failure simulation."""
            return await failure_sim.simulate_storage_operation(
                "save_video_info", video_id=video_id, info=video_info
            )

        # Test video info save with retries
        test_video_info = {
            "video_path": "/tmp/test_video.mp4",
            "file_size": 104857600,  # 100MB
            "thumbnail_path": "/tmp/test_thumbnail.jpg",
            "captions": {"en": "/tmp/captions_en.srt"},
        }

        context = ErrorContext(
            operation_name="video_info_save_retry",
            video_id="test_video_info",
            operation_context={"operation": "save_video_info"},
        )

        start_time = time.time()
        result = await storage_service.retry_manager.execute_with_retry(
            lambda: mock_video_info_save("test_video_info", test_video_info), context
        )
        execution_time = time.time() - start_time

        # Verify successful completion
        assert result.startswith("success_save_video_info_test_video_info")

        # Verify retry coordination handled different error types
        print(f"Video info save retries: {failure_sim.call_counts['save_video_info']}")
        print(f"Recovery time: {execution_time:.2f}s")

        assert (
            failure_sim.call_counts["save_video_info"] >= 4
        ), "Should have handled multiple error types"
        assert (
            execution_time < 8.0
        ), f"Error recovery took too long: {execution_time:.2f}s"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_storage_download_integration_retries(
        self, storage_service_with_retry, download_service_with_retry
    ):
        """Test storage service integration with download service during failures."""
        storage_sim = StorageFailureSimulator()
        download_sim = StorageFailureSimulator()

        # Setup coordinated failure patterns
        storage_sim.setup_failure_pattern(
            "save_completed_download",
            [False, True, True],  # Storage fails once
            [OSError("Storage temporarily unavailable")],
        )

        download_sim.setup_failure_pattern(
            "notify_storage",
            [False, False, True],  # Download notification fails twice
            [ConnectionError("Cannot reach storage service")] * 2 + [None],
        )

        storage_service = storage_service_with_retry
        download_service = download_service_with_retry

        async def mock_storage_save(video_id: str, download_info: Dict[str, Any]):
            """Mock storage save for completed download."""
            return await storage_sim.simulate_storage_operation(
                "save_completed_download", video_id=video_id, info=download_info
            )

        async def mock_download_notify(video_id: str, storage_path: str):
            """Mock download service notifying storage."""
            return await download_sim.simulate_storage_operation(
                "notify_storage", video_id=video_id, path=storage_path
            )

        async def integrated_download_storage_workflow():
            """Simulate integrated download-storage workflow with retries."""
            video_id = "integration_test_video"

            # Step 1: Download completes and notifies storage (with retries)
            download_context = ErrorContext(
                operation_name="download_completion",
                video_id=video_id,
                operation_context={"phase": "download_complete"},
            )

            notification_result = (
                await download_service.retry_manager.execute_with_retry(
                    lambda: mock_download_notify(
                        video_id, f"/downloads/{video_id}.mp4"
                    ),
                    download_context,
                )
            )

            # Step 2: Storage saves download info (with retries)
            storage_context = ErrorContext(
                operation_name="storage_save",
                video_id=video_id,
                operation_context={"phase": "storage_save"},
            )

            download_info = {
                "video_path": f"/downloads/{video_id}.mp4",
                "file_size": 157286400,  # 150MB
                "download_completed_at": "2025-01-29T21:30:00Z",
            }

            storage_result = await storage_service.retry_manager.execute_with_retry(
                lambda: mock_storage_save(video_id, download_info), storage_context
            )

            return {
                "download_notification": notification_result,
                "storage_save": storage_result,
            }

        start_time = time.time()
        result = await integrated_download_storage_workflow()
        execution_time = time.time() - start_time

        # Verify successful integration
        assert result["download_notification"].startswith("success_notify_storage")
        assert result["storage_save"].startswith("success_save_completed_download")

        # Verify retry coordination
        print(f"Download notify retries: {download_sim.call_counts['notify_storage']}")
        print(
            f"Storage save retries: {storage_sim.call_counts['save_completed_download']}"
        )
        print(f"Integration time: {execution_time:.2f}s")

        assert (
            download_sim.call_counts["notify_storage"] >= 3
        ), "Download should have retried notifications"
        assert (
            storage_sim.call_counts["save_completed_download"] >= 2
        ), "Storage should have retried saves"
        assert (
            execution_time < 10.0
        ), f"Integration took too long: {execution_time:.2f}s"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_multi_level_storage_retry_coordination(
        self, storage_service_with_retry, jobs_service_with_retry
    ):
        """Test multi-level retry coordination with jobs service orchestrating storage operations."""
        failure_sim = StorageFailureSimulator()

        # Setup cascading failure patterns
        failure_sim.setup_failure_pattern(
            "metadata_operation",
            [False, False, True],  # Metadata fails twice
            [OSError("Metadata directory locked")] * 2 + [None],
        )

        failure_sim.setup_failure_pattern(
            "video_operation",
            [False, True],  # Video operation fails once
            [PermissionError("Video directory read-only")] + [None],
        )

        failure_sim.setup_failure_pattern(
            "recovery_plan",
            [True],  # Recovery plan succeeds immediately
        )

        storage_service = storage_service_with_retry
        jobs_service = jobs_service_with_retry

        async def mock_metadata_op(video_id: str):
            return await failure_sim.simulate_storage_operation(
                "metadata_operation", video_id=video_id
            )

        async def mock_video_op(video_id: str):
            return await failure_sim.simulate_storage_operation(
                "video_operation", video_id=video_id
            )

        async def mock_recovery_plan(video_id: str):
            return await failure_sim.simulate_storage_operation(
                "recovery_plan", video_id=video_id
            )

        async def orchestrated_storage_workflow():
            """Jobs service orchestrating multiple storage operations with individual retries."""
            video_id = "multi_level_test"
            results = {}

            # Level 1: Jobs service orchestrates storage operations
            # Level 2: Storage service handles individual operation retries

            # Operation 1: Metadata handling (with storage-level retries)
            metadata_context = ErrorContext(
                operation_name="orchestrated_metadata",
                video_id=video_id,
                operation_context={"level": "storage", "op": "metadata"},
            )
            results[
                "metadata"
            ] = await storage_service.retry_manager.execute_with_retry(
                lambda: mock_metadata_op(video_id), metadata_context
            )

            # Operation 2: Video handling (with storage-level retries)
            video_context = ErrorContext(
                operation_name="orchestrated_video",
                video_id=video_id,
                operation_context={"level": "storage", "op": "video"},
            )
            results["video"] = await storage_service.retry_manager.execute_with_retry(
                lambda: mock_video_op(video_id), video_context
            )

            # Operation 3: Recovery plan (with storage-level retries)
            recovery_context = ErrorContext(
                operation_name="orchestrated_recovery",
                video_id=video_id,
                operation_context={"level": "storage", "op": "recovery"},
            )
            results[
                "recovery"
            ] = await storage_service.retry_manager.execute_with_retry(
                lambda: mock_recovery_plan(video_id), recovery_context
            )

            return results

        # Execute orchestrated workflow with jobs-level retries
        job_context = ErrorContext(
            operation_name="storage_orchestration",
            video_id="multi_level_test",
            operation_context={"level": "jobs", "orchestration": True},
        )

        start_time = time.time()
        result = await jobs_service.retry_manager.execute_with_retry(
            orchestrated_storage_workflow, job_context
        )
        execution_time = time.time() - start_time

        # Verify successful multi-level coordination
        assert result["metadata"].startswith("success_metadata_operation")
        assert result["video"].startswith("success_video_operation")
        assert result["recovery"].startswith("success_recovery_plan")

        # Verify multi-level retry coordination
        print(f"Multi-level retry counts: {failure_sim.call_counts}")
        print(f"Orchestration time: {execution_time:.2f}s")

        assert (
            failure_sim.call_counts["metadata_operation"] >= 3
        ), "Metadata should have retried multiple times"
        assert (
            failure_sim.call_counts["video_operation"] >= 2
        ), "Video should have retried once"
        assert (
            failure_sim.call_counts["recovery_plan"] >= 1
        ), "Recovery should have succeeded immediately"
        assert (
            execution_time < 12.0
        ), f"Multi-level coordination took too long: {execution_time:.2f}s"


class TestStorageServiceErrorRecovery:
    """Test storage service error recovery patterns."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_disk_space_recovery_pattern(self, storage_service_with_retry):
        """Test storage service recovery patterns during disk space issues."""
        failure_sim = StorageFailureSimulator()

        # Simulate disk space recovery scenario
        failure_sim.setup_failure_pattern(
            "disk_space_operation",
            [False, False, False, True],  # Disk space gets freed after 3 attempts
            [
                OSError("No space left on device"),
                OSError("No space left on device"),
                OSError("Insufficient disk space"),
                None,
            ],
        )

        storage_service = storage_service_with_retry

        async def mock_large_file_save(video_id: str, file_size: int):
            """Mock saving large file that might fail due to disk space."""
            return await failure_sim.simulate_storage_operation(
                "disk_space_operation", video_id=video_id, size=file_size
            )

        context = ErrorContext(
            operation_name="disk_space_recovery",
            video_id="large_video_test",
            operation_context={"issue": "disk_space", "file_size": "2GB"},
        )

        start_time = time.time()
        result = await storage_service.retry_manager.execute_with_retry(
            lambda: mock_large_file_save("large_video_test", 2147483648), context  # 2GB
        )
        execution_time = time.time() - start_time

        # Verify recovery after disk space issues
        assert result.startswith("success_disk_space_operation")

        print(
            f"Disk space recovery attempts: {failure_sim.call_counts['disk_space_operation']}"
        )
        print(f"Recovery time: {execution_time:.2f}s")

        assert (
            failure_sim.call_counts["disk_space_operation"] >= 4
        ), "Should have recovered after space freed"
        assert (
            execution_time < 15.0
        ), f"Disk space recovery took too long: {execution_time:.2f}s"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_permission_error_retry_patterns(self, storage_service_with_retry):
        """Test storage service retry patterns during permission errors."""
        failure_sim = StorageFailureSimulator()

        # Simulate permission error recovery
        failure_sim.setup_failure_pattern(
            "permission_operation",
            [False, False, True],  # Permission gets fixed after 2 attempts
            [
                PermissionError("Permission denied: metadata directory"),
                PermissionError("Write permission denied"),
                None,
            ],
        )

        storage_service = storage_service_with_retry

        async def mock_permission_sensitive_operation(video_id: str):
            """Mock operation that might fail due to permissions."""
            return await failure_sim.simulate_storage_operation(
                "permission_operation", video_id=video_id
            )

        context = ErrorContext(
            operation_name="permission_recovery",
            video_id="permission_test_video",
            operation_context={"issue": "permissions", "operation": "metadata_write"},
        )

        start_time = time.time()
        result = await storage_service.retry_manager.execute_with_retry(
            lambda: mock_permission_sensitive_operation("permission_test_video"),
            context,
        )
        execution_time = time.time() - start_time

        # Verify permission error recovery
        assert result.startswith("success_permission_operation")

        print(
            f"Permission recovery attempts: {failure_sim.call_counts['permission_operation']}"
        )
        print(f"Recovery time: {execution_time:.2f}s")

        assert (
            failure_sim.call_counts["permission_operation"] >= 3
        ), "Should have recovered after permissions fixed"
        assert (
            execution_time < 8.0
        ), f"Permission recovery took too long: {execution_time:.2f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
