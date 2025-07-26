"""Memory leak tests for Storage Service."""

import asyncio
import pytest
import tempfile
import shutil
import json
from pathlib import Path
from datetime import datetime, timezone

from tests.memory_leak_detection import (
    MemoryLeakDetector,
    memory_leak_test,
    ResourceMonitor,
)
from services.storage.main import StorageService, SaveVideoRequest
from services.common.base import ServiceSettings


class TestStorageServiceMemoryLeaks:
    """Test suite for Storage Service memory leaks."""

    @pytest.fixture
    def detector(self):
        """Create memory leak detector."""
        return MemoryLeakDetector("StorageService")

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for storage."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def storage_service(self, temp_dir):
        """Create storage service instance."""
        settings = ServiceSettings(port=8003)
        service = StorageService("TestStorageService", settings)

        # Override directories to use temp directory
        service.base_output_dir = temp_dir
        service.metadata_dir = temp_dir / "metadata"
        service.videos_dir = temp_dir / "videos"
        service.work_plans_dir = temp_dir / "work_plans"
        service._ensure_directories()

        return service

    @pytest.mark.asyncio
    @pytest.mark.memory
    async def test_metadata_storage_memory_leak(self, detector, storage_service):
        """Test memory leaks in metadata storage."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "metadata_storage"):
                # Store metadata for multiple videos
                for i in range(50):
                    video_id = f"metadata_video_{i}"
                    metadata = {
                        "video_id": video_id,
                        "title": f"Test Video {i}",
                        "description": f"Test Description {i}",
                        "duration": 120,
                        "upload_date": datetime.now(timezone.utc).isoformat(),
                        "channel_id": "test_channel",
                        "channel_title": "Test Channel",
                        "thumbnail_urls": {
                            "default": f"http://example.com/thumb_{i}.jpg"
                        },
                        "view_count": 1000,
                        "like_count": 100,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    }

                    result = await storage_service._save_metadata(video_id, metadata)
                    assert result is not None

                # Verify files were created
                metadata_files = list(
                    (storage_service.metadata_dir / "videos").glob("*.json")
                )
                assert len(metadata_files) == 50

                # Test metadata retrieval
                for i in range(50):
                    video_id = f"metadata_video_{i}"
                    exists = await storage_service._check_video_exists(video_id)
                    assert exists.exists
                    assert exists.has_metadata

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    @pytest.mark.memory
    async def test_video_storage_memory_leak(self, detector, storage_service):
        """Test memory leaks in video storage operations."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "video_storage"):
                # Store video information for multiple videos
                for i in range(20):
                    video_id = f"video_storage_{i}"
                    video_path = (
                        storage_service.videos_dir / video_id / f"{video_id}.mp4"
                    )
                    video_path.parent.mkdir(parents=True, exist_ok=True)

                    # Create fake video file
                    video_path.write_bytes(b"fake video content " * 1000)

                    request = SaveVideoRequest(
                        video_id=video_id,
                        video_path=str(video_path),
                        file_size=len(b"fake video content " * 1000),
                        download_completed_at=datetime.now(timezone.utc),
                    )

                    result = await storage_service._save_video_info(request)
                    assert result is not None

                # Verify video records were created
                for i in range(20):
                    video_id = f"video_storage_{i}"
                    exists = await storage_service._check_video_exists(video_id)
                    assert exists.exists
                    assert exists.has_video

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    @pytest.mark.memory
    async def test_work_plan_storage_memory_leak(self, detector, storage_service):
        """Test memory leaks in work plan storage."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "work_plan_storage"):
                # Import required models
                from services.common.models import UnavailableVideo, FailedDownload

                # Create multiple work plans
                for i in range(10):
                    # Create UnavailableVideo instances
                    unavailable_videos = []
                    for j in range(5):
                        unavailable_video = UnavailableVideo(
                            video_id=f"unavailable_{i}_{j}",
                            reason="private",
                            detected_at=datetime.now(timezone.utc),
                        )
                        unavailable_videos.append(unavailable_video)

                    # Create FailedDownload instances
                    failed_downloads = []
                    for j in range(3):
                        failed_download = FailedDownload(
                            video_id=f"failed_{i}_{j}",
                            title=f"Failed Video {i}_{j}",
                            attempts=1,
                            last_attempt=datetime.now(timezone.utc),
                            errors=[
                                {
                                    "error": "Download failed",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                }
                            ],
                        )
                        failed_downloads.append(failed_download)

                    result = await storage_service._generate_work_plan(
                        unavailable_videos, failed_downloads
                    )
                    assert result is not None
                    assert result.get("plan_id") is not None

                    # Sufficient delay to prevent timestamp collisions in file names
                    import time

                    time.sleep(1.0)

                # Verify work plan files were created
                work_plan_files = list(storage_service.work_plans_dir.glob("*.json"))
                assert len(work_plan_files) == 10

                # Test work plan file verification (memory leak testing focus)
                for work_plan_file in work_plan_files:
                    with open(work_plan_file) as f:
                        plan_data = json.load(f)

                    # Verify work plan data structure for memory leak testing
                    assert plan_data.get("plan_id") is not None
                    assert plan_data.get("total_videos") is not None
                    assert isinstance(plan_data.get("unavailable_videos"), list)
                    assert isinstance(plan_data.get("failed_downloads"), list)

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    @pytest.mark.memory
    async def test_storage_stats_memory_leak(self, detector, storage_service):
        """Test memory leaks in storage statistics calculation."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "storage_stats"):
                # Create test data
                for i in range(30):
                    video_id = f"stats_video_{i}"

                    # Create metadata
                    metadata = {
                        "video_id": video_id,
                        "title": f"Stats Video {i}",
                        "description": f"Stats Description {i}",
                        "duration": 120,
                        "upload_date": datetime.now(timezone.utc).isoformat(),
                        "channel_id": "stats_channel",
                        "channel_title": "Stats Channel",
                        "thumbnail_urls": {
                            "default": f"http://example.com/thumb_{i}.jpg"
                        },
                        "view_count": 1000,
                        "like_count": 100,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    }

                    await storage_service._save_metadata(video_id, metadata)

                    # Create video file
                    video_path = (
                        storage_service.videos_dir / video_id / f"{video_id}.mp4"
                    )
                    video_path.parent.mkdir(parents=True, exist_ok=True)
                    video_path.write_bytes(b"fake video content " * 500)

                    # Create thumbnail
                    thumbnail_path = (
                        storage_service.videos_dir / video_id / f"{video_id}_thumb.jpg"
                    )
                    thumbnail_path.write_bytes(b"fake thumbnail " * 100)

                # Calculate stats multiple times
                for i in range(10):
                    stats = await storage_service._get_storage_stats()
                    assert stats.total_videos == 30
                    assert stats.video_count == 30
                    assert stats.thumbnail_count == 30
                    assert stats.total_size_bytes > 0

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    @pytest.mark.memory
    async def test_file_operations_memory_leak(self, detector, storage_service):
        """Test memory leaks in file operations."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "file_operations"):
                # Test various file operations
                for i in range(25):
                    video_id = f"file_ops_video_{i}"

                    # Create and write metadata file
                    metadata_file = (
                        storage_service.metadata_dir / "videos" / f"{video_id}.json"
                    )
                    metadata_data = {
                        "video_id": video_id,
                        "title": f"File Ops Video {i}",
                        "description": f"File operations test {i}",
                        "duration": 180,
                        "upload_date": datetime.now(timezone.utc).isoformat(),
                        "channel_id": "file_ops_channel",
                        "channel_title": "File Ops Channel",
                        "thumbnail_urls": {
                            "default": f"http://example.com/thumb_{i}.jpg"
                        },
                        "view_count": 1500,
                        "like_count": 150,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    }

                    with open(metadata_file, "w") as f:
                        json.dump(metadata_data, f, indent=2)

                    # Read metadata file
                    with open(metadata_file, "r") as f:
                        loaded_data = json.load(f)

                    assert loaded_data["video_id"] == video_id

                    # Create video directory structure
                    video_dir = storage_service.videos_dir / video_id
                    video_dir.mkdir(parents=True, exist_ok=True)

                    # Create multiple files in video directory
                    (video_dir / f"{video_id}.mp4").write_bytes(b"fake video " * 200)
                    (video_dir / f"{video_id}_thumb.jpg").write_bytes(
                        b"fake thumb " * 50
                    )

                    # Create captions directory
                    captions_dir = video_dir / "captions"
                    captions_dir.mkdir(exist_ok=True)
                    (captions_dir / "en.vtt").write_text(
                        "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello world"
                    )

                    # Check file existence
                    assert (video_dir / f"{video_id}.mp4").exists()
                    assert (video_dir / f"{video_id}_thumb.jpg").exists()
                    assert (captions_dir / "en.vtt").exists()

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    @pytest.mark.memory
    async def test_concurrent_storage_operations(self, detector, storage_service):
        """Test memory leaks with concurrent storage operations."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "concurrent_storage"):
                # Define concurrent operations
                async def store_metadata(video_id: str):
                    metadata = {
                        "video_id": video_id,
                        "title": f"Concurrent Video {video_id}",
                        "description": f"Concurrent test {video_id}",
                        "duration": 120,
                        "upload_date": datetime.now(timezone.utc).isoformat(),
                        "channel_id": "concurrent_channel",
                        "channel_title": "Concurrent Channel",
                        "thumbnail_urls": {
                            "default": f"http://example.com/thumb_{video_id}.jpg"
                        },
                        "view_count": 1000,
                        "like_count": 100,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    }
                    return await storage_service._save_metadata(video_id, metadata)

                async def check_existence(video_id: str):
                    return await storage_service._check_video_exists(video_id)

                async def get_stats():
                    return await storage_service._get_storage_stats()

                # Run concurrent operations
                tasks = []
                for i in range(15):
                    video_id = f"concurrent_{i}"

                    # Store metadata
                    metadata = {
                        "video_id": video_id,
                        "title": f"Concurrent Video {video_id}",
                        "description": f"Concurrent test {video_id}",
                        "duration": 120,
                        "upload_date": datetime.now(timezone.utc).isoformat(),
                        "channel_id": "concurrent_channel",
                        "channel_title": "Concurrent Channel",
                        "thumbnail_urls": {
                            "default": f"http://example.com/thumb_{video_id}.jpg"
                        },
                        "view_count": 1000,
                        "like_count": 100,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    }

                    # Store metadata first
                    await storage_service._save_metadata(video_id, metadata)

                    request = SaveVideoRequest(
                        video_id=video_id,
                        video_path=str(
                            storage_service.videos_dir / video_id / f"{video_id}.mp4"
                        ),
                        file_size=1000,
                        download_completed_at=datetime.now(timezone.utc),
                    )

                    tasks.append(store_metadata(video_id))
                    tasks.append(check_existence(video_id))
                    tasks.append(storage_service._save_video_info(request))
                    if i % 5 == 0:
                        tasks.append(get_stats())

                # Wait for all operations
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Verify most operations succeeded
                successful = sum(1 for r in results if not isinstance(r, Exception))
                assert successful > len(tasks) * 0.8  # At least 80% success rate

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    @pytest.mark.memory
    async def test_large_file_handling(self, detector, storage_service):
        """Test memory leaks with large file handling."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "large_file_handling"):
                # Create large metadata files
                for i in range(5):
                    video_id = f"large_file_{i}"

                    # Create large metadata (simulate comprehensive video info)
                    large_metadata = {
                        "video_id": video_id,
                        "title": f"Large File Test {i}",
                        "description": "Large description " * 1000,  # Large description
                        "duration": 7200,  # 2 hours
                        "upload_date": datetime.now(timezone.utc).isoformat(),
                        "channel_id": "large_file_channel",
                        "channel_title": "Large File Channel",
                        "thumbnail_urls": {
                            "default": f"http://example.com/thumb_{i}.jpg",
                            "medium": f"http://example.com/thumb_medium_{i}.jpg",
                            "high": f"http://example.com/thumb_high_{i}.jpg",
                            "standard": f"http://example.com/thumb_standard_{i}.jpg",
                            "maxres": f"http://example.com/thumb_maxres_{i}.jpg",
                        },
                        "view_count": 1000000,
                        "like_count": 50000,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "comments": [
                            f"Comment {j}" for j in range(1000)
                        ],  # Many comments
                        "tags": [f"tag_{j}" for j in range(100)],  # Many tags
                    }

                    result = await storage_service._save_metadata(
                        video_id, large_metadata
                    )
                    assert result is not None

                    # Verify file was created and can be read
                    exists = await storage_service._check_video_exists(video_id)
                    assert exists.exists
                    assert exists.has_metadata

                    # Create large video file placeholder
                    video_path = (
                        storage_service.videos_dir / video_id / f"{video_id}.mp4"
                    )
                    video_path.parent.mkdir(parents=True, exist_ok=True)
                    video_path.write_bytes(b"fake large video content " * 10000)

                # Test storage stats with large files
                stats = await storage_service._get_storage_stats()
                assert stats.total_videos == 5
                assert stats.total_size_bytes > 0

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    @pytest.mark.memory
    async def test_continuous_monitoring(self, detector, storage_service):
        """Test continuous monitoring for memory leaks."""
        monitor = ResourceMonitor("StorageService")

        try:
            # Start monitoring
            await monitor.start_monitoring(interval=0.5)

            # Simulate continuous storage operations
            for i in range(15):
                video_id = f"monitor_video_{i}"

                # Store metadata
                metadata = {
                    "video_id": video_id,
                    "title": f"Monitor Video {i}",
                    "description": f"Monitor Description {i}",
                    "duration": 120,
                    "upload_date": datetime.now(timezone.utc).isoformat(),
                    "channel_id": "monitor_channel",
                    "channel_title": "Monitor Channel",
                    "thumbnail_urls": {"default": f"http://example.com/thumb_{i}.jpg"},
                    "view_count": 1000,
                    "like_count": 100,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }

                await storage_service._save_metadata(video_id, metadata)

                # Create video file
                video_path = storage_service.videos_dir / video_id / f"{video_id}.mp4"
                video_path.parent.mkdir(parents=True, exist_ok=True)
                video_path.write_bytes(b"fake video content " * 300)

                # Check existence
                exists = await storage_service._check_video_exists(video_id)
                assert exists.exists

                # Get stats periodically
                if i % 3 == 0:
                    stats = await storage_service._get_storage_stats()
                    assert stats.total_videos > 0

                # Small delay to allow monitoring
                await asyncio.sleep(0.1)

            # Get monitoring statistics
            stats = monitor.get_statistics()

            # Verify monitoring worked
            assert stats["sample_count"] > 0
            assert (
                stats["memory_stats"]["rss_growth_mb"] < 40
            )  # Should not grow significantly

        finally:
            await monitor.stop_monitoring()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
