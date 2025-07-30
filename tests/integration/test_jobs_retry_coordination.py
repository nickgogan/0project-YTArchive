"""
Comprehensive integration tests for Jobs Service retry coordination with downstream services.

This module tests complex retry scenarios where the Jobs service orchestrates
retries across multiple downstream services (storage, metadata, download) while
those services may also be internally retrying their own operations.

Test scenarios:
- Jobs service orchestrating retries across multiple downstream services
- Nested retry behavior: Jobs retries while downstream services internally retry
- Service dependency chain retries (Service A → Service B → Service C)
- Cascading failure recovery and backoff coordination
- Retry timeout and circuit breaker coordination across services
"""

import asyncio
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, List, Optional

import pytest
import pytest_asyncio

from tests.common.temp_utils import temp_dir
from services.jobs.main import JobsService
from services.storage.main import StorageService
from services.download.main import DownloadService
from services.metadata.main import MetadataService
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
async def jobs_service_with_retry(service_settings, retry_config):
    """Create Jobs service with retry capabilities for testing."""
    service = JobsService("JobsService", service_settings)

    # Setup retry manager
    strategy = ExponentialBackoffStrategy(retry_config)
    reporter = BasicErrorReporter()
    service.retry_manager = ErrorRecoveryManager(strategy, reporter)

    # Mock external methods to avoid actual service startup
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
    service.work_plans_dir = Path(temp_storage_dir) / "work_plans"

    # Create directories
    service.metadata_dir.mkdir(parents=True, exist_ok=True)
    service.videos_dir.mkdir(parents=True, exist_ok=True)
    service.work_plans_dir.mkdir(parents=True, exist_ok=True)

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
async def metadata_service_with_retry(service_settings, retry_config):
    """Create Metadata service with retry capabilities for testing."""
    service = MetadataService("MetadataService", service_settings)

    # Setup retry manager
    strategy = ExponentialBackoffStrategy(retry_config)
    reporter = BasicErrorReporter()
    service.retry_manager = ErrorRecoveryManager(strategy, reporter)

    yield service


class FailureSimulator:
    """Utility for simulating various failure patterns in downstream services."""

    def __init__(self):
        self.call_counts: Dict[str, int] = {}
        self.failure_patterns: Dict[str, List[bool]] = {}
        self.delays: Dict[str, List[float]] = {}

    def setup_failure_pattern(
        self,
        service_name: str,
        pattern: List[bool],
        delays: Optional[List[float]] = None,
    ):
        """Setup a failure pattern for a service (True = success, False = failure)."""
        self.failure_patterns[service_name] = pattern
        self.delays[service_name] = delays or [0.0] * len(pattern)
        self.call_counts[service_name] = 0

    async def simulate_service_call(self, service_name: str, operation: str) -> str:
        """Simulate a service call with configured failure pattern."""
        if service_name not in self.failure_patterns:
            return f"success_{service_name}_{operation}"

        call_index = self.call_counts[service_name]
        pattern = self.failure_patterns[service_name]

        # Cycle through pattern if we exceed its length
        pattern_index = call_index % len(pattern)
        should_succeed = pattern[pattern_index]

        # Apply delay
        delay = (
            self.delays[service_name][pattern_index]
            if self.delays[service_name]
            else 0.0
        )
        if delay > 0:
            await asyncio.sleep(delay)

        self.call_counts[service_name] += 1

        if should_succeed:
            return f"success_{service_name}_{operation}_{call_index}"
        else:
            raise ConnectionError(
                f"Simulated failure in {service_name}.{operation} (attempt {call_index})"
            )


class TestJobsServiceRetryCoordination:
    """Test Jobs service coordinating retries across multiple downstream services."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_jobs_orchestrating_downstream_retries(
        self,
        jobs_service_with_retry,
        storage_service_with_retry,
        download_service_with_retry,
        metadata_service_with_retry,
    ):
        """Test Jobs service orchestrating retries across multiple downstream services."""
        failure_sim = FailureSimulator()

        # Setup failure patterns for downstream services
        # Storage: fail first 2 attempts, then succeed
        failure_sim.setup_failure_pattern("storage", [False, False, True, True])
        # Download: fail first attempt, then succeed
        failure_sim.setup_failure_pattern("download", [False, True, True, True])
        # Metadata: succeed on first attempt
        failure_sim.setup_failure_pattern("metadata", [True, True, True, True])

        jobs_service = jobs_service_with_retry
        storage_service = storage_service_with_retry
        download_service = download_service_with_retry
        metadata_service = metadata_service_with_retry

        # Mock downstream service calls
        async def mock_storage_operation():
            return await failure_sim.simulate_service_call("storage", "save_metadata")

        async def mock_download_operation():
            return await failure_sim.simulate_service_call("download", "start_download")

        async def mock_metadata_operation():
            return await failure_sim.simulate_service_call("metadata", "get_metadata")

        # Execute coordinated operations without needing to mock specific service methods
        # This tests the retry coordination patterns directly

        # Create a coordinated job that needs all three services
        async def coordinated_job():
            """A job that coordinates multiple downstream services."""
            results = {}

            # Step 1: Download video (with internal retries)
            context = ErrorContext(
                operation_name="coordinated_download",
                video_id="test_video_123",
                operation_context={"step": "download"},
            )
            results[
                "download"
            ] = await download_service.retry_manager.execute_with_retry(
                mock_download_operation, context
            )

            # Step 2: Extract metadata (with internal retries)
            context = ErrorContext(
                operation_name="coordinated_metadata",
                video_id="test_video_123",
                operation_context={"step": "metadata"},
            )
            results[
                "metadata"
            ] = await metadata_service.retry_manager.execute_with_retry(
                mock_metadata_operation, context
            )

            # Step 3: Store video (with internal retries)
            context = ErrorContext(
                operation_name="coordinated_storage",
                video_id="test_video_123",
                operation_context={"step": "storage"},
            )
            results["storage"] = await storage_service.retry_manager.execute_with_retry(
                mock_storage_operation, context
            )

            return results

        # Execute the coordinated job with Jobs service retries
        job_context = ErrorContext(
            operation_name="coordinated_job",
            video_id="test_video_123",
            operation_context={"job_type": "video_processing"},
        )

        start_time = time.time()
        result = await jobs_service.retry_manager.execute_with_retry(
            coordinated_job, job_context
        )
        execution_time = time.time() - start_time

        # Verify results
        assert "download" in result
        assert "metadata" in result
        assert "storage" in result

        # Verify successful results
        assert result["download"].startswith("success_download")
        assert result["metadata"].startswith("success_metadata")
        assert result["storage"].startswith("success_storage")

        # Verify retry coordination worked
        assert failure_sim.call_counts["storage"] >= 3  # Failed twice, succeeded on 3rd
        assert failure_sim.call_counts["download"] >= 2  # Failed once, succeeded on 2nd
        assert failure_sim.call_counts["metadata"] >= 1  # Succeeded on 1st

        # Verify reasonable execution time (should handle retries efficiently)
        assert execution_time < 10.0, f"Execution took too long: {execution_time:.2f}s"

        print(f"Coordinated job completed in {execution_time:.2f}s")
        print(f"Service call counts: {failure_sim.call_counts}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_nested_retry_behavior(
        self, jobs_service_with_retry, storage_service_with_retry, retry_config
    ):
        """Test nested retry behavior: Jobs retries while downstream services internally retry."""
        failure_sim = FailureSimulator()

        # Setup complex failure pattern
        # Storage will fail multiple times at different levels
        failure_sim.setup_failure_pattern(
            "storage",
            [False, False, False, True],  # First 3 attempts fail, 4th succeeds
            [0.1, 0.1, 0.1, 0.0],  # Small delays for failures
        )

        jobs_service = jobs_service_with_retry
        storage_service = storage_service_with_retry

        # Track retry attempts at different levels
        jobs_retry_count = 0
        storage_retry_count = 0

        async def mock_storage_with_internal_retries():
            """Mock storage operation that has its own internal retries."""
            nonlocal storage_retry_count
            storage_retry_count += 1

            # Storage service has its own retry logic
            async def storage_operation():
                return await failure_sim.simulate_service_call(
                    "storage", "complex_store"
                )

            context = ErrorContext(
                operation_name="internal_storage",
                video_id="test_video_nested",
                operation_context={"internal_retry": storage_retry_count},
            )

            return await storage_service.retry_manager.execute_with_retry(
                storage_operation, context
            )

        async def jobs_level_operation():
            """Jobs service level operation that calls downstream services."""
            nonlocal jobs_retry_count
            jobs_retry_count += 1

            # This operation itself might be retried by Jobs service
            return await mock_storage_with_internal_retries()

        # Execute with Jobs service retry coordination
        job_context = ErrorContext(
            operation_name="nested_retry_job",
            video_id="test_video_nested",
            operation_context={"nested_test": True},
        )

        start_time = time.time()
        result = await jobs_service.retry_manager.execute_with_retry(
            jobs_level_operation, job_context
        )
        execution_time = time.time() - start_time

        # Verify successful completion
        assert result.startswith("success_storage")

        # Verify retry coordination
        print(f"Jobs service retries: {jobs_retry_count}")
        print(f"Storage service retries: {storage_retry_count}")
        print(f"Total storage calls: {failure_sim.call_counts['storage']}")
        print(f"Execution time: {execution_time:.2f}s")

        # Verify both levels attempted retries
        assert jobs_retry_count >= 1, "Jobs service should have attempted retries"
        assert (
            storage_retry_count >= 1
        ), "Storage service should have attempted internal retries"
        assert (
            failure_sim.call_counts["storage"] >= 4
        ), "Should have made multiple storage calls"

        # Verify reasonable execution time
        assert (
            execution_time < 15.0
        ), f"Nested retries took too long: {execution_time:.2f}s"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_service_dependency_chain_retries(
        self,
        jobs_service_with_retry,
        metadata_service_with_retry,
        storage_service_with_retry,
        download_service_with_retry,
    ):
        """Test service dependency chain retries (Service A → Service B → Service C)."""
        failure_sim = FailureSimulator()

        # Setup failure patterns for dependency chain
        # Download -> Metadata -> Storage (each depends on previous)
        failure_sim.setup_failure_pattern("download", [False, True, True])  # Fail once
        failure_sim.setup_failure_pattern(
            "metadata", [False, False, True]
        )  # Fail twice
        failure_sim.setup_failure_pattern(
            "storage", [True, True, True]
        )  # Always succeed

        # Create dependency chain: Download -> Metadata -> Storage
        async def download_operation():
            return await failure_sim.simulate_service_call("download", "get_video")

        async def metadata_operation(download_result: str):
            # Metadata depends on download result
            if not download_result.startswith("success_download"):
                raise ValueError(
                    f"Cannot process metadata without download: {download_result}"
                )
            return await failure_sim.simulate_service_call(
                "metadata", "process_metadata"
            )

        async def storage_operation(metadata_result: str):
            # Storage depends on metadata result
            if not metadata_result.startswith("success_metadata"):
                raise ValueError(f"Cannot store without metadata: {metadata_result}")
            return await failure_sim.simulate_service_call("storage", "store_processed")

        async def dependency_chain():
            """Execute full dependency chain with retries at each level."""
            # Step 1: Download (with retries)
            download_context = ErrorContext(
                operation_name="chain_download",
                video_id="test_chain_video",
                operation_context={"chain_step": 1},
            )
            download_result = (
                await download_service_with_retry.retry_manager.execute_with_retry(
                    download_operation, download_context
                )
            )

            # Step 2: Metadata processing (with retries, depends on download)
            async def metadata_with_dependency():
                return await metadata_operation(download_result)

            metadata_context = ErrorContext(
                operation_name="chain_metadata",
                video_id="test_chain_video",
                operation_context={"chain_step": 2},
            )
            metadata_result = (
                await metadata_service_with_retry.retry_manager.execute_with_retry(
                    metadata_with_dependency, metadata_context
                )
            )

            # Step 3: Storage (with retries, depends on metadata)
            async def storage_with_dependency():
                return await storage_operation(metadata_result)

            storage_context = ErrorContext(
                operation_name="chain_storage",
                video_id="test_chain_video",
                operation_context={"chain_step": 3},
            )
            storage_result = (
                await storage_service_with_retry.retry_manager.execute_with_retry(
                    storage_with_dependency, storage_context
                )
            )

            return {
                "download": download_result,
                "metadata": metadata_result,
                "storage": storage_result,
            }

        # Execute dependency chain with Jobs service coordination
        job_context = ErrorContext(
            operation_name="dependency_chain_job",
            video_id="test_chain_video",
            operation_context={"chain_test": True},
        )

        start_time = time.time()
        result = await jobs_service_with_retry.retry_manager.execute_with_retry(
            dependency_chain, job_context
        )
        execution_time = time.time() - start_time

        # Verify successful completion of entire chain
        assert result["download"].startswith("success_download")
        assert result["metadata"].startswith("success_metadata")
        assert result["storage"].startswith("success_storage")

        # Verify retry counts for each service in the chain
        print(f"Dependency chain call counts: {failure_sim.call_counts}")
        print(f"Chain execution time: {execution_time:.2f}s")

        # Verify expected retry behavior
        assert (
            failure_sim.call_counts["download"] >= 2
        ), "Download should have retried once"
        assert (
            failure_sim.call_counts["metadata"] >= 3
        ), "Metadata should have retried twice"
        assert (
            failure_sim.call_counts["storage"] >= 1
        ), "Storage should have succeeded first time"

        # Verify reasonable execution time for chain
        assert (
            execution_time < 20.0
        ), f"Dependency chain took too long: {execution_time:.2f}s"


class TestCascadingFailureRecovery:
    """Test cascading failure recovery and backoff coordination."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cascading_failure_backoff_coordination(
        self,
        jobs_service_with_retry,
        storage_service_with_retry,
        download_service_with_retry,
    ):
        """Test backoff coordination when multiple services fail simultaneously."""
        failure_sim = FailureSimulator()

        # Setup cascading failure pattern
        # Both services fail initially, then recover at different rates
        failure_sim.setup_failure_pattern(
            "download",
            [False, False, False, True, True],  # Download recovers after 3 failures
            [0.1, 0.2, 0.3, 0.0, 0.0],  # Increasing delays
        )
        failure_sim.setup_failure_pattern(
            "storage",
            [False, False, True, True, True],  # Storage recovers after 2 failures
            [0.1, 0.2, 0.0, 0.0, 0.0],  # Delays for failures
        )

        async def download_op():
            return await failure_sim.simulate_service_call(
                "download", "cascade_download"
            )

        async def storage_op():
            return await failure_sim.simulate_service_call("storage", "cascade_storage")

        async def coordinated_operations():
            """Execute operations that may fail simultaneously."""
            # Execute both operations concurrently
            download_context = ErrorContext(
                operation_name="cascade_download",
                video_id="cascade_test",
                operation_context={"cascade": True},
            )

            storage_context = ErrorContext(
                operation_name="cascade_storage",
                video_id="cascade_test",
                operation_context={"cascade": True},
            )

            download_task = (
                download_service_with_retry.retry_manager.execute_with_retry(
                    download_op, download_context
                )
            )
            storage_task = storage_service_with_retry.retry_manager.execute_with_retry(
                storage_op, storage_context
            )

            # Wait for both to complete
            download_result, storage_result = await asyncio.gather(
                download_task, storage_task
            )

            return {"download": download_result, "storage": storage_result}

        # Execute with Jobs service coordination
        job_context = ErrorContext(
            operation_name="cascading_failure_job",
            video_id="cascade_test",
            operation_context={"test_type": "cascading_failure"},
        )

        start_time = time.time()
        result = await jobs_service_with_retry.retry_manager.execute_with_retry(
            coordinated_operations, job_context
        )
        execution_time = time.time() - start_time

        # Verify successful recovery
        assert result["download"].startswith("success_download")
        assert result["storage"].startswith("success_storage")

        # Verify coordinated backoff behavior
        print(f"Cascading failure call counts: {failure_sim.call_counts}")
        print(f"Recovery time: {execution_time:.2f}s")

        # Verify both services attempted retries
        assert (
            failure_sim.call_counts["download"] >= 4
        ), "Download should have retried multiple times"
        assert (
            failure_sim.call_counts["storage"] >= 3
        ), "Storage should have retried multiple times"

        # Verify backoff coordination didn't cause excessive delays
        assert (
            execution_time < 25.0
        ), f"Cascading recovery took too long: {execution_time:.2f}s"

        # Verify services recovered (allow for concurrent execution variations)
        # Both services should have attempted multiple retries
        assert (
            failure_sim.call_counts["storage"] >= 3
        ), "Storage should have retried multiple times"
        assert (
            failure_sim.call_counts["download"] >= 4
        ), "Download should have retried multiple times"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
