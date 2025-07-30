"""Integration tests for error recovery system with real services."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import pytest
import httpx

from services.download.main import (
    DownloadService,
    DownloadRequest,
    DownloadStatus,
    DownloadTask,
)
from services.error_recovery import ErrorRecoveryManager
from services.error_recovery.retry import (
    ExponentialBackoffStrategy,
    CircuitBreakerStrategy,
)
from services.error_recovery.reporting import BasicErrorReporter
from services.error_recovery.types import (
    RetryConfig,
    ErrorContext,
)
from services.common.base import ServiceSettings


class TestDownloadServiceIntegration:
    """Integration tests for download service with error recovery."""

    @pytest.fixture
    async def download_service(self, tmp_path):
        """Create a download service instance for testing."""
        settings = ServiceSettings(port=8002, host="localhost", debug=True)
        service = DownloadService("TestDownloadService", settings)

        # Use temporary path for downloads
        service.download_root = tmp_path

        yield service

        # Cleanup any pending tasks
        await service.cleanup_pending_tasks()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_download_with_network_retry(self, download_service):
        """Test download service handles network errors with retry logic."""

        # Mock yt-dlp to simulate network failures then success
        call_count = 0

        def mock_ytdlp_download(url, opts):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # Simulate network errors on first 2 attempts
                raise Exception("HTTP Error 503: Service Temporarily Unavailable")
            # Success on 3rd attempt
            return {
                "id": "test_video_123",
                "title": "Test Video",
                "duration": 300,
                "formats": [{"format_id": "22", "ext": "mp4", "height": 720}],
            }

        with patch.object(
            download_service, "_run_ytdlp", side_effect=mock_ytdlp_download
        ):
            # Start download request
            request = DownloadRequest(
                video_id="test_video_123",
                quality="720p",
                output_path=str(download_service.download_root),
            )

            # Mock storage service to avoid HTTP calls
            with patch.object(
                download_service,
                "_get_storage_path",
                return_value=str(download_service.download_root),
            ):
                # Execute download with retry
                task = await download_service._create_download_task(request)

                # Process download - should succeed after retries
                await download_service._process_download(task)

                # Verify retry happened and succeeded
                assert call_count == 3  # Failed twice, succeeded on 3rd
                assert task.status == DownloadStatus.COMPLETED
                assert task.error is None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_download_error_handler_integration(self, download_service):
        """Test download error handler integrates properly with retry system."""

        error_handler = download_service.download_error_handler
        context = ErrorContext(
            operation_name="test_download", video_id="test_video_456"
        )

        # Test network error handling
        network_error = Exception("Connection timeout after 30 seconds")
        handled = await error_handler.handle_error(network_error, context)
        assert handled is True  # Should be handled and allow retry

        # Test YouTube-specific error (should not retry)
        youtube_error = Exception("Video unavailable: This video is private")
        handled = await error_handler.handle_error(youtube_error, context)
        assert handled is False  # Should not be retried

        # Test filesystem error (should retry)
        fs_error = Exception("Permission denied: cannot write to directory")
        handled = await error_handler.handle_error(fs_error, context)
        assert handled is True  # Should be handled and allow retry

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_circuit_breaker_with_download_service(self, download_service):
        """Test circuit breaker behavior with repeated download failures."""

        # Replace retry strategy with circuit breaker
        circuit_breaker_config = RetryConfig(
            max_attempts=5,
            failure_threshold=3,  # Open circuit after 3 failures
            recovery_timeout=0.1,  # Short timeout for testing
            base_delay=0.01,
        )

        circuit_breaker_strategy = CircuitBreakerStrategy(circuit_breaker_config)
        download_service.error_recovery.retry_strategy = circuit_breaker_strategy

        # Mock download method to always fail - test circuit breaker directly
        async def mock_download_failure(task):
            raise Exception("HTTP Error 500: Internal Server Error")

        # Mock successful methods to avoid interference with circuit breaker
        with patch.object(
            download_service, "_download_video", side_effect=mock_download_failure
        ):
            with patch.object(
                download_service,
                "_get_storage_path",
                return_value=str(download_service.download_root),
            ):
                with patch.object(
                    download_service, "_report_job_status", new_callable=AsyncMock
                ):
                    # Make multiple direct calls to the error recovery system for download_video
                    results = []
                    for i in range(6):
                        context = ErrorContext(
                            operation_name="download_video",
                            video_id=f"test_video_{i}",
                            operation_context={
                                "task_id": f"task_{i}",
                                "quality": "720p",
                            },
                        )

                        # Create a dummy task for the failing method
                        task = DownloadTask(
                            task_id=f"task_{i}",
                            video_id=f"test_video_{i}",
                            quality="720p",
                            output_path=str(download_service.download_root),
                            status=DownloadStatus.PENDING,
                            created_at=datetime.now(timezone.utc),
                        )

                        try:
                            await download_service.error_recovery.execute_with_retry(
                                download_service._download_video, context, None, task
                            )
                            results.append("success")
                        except Exception:
                            results.append("failure")

                    # Verify circuit breaker behavior
                    assert circuit_breaker_strategy.state == "open"
                    assert circuit_breaker_strategy.failed_attempts >= 3
                    assert len([r for r in results if r == "failure"]) >= 3

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_downloads_with_error_recovery(self, download_service):
        """Test multiple concurrent downloads with error recovery."""

        # Mock _download_video with mixed success/failure behavior
        call_counts = {}

        async def mock_download_video(task: DownloadTask):
            video_id = task.video_id
            call_counts[video_id] = call_counts.get(video_id, 0) + 1

            # Video 1: succeeds immediately
            if video_id == "video_1":
                task.status = DownloadStatus.COMPLETED
                return

            # Video 2: fails twice then succeeds
            elif video_id == "video_2":
                if call_counts[video_id] <= 2:
                    raise Exception("Temporary network error")
                task.status = DownloadStatus.COMPLETED
                return

            # Video 3: always fails
            elif video_id == "video_3":
                raise Exception("Video unavailable: Private video")

            # Video 4: succeeds after 1 failure
            elif video_id == "video_4":
                if call_counts[video_id] == 1:
                    raise Exception("Connection reset by peer")
                task.status = DownloadStatus.COMPLETED
                return

        with patch.object(
            download_service, "_download_video", side_effect=mock_download_video
        ):
            with patch.object(
                download_service,
                "_get_storage_path",
                return_value=str(download_service.download_root),
            ):
                # Create concurrent download tasks
                requests = [
                    DownloadRequest(
                        video_id="video_1",
                        quality="720p",
                        output_path=str(download_service.download_root),
                    ),
                    DownloadRequest(
                        video_id="video_2",
                        quality="720p",
                        output_path=str(download_service.download_root),
                    ),
                    DownloadRequest(
                        video_id="video_3",
                        quality="720p",
                        output_path=str(download_service.download_root),
                    ),
                    DownloadRequest(
                        video_id="video_4",
                        quality="720p",
                        output_path=str(download_service.download_root),
                    ),
                ]

                tasks = [
                    await download_service._create_download_task(req)
                    for req in requests
                ]

                # Process all downloads concurrently
                await asyncio.gather(
                    *[download_service._process_download(task) for task in tasks],
                    return_exceptions=True,
                )

                # Verify expected outcomes
                assert (
                    tasks[0].status == DownloadStatus.COMPLETED
                )  # video_1: immediate success
                assert (
                    tasks[1].status == DownloadStatus.COMPLETED
                )  # video_2: success after retries
                assert (
                    tasks[2].status == DownloadStatus.FAILED
                )  # video_3: permanent failure
                assert (
                    tasks[3].status == DownloadStatus.COMPLETED
                )  # video_4: success after 1 retry

                # Verify retry counts
                assert call_counts["video_1"] == 1  # No retries needed
                assert call_counts["video_2"] == 3  # 2 failures + 1 success
                assert call_counts["video_4"] == 2  # 1 failure + 1 success

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_reporting_integration(self, download_service, tmp_path):
        """Test error reporting integration with download service."""

        # Use temporary directory for error reports
        download_service.error_reporter.reports_dir = str(tmp_path)

        # Mock _download_video to fail permanently
        async def mock_download_failure(task: DownloadTask):
            raise Exception("Critical download error: Disk full")

        with patch.object(
            download_service, "_download_video", side_effect=mock_download_failure
        ):
            with patch.object(
                download_service,
                "_get_storage_path",
                return_value=str(download_service.download_root),
            ):
                request = DownloadRequest(
                    video_id="test_error_video",
                    quality="720p",
                    output_path=str(download_service.download_root),
                )

                task = await download_service._create_download_task(request)

                # Process download - should fail and create error report
                await download_service._process_download(task)

                # Verify error was reported
                assert task.status == DownloadStatus.FAILED
                assert "Disk full" in task.error

                # Check error reports were created
                error_summary = (
                    await download_service.error_reporter.get_error_summary()
                )
                assert error_summary["total_errors"] > 0
                recent_errors = error_summary["recent_errors"]
                assert len(recent_errors) > 0
                assert any("Disk full" in error["title"] for error in recent_errors)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_storage_service_communication_retry(
        self, download_service, tmp_path
    ):
        """Test that communication with the Storage service is retried on failure."""
        storage_call_count = 0

        async def mock_get_storage_path(*args, **kwargs):
            nonlocal storage_call_count
            storage_call_count += 1
            if storage_call_count <= 2:  # Fail twice
                raise httpx.TimeoutException("Storage service timeout")
            return str(tmp_path)

        with patch.object(
            download_service, "_get_storage_path", side_effect=mock_get_storage_path
        ):
            request = DownloadRequest(
                video_id="test_video_storage_retry",
                quality="720p",
                output_path=str(tmp_path),
            )
            # This simulates the start of the download process, which calls the wrapped _get_storage_path
            task = await download_service._create_download_task(request)

            assert storage_call_count == 3  # 2 failures + 1 success
            assert task.output_path.startswith(str(tmp_path))

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_jobs_service_communication_retry(self, download_service):
        """Test that communication with the Jobs service is retried on failure."""
        jobs_call_count = 0

        async def mock_report_job_status(*args, **kwargs):
            nonlocal jobs_call_count
            jobs_call_count += 1
            if jobs_call_count <= 2:  # Fail twice
                raise httpx.ConnectError("Jobs service unavailable")
            return

        # We need a real task object to pass to _process_download
        request = DownloadRequest(
            video_id="test_video_jobs_retry",
            quality="720p",
            job_id="job_123",
            output_path="/tmp/fake_path",
        )

        # Since _create_download_task calls _get_storage_path, we mock it here
        with patch.object(
            download_service, "_get_storage_path", return_value="/tmp/fake_path"
        ):
            task = await download_service._create_download_task(request)

        # Now, mock the other methods for the _process_download call
        with patch.object(download_service, "_download_video", new_callable=AsyncMock):
            with patch.object(
                download_service,
                "_report_job_status",
                side_effect=mock_report_job_status,
            ):
                await download_service._process_download(task)

        # It's called for 'downloading' and 'completed', so 2 failures + 1 success for each = 6 calls
        # Let's check for at least one retry on the first call.
        assert jobs_call_count >= 3


# ... (rest of the code remains the same)


class TestPerformanceIntegration:
    """Performance-focused integration tests."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_high_load_error_recovery_performance(self):
        """Test error recovery system performance under high load."""

        config = RetryConfig(max_attempts=3, base_delay=0.001, max_delay=0.01)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        # Simulate high-load scenario with mixed success/failure
        async def simulate_operation(operation_id: int):
            context = ErrorContext(operation_name=f"load_test_op_{operation_id}")

            # Mock function with failure pattern
            call_count = 0

            async def mock_operation():
                nonlocal call_count
                call_count += 1

                # 30% immediate success, 50% succeed after 1-2 retries, 20% permanent failure
                if operation_id % 10 < 3:
                    return f"immediate_success_{operation_id}"
                elif operation_id % 10 < 8:
                    if call_count <= (operation_id % 3) + 1:
                        raise Exception(f"Temporary error for op {operation_id}")
                    return f"retry_success_{operation_id}"
                else:
                    raise Exception(f"Permanent failure for op {operation_id}")

            try:
                result = await manager.execute_with_retry(mock_operation, context)
                return ("success", result)
            except Exception as e:
                return ("failure", str(e))

        # Run 100 concurrent operations
        import time

        start_time = time.time()

        tasks = [simulate_operation(i) for i in range(100)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        total_time = end_time - start_time

        # Analyze results
        successes = sum(
            1 for r in results if isinstance(r, tuple) and r[0] == "success"
        )
        failures = sum(1 for r in results if isinstance(r, tuple) and r[0] == "failure")
        exceptions = sum(1 for r in results if isinstance(r, Exception))

        # Performance assertions
        assert total_time < 5.0  # Should complete within 5 seconds
        assert (
            successes >= 60
        )  # At least 60% success rate expected, allowing for randomness
        assert (
            failures + exceptions <= 40
        )  # At most 40% failure rate, allowing for randomness

        # Verify cleanup - no memory leaks
        assert len(manager.get_active_recoveries()) == 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_memory_usage_during_long_retry_sequences(self):
        """Test memory usage during extended retry sequences."""

        config = RetryConfig(max_attempts=10, base_delay=0.001, max_delay=0.1)
        strategy = ExponentialBackoffStrategy(config)
        reporter = BasicErrorReporter()
        manager = ErrorRecoveryManager(strategy, reporter)

        context = ErrorContext(operation_name="memory_stress_test")

        # Track memory usage (simplified)
        initial_active_recoveries = len(manager.get_active_recoveries())
        max_active_recoveries = 0

        async def long_retry_operation():
            nonlocal max_active_recoveries

            # Monitor active recoveries during execution
            current_active = len(manager.get_active_recoveries())
            max_active_recoveries = max(max_active_recoveries, current_active)

            # Always fail to force maximum retries
            raise Exception("Persistent error for memory test")

        # Run operation that will exhaust all retries
        try:
            await manager.execute_with_retry(long_retry_operation, context)
        except Exception:
            pass  # Expected failure

        # Verify memory cleanup after completion
        final_active_recoveries = len(manager.get_active_recoveries())

        assert final_active_recoveries == initial_active_recoveries  # Back to baseline
        assert max_active_recoveries <= 1  # Should only track 1 operation at a time


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
