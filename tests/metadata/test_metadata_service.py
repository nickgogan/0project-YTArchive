"""Comprehensive tests for Metadata Service."""

import asyncio
import os
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient
from googleapiclient.errors import HttpError

from services.metadata.main import MetadataService
from services.common.base import ServiceSettings


@pytest.fixture
def mock_youtube_api():
    """Mock YouTube API client."""
    mock_youtube = MagicMock()
    return mock_youtube


@pytest.fixture
def sample_video_data():
    """Sample YouTube API video response data."""
    return {
        "id": "dQw4w9WgXcQ",
        "snippet": {
            "title": "Rick Astley - Never Gonna Give You Up",
            "description": "Official music video for Never Gonna Give You Up",
            "publishedAt": "2009-10-25T06:57:33Z",
            "channelId": "UCuAXFkgsw1L7xaCfnd5JJOw",
            "channelTitle": "Rick Astley",
            "thumbnails": {
                "default": {"url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/default.jpg"},
                "medium": {"url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg"},
                "high": {"url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"},
            },
        },
        "contentDetails": {"duration": "PT3M33S"},
        "statistics": {"viewCount": "1234567890", "likeCount": "9876543"},
    }


@pytest.fixture
def sample_playlist_data():
    """Sample YouTube API playlist response data."""
    return {
        "id": "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf",
        "snippet": {
            "title": "Test Playlist",
            "description": "A test playlist",
            "channelId": "UCuAXFkgsw1L7xaCfnd5JJOw",
            "channelTitle": "Test Channel",
        },
        "contentDetails": {"itemCount": 2},
    }


@pytest.fixture
def sample_playlist_items():
    """Sample YouTube API playlist items response data."""
    return [
        {"snippet": {"title": "Video 1", "resourceId": {"videoId": "video1"}}},
        {"snippet": {"title": "Video 2", "resourceId": {"videoId": "video2"}}},
    ]


@pytest.fixture
def metadata_service(mock_youtube_api):
    """Create MetadataService instance with mocked YouTube API."""
    # Set required environment variable
    os.environ["YOUTUBE_API_KEY"] = "test_api_key"

    settings = ServiceSettings(port=8001)
    service = MetadataService("MetadataService", settings)

    # Replace the real YouTube API client with our mock
    service.youtube = mock_youtube_api

    yield service

    # Cleanup
    if "YOUTUBE_API_KEY" in os.environ:
        del os.environ["YOUTUBE_API_KEY"]


@pytest_asyncio.fixture
async def client(metadata_service):
    """Create test client for the metadata service."""
    async with AsyncClient(app=metadata_service.app, base_url="http://test") as client:
        yield client


class TestMetadataService:
    """Test cases for MetadataService."""

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_get_video_metadata_success(
        self,
        client: AsyncClient,
        metadata_service: MetadataService,
        sample_video_data: Dict[str, Any],
    ):
        """Test successful video metadata retrieval."""
        # Mock YouTube API response
        mock_response: Dict[str, Any] = {"items": [sample_video_data]}
        metadata_service.youtube.videos().list().execute.return_value = mock_response

        response = await client.get("/api/v1/metadata/video/dQw4w9WgXcQ")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["data"]["video_id"] == "dQw4w9WgXcQ"
        assert data["data"]["title"] == "Rick Astley - Never Gonna Give You Up"
        assert data["data"]["duration"] == 213  # 3m33s = 213 seconds
        assert data["data"]["channel_title"] == "Rick Astley"

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_get_video_metadata_not_found(
        self, client: AsyncClient, metadata_service: MetadataService
    ):
        """Test video not found scenario."""
        # Mock empty response (video not found)
        mock_response: Dict[str, Any] = {"items": []}
        metadata_service.youtube.videos().list().execute.return_value = mock_response

        response = await client.get("/api/v1/metadata/video/nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_get_video_metadata_quota_exceeded(
        self, client: AsyncClient, metadata_service: MetadataService
    ):
        """Test quota exceeded scenario."""
        # Set quota to maximum to simulate quota exceeded
        metadata_service.quota_used = (
            metadata_service.quota_limit - metadata_service.quota_reserve
        )

        response = await client.get("/api/v1/metadata/video/dQw4w9WgXcQ")
        assert response.status_code == 429
        assert "quota exceeded" in response.json()["detail"].lower()

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_get_video_metadata_api_error(
        self, client: AsyncClient, metadata_service: MetadataService
    ):
        """Test YouTube API error handling."""
        # Mock YouTube API error
        error_response = MagicMock()
        error_response.status = 403
        metadata_service.youtube.videos().list().execute.side_effect = HttpError(
            error_response, b"Forbidden"
        )

        response = await client.get("/api/v1/metadata/video/dQw4w9WgXcQ")
        assert response.status_code == 403

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_get_playlist_metadata_success(
        self,
        client: AsyncClient,
        metadata_service: MetadataService,
        sample_playlist_data: Dict[str, Any],
        sample_playlist_items: list,
    ):
        """Test successful playlist metadata retrieval."""
        # Mock playlist response
        playlist_response = {"items": [sample_playlist_data]}
        items_response = {"items": sample_playlist_items}

        metadata_service.youtube.playlists().list().execute.return_value = (
            playlist_response
        )
        metadata_service.youtube.playlistItems().list().execute.return_value = (
            items_response
        )

        response = await client.get(
            "/api/v1/metadata/playlist/PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["data"]["playlist_id"] == "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
        assert data["data"]["title"] == "Test Playlist"
        assert data["data"]["video_count"] == 2
        assert len(data["data"]["videos"]) == 2

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_get_playlist_metadata_not_found(
        self, client: AsyncClient, metadata_service: MetadataService
    ):
        """Test playlist not found scenario."""
        # Mock empty response
        mock_response: Dict[str, Any] = {"items": []}
        metadata_service.youtube.playlists().list().execute.return_value = mock_response

        response = await client.get("/api/v1/metadata/playlist/nonexistent")
        assert response.status_code == 404

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_batch_fetch_metadata_success(
        self,
        client: AsyncClient,
        metadata_service: MetadataService,
        sample_video_data: Dict[str, Any],
    ):
        """Test successful batch metadata fetching."""
        # Create multiple video data
        video_data_1 = sample_video_data.copy()
        video_data_1["id"] = "video1"
        video_data_2 = sample_video_data.copy()
        video_data_2["id"] = "video2"

        mock_response = {"items": [video_data_1, video_data_2]}
        metadata_service.youtube.videos().list().execute.return_value = mock_response

        request_data: Dict[str, Any] = {"video_ids": ["video1", "video2"]}
        response = await client.post("/api/v1/metadata/batch", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["metadata"]) == 2
        assert len(data["data"]["failed"]) == 0

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_batch_fetch_metadata_partial_failure(
        self,
        client: AsyncClient,
        metadata_service: MetadataService,
        sample_video_data: Dict[str, Any],
    ):
        """Test batch fetch with some videos unavailable."""
        # Mock response with only one video found
        video_data = sample_video_data.copy()
        video_data["id"] = "video1"
        mock_response = {"items": [video_data]}
        metadata_service.youtube.videos().list().execute.return_value = mock_response

        request_data: Dict[str, Any] = {"video_ids": ["video1", "nonexistent"]}
        response = await client.post("/api/v1/metadata/batch", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["metadata"]) == 1
        assert len(data["data"]["failed"]) == 1
        assert data["data"]["failed"][0]["video_id"] == "nonexistent"

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_batch_fetch_invalid_request(self, client: AsyncClient):
        """Test batch fetch with invalid request data."""
        # Empty video_ids list
        empty_request: Dict[str, Any] = {"video_ids": []}
        response = await client.post("/api/v1/metadata/batch", json=empty_request)
        assert response.status_code == 422

        # Too many video_ids
        large_request: Dict[str, Any] = {"video_ids": ["video"] * 51}
        response = await client.post("/api/v1/metadata/batch", json=large_request)
        assert response.status_code == 422

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_get_quota_status(
        self, client: AsyncClient, metadata_service: MetadataService
    ):
        """Test quota status endpoint."""
        # Set some quota usage
        metadata_service.quota_used = 2500

        response = await client.get("/api/v1/metadata/quota")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["data"]["quota_limit"] == 10000
        assert data["data"]["quota_used"] == 2500
        assert data["data"]["quota_remaining"] == 7500

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_caching_video_metadata(
        self,
        client: AsyncClient,
        metadata_service: MetadataService,
        sample_video_data: Dict[str, Any],
    ):
        """Test that video metadata is properly cached."""
        mock_response = {"items": [sample_video_data]}
        metadata_service.youtube.videos().list().execute.return_value = mock_response

        # First call should hit the API
        response1 = await client.get("/api/v1/metadata/video/dQw4w9WgXcQ")
        assert response1.status_code == 200

        # Second call should use cache (API not called again)
        metadata_service.youtube.videos().list().execute.reset_mock()
        response2 = await client.get("/api/v1/metadata/video/dQw4w9WgXcQ")
        assert response2.status_code == 200

        # Verify API was not called second time
        metadata_service.youtube.videos().list().execute.assert_not_called()

        # Verify responses are identical
        assert response1.json() == response2.json()

    def test_duration_parsing(self, metadata_service: MetadataService):
        """Test YouTube duration string parsing."""
        assert metadata_service._parse_duration("PT3M33S") == 213  # 3m33s
        assert metadata_service._parse_duration("PT1H2M3S") == 3723  # 1h2m3s
        assert metadata_service._parse_duration("PT45S") == 45  # 45s
        assert metadata_service._parse_duration("PT2M") == 120  # 2m
        assert metadata_service._parse_duration("PT1H") == 3600  # 1h
        assert metadata_service._parse_duration("PT") == 0  # empty

    def test_error_handling_missing_api_key(self):
        """Test error handling when API key is missing."""
        # Ensure API key is not set
        if "YOUTUBE_API_KEY" in os.environ:
            del os.environ["YOUTUBE_API_KEY"]

        settings = ServiceSettings(port=8001)

        with pytest.raises(ValueError, match="YOUTUBE_API_KEY"):
            MetadataService("MetadataService", settings)

    def test_quota_management_edge_cases(self, metadata_service: MetadataService):
        """Test quota management edge cases."""
        # Test quota check at limit
        metadata_service.quota_used = (
            metadata_service.quota_limit - metadata_service.quota_reserve - 1
        )
        assert metadata_service._check_quota(1) is True
        assert metadata_service._check_quota(2) is False

        # Test quota usage tracking
        initial_used = metadata_service.quota_used
        metadata_service._use_quota(5)
        assert metadata_service.quota_used == initial_used + 5

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_cache_expiration(self, metadata_service: MetadataService):
        """Test cache entry expiration."""
        from services.metadata.main import CacheEntry

        # Create cache entry with very short TTL
        entry = CacheEntry("test_data", 1)  # 1 second (int required)
        assert not entry.is_expired()

        # Wait for expiration
        await asyncio.sleep(1.1)
        assert entry.is_expired()

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_private_video_handling(
        self,
        client: AsyncClient,
        metadata_service: MetadataService,
        sample_playlist_data: Dict[str, Any],
    ):
        """Test handling of private videos in playlists."""
        # Mock playlist with private video
        private_items = [
            {
                "snippet": {
                    "title": "Private video",
                    "resourceId": {"videoId": "private1"},
                }
            },
            {
                "snippet": {
                    "title": "Public video",
                    "resourceId": {"videoId": "public1"},
                }
            },
        ]

        playlist_response = {"items": [sample_playlist_data]}
        items_response = {"items": private_items}

        metadata_service.youtube.playlists().list().execute.return_value = (
            playlist_response
        )
        metadata_service.youtube.playlistItems().list().execute.return_value = (
            items_response
        )

        response = await client.get(
            "/api/v1/metadata/playlist/PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
        )
        assert response.status_code == 200

        data = response.json()
        videos = data["data"]["videos"]

        # Check that private video is marked as unavailable
        private_video = next(v for v in videos if v["video_id"] == "private1")
        public_video = next(v for v in videos if v["video_id"] == "public1")

        assert private_video["is_available"] is False
        assert public_video["is_available"] is True
