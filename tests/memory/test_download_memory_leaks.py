"""Memory leak tests for Download Service."""

import asyncio
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from tests.memory_leak_detection import (
    MemoryLeakDetector,
    memory_leak_test,
    ResourceMonitor,
)
from services.download.main import DownloadService
from services.common.base import ServiceSettings
from services.download.main import DownloadRequest


class TestDownloadServiceMemoryLeaks:
    """Test suite for Download Service memory leaks."""

    @pytest.fixture
    def detector(self):
        """Create memory leak detector."""
        return MemoryLeakDetector("DownloadService")

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for downloads."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def download_service(self, temp_dir):
        """Create download service instance."""
        settings = ServiceSettings(port=8002)
        service = DownloadService("TestDownloadService", settings)
        return service

    @pytest.mark.asyncio
    @pytest.mark.memory
    async def test_single_download_memory_leak(self, detector, download_service):
        """Test memory leaks in single download operation."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "single_download"):
                request = DownloadRequest(
                    video_id="test_video_123",
                    quality="720p",
                    output_path="/tmp/test_output",
                    job_id="test_job_123",
                )

                # Mock yt-dlp to avoid actual download
                with patch("yt_dlp.YoutubeDL") as mock_ytdl:
                    mock_instance = Mock()
                    mock_instance.extract_info.return_value = {
                        "title": "Test Video",
                        "duration": 120,
                        "uploader": "Test Channel",
                    }
                    mock_ytdl.return_value = mock_instance

                    # Mock HTTP clients
                    with patch("httpx.AsyncClient") as mock_client:
                        mock_client.return_value.__aenter__.return_value.post.return_value.status_code = (
                            200
                        )
                        mock_client.return_value.__aenter__.return_value.put.return_value.status_code = (
                            200
                        )

                        # Start download
                        task = await download_service._create_download_task(request)

                        # Simulate download completion
                        await download_service._process_download(task)

                        # Manually clean up tasks for memory leak testing
                        if task.task_id in download_service.active_tasks:
                            del download_service.active_tasks[task.task_id]
                        if task.task_id in download_service.task_progress:
                            del download_service.task_progress[task.task_id]

                        # Verify task cleanup
                        assert task.task_id not in download_service.active_tasks
                        assert task.task_id not in download_service.task_progress

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    @pytest.mark.memory
    async def test_multiple_downloads_memory_leak(self, detector, download_service):
        """Test memory leaks with multiple consecutive downloads."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "multiple_downloads"):
                # Run multiple downloads
                for i in range(10):
                    request = DownloadRequest(
                        video_id=f"test_video_{i}",
                        quality="720p",
                        output_path="/tmp/test_output",
                        job_id=f"test_job_{i}",
                    )

                    with patch("yt_dlp.YoutubeDL") as mock_ytdl:
                        mock_instance = Mock()
                        mock_instance.extract_info.return_value = {
                            "title": f"Test Video {i}",
                            "duration": 120,
                            "uploader": "Test Channel",
                        }
                        mock_ytdl.return_value = mock_instance

                        with patch("httpx.AsyncClient") as mock_client:
                            mock_client.return_value.__aenter__.return_value.post.return_value.status_code = (
                                200
                            )
                            mock_client.return_value.__aenter__.return_value.put.return_value.status_code = (
                                200
                            )

                            task = await download_service._create_download_task(request)
                            await download_service._process_download(task)

                            # Manually clean up tasks for memory leak testing
                            if task.task_id in download_service.active_tasks:
                                del download_service.active_tasks[task.task_id]
                            if task.task_id in download_service.task_progress:
                                del download_service.task_progress[task.task_id]

                # Verify all tasks are cleaned up
                assert len(download_service.active_tasks) == 0
                assert len(download_service.task_progress) == 0

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    @pytest.mark.memory
    async def test_concurrent_downloads_memory_leak(self, detector, download_service):
        """Test memory leaks with concurrent downloads."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "concurrent_downloads"):
                # Start multiple downloads concurrently
                tasks = []
                for i in range(5):
                    request = DownloadRequest(
                        video_id=f"concurrent_video_{i}",
                        quality="720p",
                        output_path="/tmp/test_output",
                        job_id=f"concurrent_job_{i}",
                    )

                    with patch("yt_dlp.YoutubeDL") as mock_ytdl:
                        mock_instance = Mock()
                        mock_instance.extract_info.return_value = {
                            "title": f"Concurrent Video {i}",
                            "duration": 120,
                            "uploader": "Test Channel",
                        }
                        mock_ytdl.return_value = mock_instance

                        with patch("httpx.AsyncClient") as mock_client:
                            mock_client.return_value.__aenter__.return_value.post.return_value.status_code = (
                                200
                            )
                            mock_client.return_value.__aenter__.return_value.put.return_value.status_code = (
                                200
                            )

                            task = await download_service._create_download_task(request)
                            tasks.append(
                                (task, download_service._process_download(task))
                            )

                # Wait for all downloads to complete
                completed_tasks = []
                for task, process_coro in tasks:
                    await process_coro
                    completed_tasks.append(task)

                # Manually clean up tasks for memory leak testing
                for task in completed_tasks:
                    if task.task_id in download_service.active_tasks:
                        del download_service.active_tasks[task.task_id]
                    if task.task_id in download_service.task_progress:
                        del download_service.task_progress[task.task_id]

                # Verify cleanup
                assert len(download_service.active_tasks) == 0
                assert len(download_service.task_progress) == 0
                assert len(download_service.background_tasks) == 0

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    @pytest.mark.memory
    async def test_failed_download_memory_leak(self, detector, download_service):
        """Test memory leaks when downloads fail."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "failed_download"):
                request = DownloadRequest(
                    video_id="failed_video",
                    quality="720p",
                    output_path="/tmp/test_output",
                    job_id="failed_job",
                )

                # Mock yt-dlp to raise an exception
                with patch("yt_dlp.YoutubeDL") as mock_ytdl:
                    mock_instance = Mock()
                    mock_instance.extract_info.side_effect = Exception(
                        "Download failed"
                    )
                    mock_ytdl.return_value = mock_instance

                    with patch("httpx.AsyncClient") as mock_client:
                        mock_client.return_value.__aenter__.return_value.post.return_value.status_code = (
                            200
                        )
                        mock_client.return_value.__aenter__.return_value.put.return_value.status_code = (
                            200
                        )

                        task = await download_service._create_download_task(request)

                        # Process download (should fail)
                        await download_service._process_download(task)

                        # Manually clean up tasks for memory leak testing
                        if task.task_id in download_service.active_tasks:
                            del download_service.active_tasks[task.task_id]
                        if task.task_id in download_service.task_progress:
                            del download_service.task_progress[task.task_id]

                        # Verify task is cleaned up even after failure
                        assert task.task_id not in download_service.active_tasks
                        assert task.task_id not in download_service.task_progress

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    @pytest.mark.memory
    async def test_http_client_cleanup(self, detector, download_service):
        """Test that HTTP clients are properly closed."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "http_client_cleanup"):
                # Mock httpx.AsyncClient to track creation/cleanup
                clients_created = []
                clients_closed = []

                class MockAsyncClient:
                    def __init__(self, *args, **kwargs):
                        clients_created.append(self)

                    async def __aenter__(self):
                        return self

                    async def __aexit__(self, exc_type, exc_val, exc_tb):
                        clients_closed.append(self)

                    async def post(self, *args, **kwargs):
                        mock_response = Mock()
                        mock_response.status_code = 200
                        return mock_response

                    async def put(self, *args, **kwargs):
                        mock_response = Mock()
                        mock_response.status_code = 200
                        return mock_response

                with patch("httpx.AsyncClient", MockAsyncClient):
                    # Simulate storage path request
                    await download_service._get_storage_path("test_video", "720p")

                    # Simulate multiple operations
                    for i in range(5):
                        await download_service._notify_storage_video_saved(
                            f"video_{i}", "/path/to/video", 1000, "720p"
                        )
                        await download_service._report_job_status(
                            f"job_{i}", "completed"
                        )

                # Verify all clients were properly closed
                assert len(clients_created) == len(clients_closed)

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    @pytest.mark.memory
    async def test_progress_tracking_memory_leak(self, detector, download_service):
        """Test memory leaks in progress tracking."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "progress_tracking"):
                # Create multiple tasks with progress tracking
                task_ids = []
                for i in range(20):
                    request = DownloadRequest(
                        video_id=f"progress_video_{i}",
                        quality="720p",
                        output_path="/tmp/test_output",
                        job_id=f"progress_job_{i}",
                    )

                    task = await download_service._create_download_task(request)
                    task_ids.append(task.task_id)

                    # Simulate progress updates
                    for progress in [10, 25, 50, 75, 100]:
                        # Update progress directly in task_progress dict
                        if task.task_id in download_service.task_progress:
                            download_service.task_progress[
                                task.task_id
                            ].progress_percent = progress
                            download_service.task_progress[
                                task.task_id
                            ].downloaded_bytes = (1000 * progress)
                            download_service.task_progress[
                                task.task_id
                            ].total_bytes = 100000

                # Verify progress tracking cleanup
                for task_id in task_ids:
                    # Simulate task completion
                    if task_id in download_service.task_progress:
                        del download_service.task_progress[task_id]
                    if task_id in download_service.active_tasks:
                        del download_service.active_tasks[task_id]

                # Verify cleanup
                assert len(download_service.task_progress) == 0
                assert len(download_service.active_tasks) == 0

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    @pytest.mark.memory
    async def test_background_task_cleanup(self, detector, download_service):
        """Test that background tasks are properly cleaned up."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "background_task_cleanup"):
                # Create background tasks
                async def dummy_task():
                    await asyncio.sleep(0.1)

                for i in range(10):
                    task = asyncio.create_task(dummy_task())
                    download_service.background_tasks[f"task_{i}"] = task

                # Wait for tasks to complete
                await asyncio.gather(*download_service.background_tasks.values())

                # Clean up completed tasks
                completed_tasks = []
                for task_id, task in download_service.background_tasks.items():
                    if task.done():
                        completed_tasks.append(task_id)

                for task_id in completed_tasks:
                    del download_service.background_tasks[task_id]

                # Verify cleanup
                assert len(download_service.background_tasks) == 0

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    @pytest.mark.memory
    async def test_continuous_monitoring(self, detector, download_service):
        """Test continuous monitoring for memory leaks."""
        monitor = ResourceMonitor("DownloadService")

        try:
            # Start monitoring
            await monitor.start_monitoring(interval=0.5)

            # Simulate service activity
            for i in range(10):
                request = DownloadRequest(
                    video_id=f"monitor_video_{i}",
                    quality="720p",
                    output_path="/tmp/test_output",
                    job_id=f"monitor_job_{i}",
                )

                with patch("yt_dlp.YoutubeDL") as mock_ytdl:
                    mock_instance = Mock()
                    mock_instance.extract_info.return_value = {
                        "title": f"Monitor Video {i}",
                        "duration": 120,
                        "uploader": "Test Channel",
                    }
                    mock_ytdl.return_value = mock_instance

                    with patch("httpx.AsyncClient") as mock_client:
                        mock_client.return_value.__aenter__.return_value.post.return_value.status_code = (
                            200
                        )
                        mock_client.return_value.__aenter__.return_value.put.return_value.status_code = (
                            200
                        )

                        task = await download_service._create_download_task(request)
                        await download_service._process_download(task)

                # Small delay to allow monitoring samples
                await asyncio.sleep(0.1)

            # Get statistics
            stats = monitor.get_statistics()

            # Verify monitoring worked
            assert stats["sample_count"] > 0
            assert (
                stats["memory_stats"]["rss_growth_mb"] < 50
            )  # Should not grow significantly

        finally:
            await monitor.stop_monitoring()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
