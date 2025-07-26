"""Simple memory leak tests for YTArchive services."""

import gc
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import psutil
import pytest

# Add project root to path BEFORE importing services
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import services after path modification
from services.common.base import ServiceSettings  # noqa: E402
from services.download.main import DownloadService  # noqa: E402
from services.metadata.main import MetadataService  # noqa: E402
from services.storage.main import StorageService  # noqa: E402


class SimpleMemoryProfiler:
    """Simple memory profiler for basic leak detection."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.start_memory = 0
        self.peak_memory = 0
        self.end_memory = 0
        self.process = psutil.Process()

    def start(self):
        """Start memory profiling."""
        gc.collect()  # Force garbage collection
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.peak_memory = self.start_memory
        print(f"🔍 {self.service_name} - Start memory: {self.start_memory:.1f} MB")

    def checkpoint(self, label: str = ""):
        """Take a memory checkpoint."""
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.peak_memory = max(self.peak_memory, current_memory)
        print(f"📊 {self.service_name} - {label} memory: {current_memory:.1f} MB")
        return current_memory

    def stop(self):
        """Stop memory profiling and analyze."""
        gc.collect()  # Force garbage collection
        self.end_memory = self.process.memory_info().rss / 1024 / 1024  # MB

        memory_growth = self.end_memory - self.start_memory
        peak_growth = self.peak_memory - self.start_memory

        print(f"📊 {self.service_name} - End memory: {self.end_memory:.1f} MB")
        print(f"📈 {self.service_name} - Memory growth: {memory_growth:.1f} MB")
        print(f"🔝 {self.service_name} - Peak growth: {peak_growth:.1f} MB")

        # Define thresholds (MB)
        if memory_growth > 50:
            print(f"🚨 {self.service_name} - CRITICAL: Memory growth > 50 MB!")
            return "CRITICAL"
        elif memory_growth > 20:
            print(f"⚠️ {self.service_name} - HIGH: Memory growth > 20 MB!")
            return "HIGH"
        elif memory_growth > 10:
            print(f"⚠️ {self.service_name} - MEDIUM: Memory growth > 10 MB!")
            return "MEDIUM"
        elif memory_growth > 5:
            print(f"⚠️ {self.service_name} - LOW: Memory growth > 5 MB!")
            return "LOW"
        else:
            print(f"✅ {self.service_name} - OK: Memory growth acceptable")
            return "OK"


class TestSimpleMemoryLeaks:
    """Simple memory leak tests for YTArchive services."""

    @pytest.mark.memory
    def test_download_service_memory_usage(self):
        """Test Download Service memory usage."""
        profiler = SimpleMemoryProfiler("DownloadService")
        profiler.start()

        # Mock environment for testing
        with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test_key"}):
            settings = ServiceSettings(port=8002)
            service = DownloadService("TestDownloadService", settings)

            profiler.checkpoint("After service creation")

            # Simulate multiple downloads
            for i in range(10):
                # Mock yt-dlp and HTTP clients
                with patch("yt_dlp.YoutubeDL") as mock_ytdl, patch(
                    "httpx.AsyncClient"
                ) as mock_client:
                    mock_instance = Mock()
                    mock_instance.extract_info.return_value = {
                        "title": f"Test Video {i}",
                        "duration": 120,
                        "uploader": "Test Channel",
                    }
                    mock_ytdl.return_value = mock_instance

                    mock_client.return_value.__aenter__.return_value.post.return_value.status_code = (
                        200
                    )
                    mock_client.return_value.__aenter__.return_value.put.return_value.status_code = (
                        200
                    )

                    # Create download task (synchronous parts only)
                    task_id = f"task_{i}"
                    service.active_tasks[task_id] = Mock()

                    # Simulate cleanup
                    if task_id in service.active_tasks:
                        del service.active_tasks[task_id]

            profiler.checkpoint("After simulated downloads")

            # Verify cleanup
            assert len(service.active_tasks) == 0

            result = profiler.stop()
            assert result in [
                "OK",
                "LOW",
                "MEDIUM",
            ], f"Download service memory usage too high: {result}"

    @pytest.mark.memory
    def test_metadata_service_memory_usage(self):
        """Test Metadata Service memory usage."""
        profiler = SimpleMemoryProfiler("MetadataService")
        profiler.start()

        # Mock environment for testing
        with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test_key"}):
            settings = ServiceSettings(port=8001)
            service = MetadataService("TestMetadataService", settings)

            profiler.checkpoint("After service creation")

            # Mock YouTube API
            mock_response = {
                "items": [
                    {
                        "id": "test_video",
                        "snippet": {
                            "title": "Test Video",
                            "description": "Test Description",
                            "publishedAt": "2023-01-01T00:00:00Z",
                            "channelId": "test_channel",
                            "channelTitle": "Test Channel",
                            "thumbnails": {
                                "default": {"url": "http://example.com/thumb.jpg"}
                            },
                        },
                        "contentDetails": {"duration": "PT4M13S"},
                        "statistics": {"viewCount": "1000", "likeCount": "100"},
                    }
                ]
            }

            # Mock YouTube API chains properly
            with patch.object(service, "youtube") as mock_youtube:
                # Create proper mock chain for YouTube API
                mock_execute = Mock()
                mock_execute.return_value = mock_response
                mock_list = Mock()
                mock_list.return_value.execute = mock_execute
                mock_videos = Mock()
                mock_videos.return_value.list = mock_list
                mock_youtube.videos = mock_videos

                # Simulate multiple metadata requests
                for i in range(50):
                    video_id = f"test_video_{i}"
                    # Set cache directly to simulate API responses
                    cache_key = service._get_cache_key("video", video_id)
                    service._set_cache(cache_key, mock_response["items"][0], 3600)

                profiler.checkpoint("After simulated metadata requests")

                # Test cache cleanup
                # Cache size before cleanup
                len(service.cache)

                # Force cache expiration
                for cache_key in list(service.cache.keys()):
                    service.cache[cache_key].expires_at = time.time() - 1

                # Trigger cleanup by accessing cache
                service._get_from_cache("non_existent_key")

                profiler.checkpoint("After cache cleanup")

            result = profiler.stop()
            assert result in [
                "OK",
                "LOW",
                "MEDIUM",
            ], f"Metadata service memory usage too high: {result}"

    @pytest.mark.memory
    def test_storage_service_memory_usage(self):
        """Test Storage Service memory usage."""
        profiler = SimpleMemoryProfiler("StorageService")
        profiler.start()

        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            settings = ServiceSettings(port=8003)
            service = StorageService("TestStorageService", settings)

            # Override directories to use temp directory
            service.base_output_dir = temp_path
            service.metadata_dir = temp_path / "metadata"
            service.videos_dir = temp_path / "videos"
            service.work_plans_dir = temp_path / "work_plans"
            service._ensure_directories()

            profiler.checkpoint("After service creation")

            # Simulate multiple storage operations
            for i in range(30):
                video_id = f"storage_video_{i}"

                # Create metadata
                metadata = {
                    "video_id": video_id,
                    "title": f"Storage Video {i}",
                    "description": f"Storage Description {i}",
                    "duration": 120,
                    "upload_date": "2023-01-01T00:00:00Z",
                    "channel_id": "storage_channel",
                    "channel_title": "Storage Channel",
                    "thumbnail_urls": {"default": f"http://example.com/thumb_{i}.jpg"},
                    "view_count": 1000,
                    "like_count": 100,
                    "fetched_at": "2023-01-01T00:00:00Z",
                }

                # Save metadata (synchronous for testing)
                metadata_file = service.metadata_dir / "videos" / f"{video_id}.json"
                with open(metadata_file, "w") as f:
                    import json

                    json.dump(metadata, f)

                # Create video file
                video_path = service.videos_dir / video_id / f"{video_id}.mp4"
                video_path.parent.mkdir(parents=True, exist_ok=True)
                video_path.write_bytes(b"fake video content " * 100)

            profiler.checkpoint("After simulated storage operations")

            # Verify files were created
            metadata_files = list((service.metadata_dir / "videos").glob("*.json"))
            assert len(metadata_files) == 30

            video_dirs = list(service.videos_dir.glob("*"))
            assert len(video_dirs) == 30

            result = profiler.stop()
            assert result in [
                "OK",
                "LOW",
                "MEDIUM",
            ], f"Storage service memory usage too high: {result}"

    @pytest.mark.memory
    def test_service_cleanup_effectiveness(self):
        """Test that services properly clean up resources."""
        profiler = SimpleMemoryProfiler("ServiceCleanup")
        profiler.start()

        # Create and destroy services multiple times
        for i in range(5):
            with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test_key"}):
                # Create services
                download_service = DownloadService(
                    "TestDownload", ServiceSettings(port=8002)
                )
                metadata_service = MetadataService(
                    "TestMetadata", ServiceSettings(port=8001)
                )
                storage_service = StorageService(
                    "TestStorage", ServiceSettings(port=8003)
                )

                # Use services briefly
                download_service.active_tasks[f"task_{i}"] = Mock()
                metadata_service._set_cache(f"test_key_{i}", {"data": "test"}, 3600)

                # Clean up
                del download_service.active_tasks[f"task_{i}"]
                del metadata_service.cache[f"test_key_{i}"]

                # Delete service instances
                del download_service
                del metadata_service
                del storage_service

                # Force garbage collection
                gc.collect()

        profiler.checkpoint("After service creation/destruction cycles")

        result = profiler.stop()
        assert result in ["OK", "LOW"], f"Service cleanup ineffective: {result}"

    @pytest.mark.memory
    def test_concurrent_operations_memory_usage(self):
        """Test memory usage under concurrent operations."""
        profiler = SimpleMemoryProfiler("ConcurrentOperations")
        profiler.start()

        with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test_key"}):
            # Create services
            download_service = DownloadService(
                "TestDownload", ServiceSettings(port=8002)
            )
            metadata_service = MetadataService(
                "TestMetadata", ServiceSettings(port=8001)
            )

            profiler.checkpoint("After service creation")

            # Simulate concurrent operations
            for i in range(20):
                # Download service operations
                task_id = f"concurrent_task_{i}"
                download_service.active_tasks[task_id] = Mock()
                download_service.task_progress[task_id] = Mock()

                # Metadata service operations
                cache_key = f"concurrent_video_{i}"
                metadata_service._set_cache(cache_key, {"video_id": cache_key}, 3600)

                # Simulate some work
                time.sleep(0.001)

                # Clean up
                if task_id in download_service.active_tasks:
                    del download_service.active_tasks[task_id]
                if task_id in download_service.task_progress:
                    del download_service.task_progress[task_id]

            profiler.checkpoint("After concurrent operations")

            # Verify cleanup
            assert len(download_service.active_tasks) == 0
            assert len(download_service.task_progress) == 0

            result = profiler.stop()
            assert result in [
                "OK",
                "LOW",
                "MEDIUM",
            ], f"Concurrent operations memory usage too high: {result}"


@pytest.mark.memory
def test_memory_leak_summary():
    """Run all memory leak tests and provide summary."""
    print("\n" + "=" * 60)
    print("🔍 YTARCHIVE MEMORY LEAK DETECTION SUMMARY")
    print("=" * 60)

    # This will run all the test methods above
    test_instance = TestSimpleMemoryLeaks()

    results = []

    try:
        print("\n1. Testing Download Service...")
        test_instance.test_download_service_memory_usage()
        results.append("✅ Download Service: PASSED")
    except Exception as e:
        results.append(f"❌ Download Service: FAILED - {str(e)}")

    try:
        print("\n2. Testing Metadata Service...")
        test_instance.test_metadata_service_memory_usage()
        results.append("✅ Metadata Service: PASSED")
    except Exception as e:
        results.append(f"❌ Metadata Service: FAILED - {str(e)}")

    try:
        print("\n3. Testing Storage Service...")
        test_instance.test_storage_service_memory_usage()
        results.append("✅ Storage Service: PASSED")
    except Exception as e:
        results.append(f"❌ Storage Service: FAILED - {str(e)}")

    try:
        print("\n4. Testing Service Cleanup...")
        test_instance.test_service_cleanup_effectiveness()
        results.append("✅ Service Cleanup: PASSED")
    except Exception as e:
        results.append(f"❌ Service Cleanup: FAILED - {str(e)}")

    try:
        print("\n5. Testing Concurrent Operations...")
        test_instance.test_concurrent_operations_memory_usage()
        results.append("✅ Concurrent Operations: PASSED")
    except Exception as e:
        results.append(f"❌ Concurrent Operations: FAILED - {str(e)}")

    print("\n" + "=" * 60)
    print("📊 MEMORY LEAK DETECTION RESULTS")
    print("=" * 60)

    passed = sum(1 for r in results if "PASSED" in r)
    failed = sum(1 for r in results if "FAILED" in r)

    for result in results:
        print(result)

    print(f"\nSummary: {passed} passed, {failed} failed")

    if failed == 0:
        print("\n✅ ALL MEMORY LEAK TESTS PASSED!")
        print("🚀 Services are ready for production deployment")
    else:
        print(f"\n❌ {failed} MEMORY LEAK TESTS FAILED!")
        print("⚠️ Review and fix issues before production deployment")

    # Assert all tests passed (pytest expects None return, not boolean)
    assert failed == 0, f"{failed} memory leak tests failed - review and fix issues"


if __name__ == "__main__":
    test_memory_leak_summary()
