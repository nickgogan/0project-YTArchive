"""
Comprehensive integration tests for Metadata Service retry behavior and coordination.

This module tests metadata service retry patterns in isolation and coordination
with other services, focusing on:
- YouTube API retry patterns during rate limiting and failures
- Metadata extraction retry coordination
- Metadata service integration with download and storage services
- Multi-level retry coordination during metadata failures
- API quota and network error recovery patterns
"""

import os
import time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, List, Optional, Any

import pytest
import pytest_asyncio

from tests.common.temp_utils import temp_dir
from services.metadata.main import MetadataService
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
async def metadata_service_with_retry(service_settings, retry_config):
    """Create Metadata service with retry capabilities for testing."""
    service = MetadataService("MetadataService", service_settings)

    # Setup retry manager
    strategy = ExponentialBackoffStrategy(retry_config)
    reporter = BasicErrorReporter()
    service.retry_manager = ErrorRecoveryManager(strategy, reporter)

    # Mock external methods to avoid actual API calls
    service.run = MagicMock()
    service._start_server = AsyncMock()

    yield service


@pytest_asyncio.fixture
async def storage_service_with_retry(temp_storage_dir, service_settings, retry_config):
    """Create Storage service with retry capabilities for testing."""
    service = StorageService("StorageService", service_settings)

    # Override paths to use temp directory
    service.base_output_dir = Path(temp_storage_dir)
    service.metadata_dir = Path(temp_storage_dir) / "metadata"
    service.videos_dir = Path(temp_storage_dir) / "videos"

    # Create directories
    service.metadata_dir.mkdir(parents=True, exist_ok=True)
    service.videos_dir.mkdir(parents=True, exist_ok=True)

    # Setup retry manager
    strategy = CircuitBreakerStrategy(retry_config)
    reporter = BasicErrorReporter()
    service.retry_manager = ErrorRecoveryManager(strategy, reporter)

    yield service


@pytest_asyncio.fixture
async def download_service_with_retry(service_settings, retry_config):
    """Create Download service with retry capabilities for testing."""
    service = DownloadService("DownloadService", service_settings)

    # Setup retry manager
    strategy = AdaptiveStrategy(retry_config)
    reporter = BasicErrorReporter()
    service.retry_manager = ErrorRecoveryManager(strategy, reporter)

    yield service


@pytest_asyncio.fixture
async def jobs_service_with_retry(service_settings, retry_config):
    """Create Jobs service with retry capabilities for testing."""
    service = JobsService("JobsService", service_settings)

    # Setup retry manager
    strategy = ExponentialBackoffStrategy(retry_config)
    reporter = BasicErrorReporter()
    service.retry_manager = ErrorRecoveryManager(strategy, reporter)

    # Mock external methods
    service.run = MagicMock()
    service._start_server = AsyncMock()

    yield service


class MetadataFailureSimulator:
    """Utility for simulating various metadata service failure patterns."""

    def __init__(self):
        self.call_counts: Dict[str, int] = {}
        self.failure_patterns: Dict[str, List[bool]] = {}
        self.error_types: Dict[str, List[Exception]] = {}
        self.response_data: Dict[str, List[Any]] = {}

    def setup_failure_pattern(
        self,
        operation: str,
        pattern: List[bool],
        error_types: Optional[List[Exception]] = None,
        response_data: Optional[List[Any]] = None,
    ):
        """Setup a failure pattern for a metadata operation."""
        self.failure_patterns[operation] = pattern
        self.error_types[operation] = error_types or [
            ConnectionError("API failure")
        ] * len(pattern)
        self.response_data[operation] = response_data or [{}] * len(pattern)
        self.call_counts[operation] = 0

    async def simulate_metadata_operation(
        self, operation: str, video_id: str = "unknown", **kwargs
    ) -> Any:
        """Simulate a metadata operation with configured failure pattern."""
        if operation not in self.failure_patterns:
            return {
                "video_id": video_id,
                "title": f"Test Video {video_id}",
                "operation": operation,
                "status": "success",
            }

        call_index = self.call_counts[operation]
        pattern = self.failure_patterns[operation]

        # Cycle through pattern if we exceed its length
        pattern_index = call_index % len(pattern)
        should_succeed = pattern[pattern_index]

        self.call_counts[operation] += 1

        if should_succeed:
            # Return success response
            base_response = (
                self.response_data[operation][pattern_index]
                if self.response_data[operation]
                else {}
            )
            return {
                "video_id": video_id,
                "title": f"Success Video {video_id}",
                "operation": operation,
                "attempt": call_index,
                "status": "success",
                **base_response,
            }
        else:
            # Raise configured error
            error = (
                self.error_types[operation][pattern_index]
                if self.error_types[operation]
                else ConnectionError("API failure")
            )
            raise error


class TestMetadataServiceRetryIntegration:
    """Test Metadata service retry patterns in isolation and coordination."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_youtube_api_rate_limit_retry(self, metadata_service_with_retry):
        """Test metadata service retry patterns during YouTube API rate limiting."""
        failure_sim = MetadataFailureSimulator()

        # Setup rate limiting failure pattern
        from googleapiclient.errors import HttpError
        import json

        # Mock HTTP errors for rate limiting
        rate_limit_errors = []
        for i in range(3):
            error_content = json.dumps(
                {
                    "error": {
                        "code": 403,
                        "message": "quotaExceeded",
                        "errors": [{"reason": "quotaExceeded"}],
                    }
                }
            ).encode()
            rate_limit_errors.append(
                HttpError(
                    resp=MagicMock(status=403, reason="Forbidden"),
                    content=error_content,
                )
            )

        failure_sim.setup_failure_pattern(
            "get_video_metadata",
            [False, False, False, True],  # Rate limited 3 times, then succeed
            rate_limit_errors + [None],
            [None, None, None, {"duration": 300, "views": 1000000}],
        )

        metadata_service = metadata_service_with_retry

        async def mock_youtube_api_call(video_id: str):
            """Mock YouTube API call with rate limiting simulation."""
            return await failure_sim.simulate_metadata_operation(
                "get_video_metadata", video_id=video_id
            )

        context = ErrorContext(
            operation_name="youtube_api_retry",
            video_id="rate_limit_test_video",
            operation_context={"api": "youtube_v3", "operation": "videos.list"},
        )

        start_time = time.time()
        result = await metadata_service.retry_manager.execute_with_retry(
            lambda: mock_youtube_api_call("rate_limit_test_video"), context
        )
        execution_time = time.time() - start_time

        # Verify successful completion after rate limit recovery
        assert result["status"] == "success"
        assert result["video_id"] == "rate_limit_test_video"
        assert "duration" in result

        # Verify rate limit retry behavior
        print(f"Rate limit retries: {failure_sim.call_counts['get_video_metadata']}")
        print(f"Recovery time: {execution_time:.2f}s")

        assert (
            failure_sim.call_counts["get_video_metadata"] >= 4
        ), "Should have retried rate limit errors"
        assert (
            execution_time < 10.0
        ), f"Rate limit recovery took too long: {execution_time:.2f}s"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_metadata_extraction_retry_coordination(
        self, metadata_service_with_retry
    ):
        """Test metadata extraction retry coordination with different error types."""
        failure_sim = MetadataFailureSimulator()

        # Setup complex failure patterns for metadata extraction
        failure_sim.setup_failure_pattern(
            "extract_video_info",
            [False, False, False, True],  # Multiple failures before success
            [
                ConnectionError("YouTube API temporarily unavailable"),
                TimeoutError("Request timeout"),
                ValueError("Invalid video ID format"),
                None,
            ],
            [
                None,
                None,
                None,
                {
                    "title": "Successfully Extracted Video",
                    "description": "Full video description",
                    "duration": 450,
                    "upload_date": "2025-01-29",
                    "uploader": "Test Channel",
                },
            ],
        )

        metadata_service = metadata_service_with_retry

        async def mock_metadata_extraction(video_id: str):
            """Mock metadata extraction with various failure types."""
            return await failure_sim.simulate_metadata_operation(
                "extract_video_info", video_id=video_id
            )

        context = ErrorContext(
            operation_name="metadata_extraction_retry",
            video_id="extraction_test_video",
            operation_context={"extraction": "full_metadata"},
        )

        start_time = time.time()
        result = await metadata_service.retry_manager.execute_with_retry(
            lambda: mock_metadata_extraction("extraction_test_video"), context
        )
        execution_time = time.time() - start_time

        # Verify successful extraction after retries
        assert result["status"] == "success"
        assert result["title"] == "Successfully Extracted Video"
        assert result["duration"] == 450

        # Verify retry coordination handled different error types
        print(f"Extraction retries: {failure_sim.call_counts['extract_video_info']}")
        print(f"Extraction time: {execution_time:.2f}s")

        assert (
            failure_sim.call_counts["extract_video_info"] >= 4
        ), "Should have handled multiple error types"
        assert (
            execution_time < 8.0
        ), f"Extraction retry took too long: {execution_time:.2f}s"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_metadata_storage_integration_retries(
        self, metadata_service_with_retry, storage_service_with_retry
    ):
        """Test metadata service integration with storage service during failures."""
        metadata_sim = MetadataFailureSimulator()
        storage_sim = MetadataFailureSimulator()

        # Setup coordinated failure patterns
        metadata_sim.setup_failure_pattern(
            "fetch_metadata",
            [False, True, True],  # Metadata fetch fails once
            [ConnectionError("YouTube API error")],
            [None, {"title": "Fetched Video", "duration": 240}],
        )

        storage_sim.setup_failure_pattern(
            "save_metadata",
            [False, False, True],  # Storage fails twice
            [
                OSError("Storage write error"),
                PermissionError("Write permission denied"),
            ],
            [None, None, {"saved": True}],
        )

        metadata_service = metadata_service_with_retry
        storage_service = storage_service_with_retry

        async def mock_metadata_fetch(video_id: str):
            """Mock metadata fetching with failures."""
            return await metadata_sim.simulate_metadata_operation(
                "fetch_metadata", video_id=video_id
            )

        async def mock_storage_save(video_id: str, metadata: Dict[str, Any]):
            """Mock storage save with failures."""
            return await storage_sim.simulate_metadata_operation(
                "save_metadata", video_id=video_id
            )

        async def integrated_metadata_storage_workflow():
            """Simulate integrated metadata-storage workflow with retries."""
            video_id = "integration_metadata_test"

            # Step 1: Fetch metadata (with retries)
            fetch_context = ErrorContext(
                operation_name="metadata_fetch",
                video_id=video_id,
                operation_context={"phase": "fetch"},
            )

            metadata = await metadata_service.retry_manager.execute_with_retry(
                lambda: mock_metadata_fetch(video_id), fetch_context
            )

            # Step 2: Save metadata to storage (with retries)
            save_context = ErrorContext(
                operation_name="metadata_storage",
                video_id=video_id,
                operation_context={"phase": "storage_save"},
            )

            storage_result = await storage_service.retry_manager.execute_with_retry(
                lambda: mock_storage_save(video_id, metadata), save_context
            )

            return {"metadata": metadata, "storage": storage_result}

        start_time = time.time()
        result = await integrated_metadata_storage_workflow()
        execution_time = time.time() - start_time

        # Verify successful integration
        assert result["metadata"]["status"] == "success"
        assert result["metadata"]["title"] == "Fetched Video"
        assert result["storage"]["status"] == "success"

        # Verify retry coordination
        print(f"Metadata fetch retries: {metadata_sim.call_counts['fetch_metadata']}")
        print(f"Storage save retries: {storage_sim.call_counts['save_metadata']}")
        print(f"Integration time: {execution_time:.2f}s")

        assert (
            metadata_sim.call_counts["fetch_metadata"] >= 2
        ), "Metadata should have retried fetch"
        assert (
            storage_sim.call_counts["save_metadata"] >= 3
        ), "Storage should have retried saves"
        assert (
            execution_time < 12.0
        ), f"Integration took too long: {execution_time:.2f}s"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_multi_level_metadata_retry_coordination(
        self,
        metadata_service_with_retry,
        download_service_with_retry,
        jobs_service_with_retry,
    ):
        """Test multi-level retry coordination with jobs orchestrating metadata and download."""
        failure_sim = MetadataFailureSimulator()

        # Setup cascading failure patterns for metadata pipeline
        failure_sim.setup_failure_pattern(
            "metadata_basic_info",
            [False, False, True],  # Basic metadata fails twice
            [ConnectionError("API unavailable")] * 2 + [None],
            [None, None, {"title": "Basic Video Info", "duration": 180}],
        )

        failure_sim.setup_failure_pattern(
            "metadata_detailed_info",
            [False, True],  # Detailed metadata fails once
            [TimeoutError("API timeout")] + [None],
            [None, {"description": "Detailed description", "tags": ["test", "video"]}],
        )

        failure_sim.setup_failure_pattern(
            "download_preparation",
            [True],  # Download prep succeeds immediately
            [None],
            [{"formats": ["720p", "1080p"], "status": "ready"}],
        )

        metadata_service = metadata_service_with_retry
        download_service = download_service_with_retry
        jobs_service = jobs_service_with_retry

        async def mock_basic_metadata(video_id: str):
            return await failure_sim.simulate_metadata_operation(
                "metadata_basic_info", video_id=video_id
            )

        async def mock_detailed_metadata(video_id: str):
            return await failure_sim.simulate_metadata_operation(
                "metadata_detailed_info", video_id=video_id
            )

        async def mock_download_prep(video_id: str):
            return await failure_sim.simulate_metadata_operation(
                "download_preparation", video_id=video_id
            )

        async def orchestrated_metadata_pipeline():
            """Jobs service orchestrating metadata and download preparation with individual retries."""
            video_id = "multi_level_metadata_test"
            results = {}

            # Level 1: Jobs service orchestrates the pipeline
            # Level 2: Individual services handle their own retries

            # Operation 1: Basic metadata (with metadata service retries)
            basic_context = ErrorContext(
                operation_name="orchestrated_basic_metadata",
                video_id=video_id,
                operation_context={"level": "metadata", "type": "basic"},
            )
            results["basic"] = await metadata_service.retry_manager.execute_with_retry(
                lambda: mock_basic_metadata(video_id), basic_context
            )

            # Operation 2: Detailed metadata (with metadata service retries)
            detailed_context = ErrorContext(
                operation_name="orchestrated_detailed_metadata",
                video_id=video_id,
                operation_context={"level": "metadata", "type": "detailed"},
            )
            results[
                "detailed"
            ] = await metadata_service.retry_manager.execute_with_retry(
                lambda: mock_detailed_metadata(video_id), detailed_context
            )

            # Operation 3: Download preparation (with download service retries)
            prep_context = ErrorContext(
                operation_name="orchestrated_download_prep",
                video_id=video_id,
                operation_context={"level": "download", "type": "preparation"},
            )
            results[
                "download_prep"
            ] = await download_service.retry_manager.execute_with_retry(
                lambda: mock_download_prep(video_id), prep_context
            )

            return results

        # Execute orchestrated pipeline with jobs-level retries
        job_context = ErrorContext(
            operation_name="metadata_pipeline_orchestration",
            video_id="multi_level_metadata_test",
            operation_context={"level": "jobs", "pipeline": "metadata"},
        )

        start_time = time.time()
        result = await jobs_service.retry_manager.execute_with_retry(
            orchestrated_metadata_pipeline, job_context
        )
        execution_time = time.time() - start_time

        # Verify successful multi-level coordination
        assert result["basic"]["status"] == "success"
        assert result["basic"]["title"] == "Basic Video Info"
        assert result["detailed"]["status"] == "success"
        assert result["detailed"]["description"] == "Detailed description"
        assert result["download_prep"]["status"] == "success"
        assert result["download_prep"]["formats"] == ["720p", "1080p"]

        # Verify multi-level retry coordination
        print(f"Multi-level metadata retry counts: {failure_sim.call_counts}")
        print(f"Pipeline orchestration time: {execution_time:.2f}s")

        assert (
            failure_sim.call_counts["metadata_basic_info"] >= 3
        ), "Basic metadata should have retried multiple times"
        assert (
            failure_sim.call_counts["metadata_detailed_info"] >= 2
        ), "Detailed metadata should have retried once"
        assert (
            failure_sim.call_counts["download_preparation"] >= 1
        ), "Download prep should have succeeded immediately"
        assert (
            execution_time < 15.0
        ), f"Multi-level coordination took too long: {execution_time:.2f}s"


class TestMetadataServiceAPIErrorRecovery:
    """Test metadata service API error recovery patterns."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_api_quota_exhaustion_recovery(self, metadata_service_with_retry):
        """Test metadata service recovery patterns during API quota exhaustion."""
        failure_sim = MetadataFailureSimulator()

        # Simulate quota exhaustion recovery scenario
        from googleapiclient.errors import HttpError
        import json

        quota_errors = []
        for i in range(4):
            error_content = json.dumps(
                {
                    "error": {
                        "code": 403,
                        "message": "Daily Limit Exceeded" if i < 2 else "quotaExceeded",
                        "errors": [
                            {
                                "reason": "dailyLimitExceeded"
                                if i < 2
                                else "quotaExceeded"
                            }
                        ],
                    }
                }
            ).encode()
            quota_errors.append(
                HttpError(
                    resp=MagicMock(status=403, reason="Forbidden"),
                    content=error_content,
                )
            )

        failure_sim.setup_failure_pattern(
            "api_quota_operation",
            [False, False, False, False, True],  # Quota exhausted 4 times
            quota_errors + [None],
            [
                None,
                None,
                None,
                None,
                {"title": "Quota Recovered Video", "duration": 360},
            ],
        )

        metadata_service = metadata_service_with_retry

        async def mock_quota_sensitive_operation(video_id: str):
            """Mock API operation that might hit quota limits."""
            return await failure_sim.simulate_metadata_operation(
                "api_quota_operation", video_id=video_id
            )

        context = ErrorContext(
            operation_name="api_quota_recovery",
            video_id="quota_test_video",
            operation_context={"issue": "api_quota", "api": "youtube_v3"},
        )

        start_time = time.time()
        result = await metadata_service.retry_manager.execute_with_retry(
            lambda: mock_quota_sensitive_operation("quota_test_video"), context
        )
        execution_time = time.time() - start_time

        # Verify recovery after quota issues
        assert result["status"] == "success"
        assert result["title"] == "Quota Recovered Video"

        print(
            f"API quota recovery attempts: {failure_sim.call_counts['api_quota_operation']}"
        )
        print(f"Recovery time: {execution_time:.2f}s")

        assert (
            failure_sim.call_counts["api_quota_operation"] >= 5
        ), "Should have recovered after quota restored"
        assert (
            execution_time < 20.0
        ), f"API quota recovery took too long: {execution_time:.2f}s"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_network_timeout_retry_patterns(self, metadata_service_with_retry):
        """Test metadata service retry patterns during network timeouts."""
        failure_sim = MetadataFailureSimulator()

        # Simulate network timeout recovery
        failure_sim.setup_failure_pattern(
            "network_operation",
            [False, False, False, True],  # Network issues resolve after 3 attempts
            [
                TimeoutError("Request timeout"),
                ConnectionError("Connection refused"),
                TimeoutError("Read timeout"),
                None,
            ],
            [
                None,
                None,
                None,
                {
                    "title": "Network Recovered Video",
                    "upload_date": "2025-01-29",
                    "views": 500000,
                },
            ],
        )

        metadata_service = metadata_service_with_retry

        async def mock_network_sensitive_operation(video_id: str):
            """Mock operation that might fail due to network issues."""
            return await failure_sim.simulate_metadata_operation(
                "network_operation", video_id=video_id
            )

        context = ErrorContext(
            operation_name="network_timeout_recovery",
            video_id="network_test_video",
            operation_context={"issue": "network", "operation": "metadata_fetch"},
        )

        start_time = time.time()
        result = await metadata_service.retry_manager.execute_with_retry(
            lambda: mock_network_sensitive_operation("network_test_video"), context
        )
        execution_time = time.time() - start_time

        # Verify network error recovery
        assert result["status"] == "success"
        assert result["title"] == "Network Recovered Video"
        assert result["views"] == 500000

        print(
            f"Network recovery attempts: {failure_sim.call_counts['network_operation']}"
        )
        print(f"Recovery time: {execution_time:.2f}s")

        assert (
            failure_sim.call_counts["network_operation"] >= 4
        ), "Should have recovered after network restored"
        assert (
            execution_time < 12.0
        ), f"Network recovery took too long: {execution_time:.2f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
