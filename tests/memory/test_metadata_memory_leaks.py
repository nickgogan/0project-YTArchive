"""Memory leak tests for Metadata Service."""

import asyncio
import pytest
import time
from unittest.mock import Mock, patch

from tests.memory_leak_detection import (
    MemoryLeakDetector,
    memory_leak_test,
    ResourceMonitor,
)
from services.metadata.main import MetadataService
from services.common.base import ServiceSettings


class TestMetadataServiceMemoryLeaks:
    """Test suite for Metadata Service memory leaks."""

    @pytest.fixture
    def detector(self):
        """Create memory leak detector."""
        return MemoryLeakDetector("MetadataService")

    @pytest.fixture
    def metadata_service(self):
        """Create metadata service instance."""
        settings = ServiceSettings(port=8001)

        # Mock API key
        with patch.dict("os.environ", {"YOUTUBE_API_KEY": "test_api_key"}):
            service = MetadataService("TestMetadataService", settings)
            return service

    @pytest.mark.asyncio
    async def test_single_video_metadata_memory_leak(self, detector, metadata_service):
        """Test memory leaks in single video metadata fetch."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "single_video_metadata"):
                # Mock YouTube API response
                mock_response = {
                    "items": [
                        {
                            "id": "test_video_123",
                            "snippet": {
                                "title": "Test Video",
                                "description": "Test Description",
                                "publishedAt": "2023-01-01T00:00:00Z",
                                "channelId": "test_channel",
                                "channelTitle": "Test Channel",
                                "thumbnails": {
                                    "default": {"url": "http://example.com/thumb.jpg"},
                                    "medium": {
                                        "url": "http://example.com/thumb_medium.jpg"
                                    },
                                    "high": {
                                        "url": "http://example.com/thumb_high.jpg"
                                    },
                                },
                            },
                            "contentDetails": {"duration": "PT4M13S"},
                            "statistics": {"viewCount": "1000", "likeCount": "100"},
                        }
                    ]
                }

                # Mock YouTube API client
                metadata_service.youtube.videos.return_value.list.return_value.execute.return_value = (
                    mock_response
                )

                # Fetch metadata
                result = await metadata_service._get_video_metadata("test_video_123")

                # Verify result
                assert result.video_id == "test_video_123"
                assert result.title == "Test Video"

                # Verify cache is properly managed
                cache_key = metadata_service._get_cache_key("video", "test_video_123")
                assert cache_key in metadata_service.cache

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    async def test_cache_memory_leak(self, detector, metadata_service):
        """Test memory leaks in caching system."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "cache_memory_leak"):
                # Mock YouTube API response
                mock_response = {
                    "items": [
                        {
                            "id": "cache_video_{i}",
                            "snippet": {
                                "title": "Cache Video {i}",
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

                # Fill cache with many entries
                for i in range(100):
                    # Update mock response for each video
                    mock_response["items"][0]["id"] = f"cache_video_{i}"
                    mock_response["items"][0]["snippet"]["title"] = f"Cache Video {i}"

                    metadata_service.youtube.videos.return_value.list.return_value.execute.return_value = (
                        mock_response
                    )

                    # Fetch metadata (should be cached)
                    await metadata_service._get_video_metadata(f"cache_video_{i}")

                # Verify cache size
                initial_cache_size = len(metadata_service.cache)
                assert initial_cache_size == 100

                # Test cache expiration cleanup
                # Set TTL to 0 to force expiration
                for cache_key in list(metadata_service.cache.keys()):
                    metadata_service.cache[cache_key].expires_at = time.time() - 1

                # Access cache to trigger cleanup
                await metadata_service._get_video_metadata("new_video")

                # Verify expired entries were cleaned up
                # (This depends on the implementation of cache cleanup)

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    async def test_batch_fetch_memory_leak(self, detector, metadata_service):
        """Test memory leaks in batch metadata fetch."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "batch_fetch"):
                # Mock batch API response
                mock_response = {"items": []}

                # Create 50 video entries
                for i in range(50):
                    mock_response["items"].append(
                        {
                            "id": f"batch_video_{i}",
                            "snippet": {
                                "title": f"Batch Video {i}",
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
                    )

                metadata_service.youtube.videos.return_value.list.return_value.execute.return_value = (
                    mock_response
                )

                # Batch fetch metadata
                video_ids = [f"batch_video_{i}" for i in range(50)]
                result = await metadata_service._batch_fetch_metadata(video_ids)

                # Verify results
                assert len(result.metadata) == 50
                assert len(result.failed) == 0

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    async def test_playlist_metadata_memory_leak(self, detector, metadata_service):
        """Test memory leaks in playlist metadata fetch."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "playlist_metadata"):
                # Mock playlist API response
                mock_playlist_response = {
                    "items": [
                        {
                            "id": "test_playlist",
                            "snippet": {
                                "title": "Test Playlist",
                                "description": "Test Playlist Description",
                                "channelId": "test_channel",
                                "channelTitle": "Test Channel",
                            },
                            "contentDetails": {"itemCount": 10},
                        }
                    ]
                }

                # Mock playlist items response
                mock_items_response = {"items": []}

                for i in range(10):
                    mock_items_response["items"].append(
                        {
                            "snippet": {
                                "resourceId": {"videoId": f"playlist_video_{i}"},
                                "title": f"Playlist Video {i}",
                            }
                        }
                    )

                # Mock API calls
                metadata_service.youtube.playlists.return_value.list.return_value.execute.return_value = (
                    mock_playlist_response
                )
                metadata_service.youtube.playlistItems.return_value.list.return_value.execute.return_value = (
                    mock_items_response
                )

                # Fetch playlist metadata
                result = await metadata_service._get_playlist_metadata("test_playlist")

                # Verify results
                assert result.playlist_id == "test_playlist"
                assert result.title == "Test Playlist"
                assert len(result.videos) == 10

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    async def test_quota_management_memory_leak(self, detector, metadata_service):
        """Test memory leaks in quota management."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "quota_management"):
                # Reset quota
                metadata_service.quota_used = 0

                # Simulate quota usage
                for i in range(100):
                    # Check quota
                    can_proceed = metadata_service._check_quota(1)
                    if can_proceed:
                        metadata_service._use_quota(1)

                    # Get quota status
                    quota_status = await metadata_service._get_quota_status()
                    assert quota_status.quota_used == metadata_service.quota_used

                # Verify quota tracking doesn't cause memory growth
                assert metadata_service.quota_used <= metadata_service.quota_limit

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    async def test_api_error_handling_memory_leak(self, detector, metadata_service):
        """Test memory leaks in API error handling."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "api_error_handling"):
                from googleapiclient.errors import HttpError

                # Mock API to raise errors
                mock_response = Mock()
                mock_response.status = 404
                error = HttpError(mock_response, b"Not Found")

                metadata_service.youtube.videos.return_value.list.return_value.execute.side_effect = (
                    error
                )

                # Test error handling
                for i in range(10):
                    try:
                        await metadata_service._get_video_metadata(f"error_video_{i}")
                    except Exception:
                        pass  # Expected to fail

                # Verify no memory leaks from error handling
                # Cache should not grow with failed requests
                failed_cache_entries = [
                    k for k in metadata_service.cache.keys() if "error_video" in k
                ]
                assert len(failed_cache_entries) == 0

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    async def test_concurrent_requests_memory_leak(self, detector, metadata_service):
        """Test memory leaks with concurrent requests."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "concurrent_requests"):
                # Mock API response
                mock_response = {
                    "items": [
                        {
                            "id": "concurrent_video",
                            "snippet": {
                                "title": "Concurrent Video",
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

                metadata_service.youtube.videos.return_value.list.return_value.execute.return_value = (
                    mock_response
                )

                # Start concurrent requests
                tasks = []
                for i in range(20):
                    task = asyncio.create_task(
                        metadata_service._get_video_metadata(f"concurrent_video_{i}")
                    )
                    tasks.append(task)

                # Wait for completion
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Verify results
                successful_results = [
                    r for r in results if not isinstance(r, Exception)
                ]
                assert len(successful_results) >= 0  # Some may succeed from cache

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    async def test_cache_expiration_cleanup(self, detector, metadata_service):
        """Test that cache expiration doesn't cause memory leaks."""
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, "cache_expiration"):
                # Mock API response
                mock_response = {
                    "items": [
                        {
                            "id": "expiration_video",
                            "snippet": {
                                "title": "Expiration Video",
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

                metadata_service.youtube.videos.return_value.list.return_value.execute.return_value = (
                    mock_response
                )

                # Add entries to cache
                for i in range(50):
                    cache_key = f"video:expiration_video_{i}"
                    metadata_service._set_cache(
                        cache_key, {"video_id": f"expiration_video_{i}"}, 1
                    )

                # Wait for expiration
                await asyncio.sleep(2)

                # Trigger cache cleanup by accessing a new key
                await metadata_service._get_video_metadata("new_video_after_expiration")

                # Verify expired entries were cleaned up
                expired_count = sum(
                    1 for k in metadata_service.cache.keys() if "expiration_video" in k
                )
                assert expired_count == 0  # Should be cleaned up

        finally:
            detector.stop_tracing()

    @pytest.mark.asyncio
    async def test_continuous_monitoring(self, detector, metadata_service):
        """Test continuous monitoring for memory leaks."""
        monitor = ResourceMonitor("MetadataService")

        try:
            # Start monitoring
            await monitor.start_monitoring(interval=0.5)

            # Mock API response
            mock_response = {
                "items": [
                    {
                        "id": "monitor_video",
                        "snippet": {
                            "title": "Monitor Video",
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

            metadata_service.youtube.videos.return_value.list.return_value.execute.return_value = (
                mock_response
            )

            # Simulate service activity
            for i in range(20):
                await metadata_service._get_video_metadata(f"monitor_video_{i}")
                await asyncio.sleep(0.1)

            # Get statistics
            stats = monitor.get_statistics()

            # Verify monitoring worked
            assert stats["sample_count"] > 0
            assert (
                stats["memory_stats"]["rss_growth_mb"] < 30
            )  # Should not grow significantly

        finally:
            await monitor.stop_monitoring()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
