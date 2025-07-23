"""Metadata Service for YouTube API integration and metadata management."""

import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel, Field

from services.common.base import BaseService, ServiceSettings
from services.common.models import ServiceResponse
from services.common.utils import retry_with_backoff


class VideoMetadata(BaseModel):
    """Model for video metadata from YouTube API."""

    video_id: str
    title: str
    description: str
    duration: int  # seconds
    upload_date: datetime
    channel_id: str
    channel_title: str
    thumbnail_urls: Dict[str, str]  # quality -> url
    available_captions: List[str] = []  # language codes
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    fetched_at: datetime


class PlaylistVideo(BaseModel):
    """Model for a video within a playlist."""

    video_id: str
    position: int
    title: str
    duration: Optional[int] = None
    is_available: bool = True
    added_at: Optional[datetime] = None


class PlaylistMetadata(BaseModel):
    """Model for playlist metadata from YouTube API."""

    playlist_id: str
    title: str
    description: str
    channel_id: str
    channel_title: str
    video_count: int
    videos: List[PlaylistVideo]
    fetched_at: datetime


class BatchFetchRequest(BaseModel):
    """Request model for batch fetching video metadata."""

    video_ids: List[str] = Field(..., min_length=1, max_length=50)


class BatchFetchResponse(BaseModel):
    """Response model for batch fetching results."""

    metadata: List[VideoMetadata]
    failed: List[Dict[str, str]]


class QuotaStatus(BaseModel):
    """Model for YouTube API quota status."""

    quota_limit: int
    quota_used: int
    quota_remaining: int
    reset_time: datetime
    operations_available: Dict[str, int]


class CacheEntry:
    """Simple cache entry with TTL."""

    def __init__(self, data: Any, ttl_seconds: int):
        self.data = data
        self.expires_at = time.time() + ttl_seconds

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class MetadataService(BaseService):
    """Service for fetching and managing YouTube metadata."""

    def __init__(self, service_name: str, settings: ServiceSettings):
        super().__init__(service_name, settings)

        # Initialize YouTube API client
        self.api_key = self._get_api_key()
        self.youtube = build("youtube", "v3", developerKey=self.api_key)

        # Quota management
        self.quota_limit = 10000
        self.quota_used = 0
        self.quota_reserve = 1000
        self.quota_reset_time = self._get_next_reset_time()

        # Simple in-memory cache
        self.cache: Dict[str, CacheEntry] = {}
        self.video_cache_ttl = 3600  # 1 hour
        self.playlist_cache_ttl = 1800  # 30 minutes

        # Add API routes
        self._add_metadata_routes()

    def _get_api_key(self) -> str:
        """Get YouTube API key from environment."""
        import os

        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY environment variable is required")
        return api_key

    def _get_next_reset_time(self) -> datetime:
        """Calculate next quota reset time (midnight PST/PDT)."""
        now = datetime.now(timezone.utc)
        # YouTube quota resets at midnight Pacific Time
        # Simplified to next day at midnight UTC for this implementation
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=1
        )
        return tomorrow

    def _check_quota(self, required_units: int) -> bool:
        """Check if enough quota is available for the operation."""
        if self.quota_used + required_units > (self.quota_limit - self.quota_reserve):
            return False
        return True

    def _use_quota(self, units: int):
        """Track quota usage."""
        self.quota_used += units

    def _get_cache_key(self, cache_type: str, item_id: str) -> str:
        """Generate cache key."""
        return f"{cache_type}:{item_id}"

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get item from cache if not expired."""
        entry = self.cache.get(cache_key)
        if entry and not entry.is_expired():
            return entry.data
        elif entry:
            # Remove expired entry
            del self.cache[cache_key]
        return None

    def _set_cache(self, cache_key: str, data: Any, ttl_seconds: int):
        """Set item in cache with TTL."""
        self.cache[cache_key] = CacheEntry(data, ttl_seconds)

    def _add_metadata_routes(self):
        """Add metadata-specific API routes."""

        @self.app.get("/api/v1/metadata/video/{video_id}", tags=["Metadata"])
        async def get_video_metadata(video_id: str):
            """Get metadata for a single video."""
            try:
                result = await self._get_video_metadata(video_id)
                return ServiceResponse(success=True, data=result.model_dump())
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to get video metadata: {str(e)}",
                )

        @self.app.get("/api/v1/metadata/playlist/{playlist_id}", tags=["Metadata"])
        async def get_playlist_metadata(playlist_id: str):
            """Get metadata for a playlist."""
            try:
                result = await self._get_playlist_metadata(playlist_id)
                return ServiceResponse(success=True, data=result.model_dump())
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to get playlist metadata: {str(e)}",
                )

        @self.app.post("/api/v1/metadata/batch", tags=["Metadata"])
        async def batch_fetch_metadata(request: BatchFetchRequest):
            """Batch fetch metadata for multiple videos."""
            try:
                result = await self._batch_fetch_metadata(request.video_ids)
                return ServiceResponse(success=True, data=result.model_dump())
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to batch fetch metadata: {str(e)}",
                )

        @self.app.get("/api/v1/metadata/quota", tags=["Metadata"])
        async def get_quota_status():
            """Get current quota status."""
            try:
                result = await self._get_quota_status()
                return ServiceResponse(success=True, data=result.model_dump())
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to get quota status: {str(e)}",
                )

    @retry_with_backoff(retries=3, base_delay=1.0)
    async def _get_video_metadata(self, video_id: str) -> VideoMetadata:
        """Fetch metadata for a single video with caching."""
        cache_key = self._get_cache_key("video", video_id)

        # Check cache first
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return VideoMetadata(**cached_data)

        # Check quota
        if not self._check_quota(1):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="YouTube API quota exceeded",
            )

        try:
            # Fetch from YouTube API
            response = (
                self.youtube.videos()
                .list(part="snippet,contentDetails,status,statistics", id=video_id)
                .execute()
            )

            self._use_quota(1)

            if not response.get("items"):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Video {video_id} not found or unavailable",
                )

            video_data = response["items"][0]
            metadata = self._parse_video_metadata(video_data)

            # Cache the result
            self._set_cache(cache_key, metadata.model_dump(), self.video_cache_ttl)

            return metadata

        except HttpError as e:
            if e.resp.status == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="YouTube API quota exceeded or invalid API key",
                )
            elif e.resp.status == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Video {video_id} not found",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"YouTube API error: {str(e)}",
                )

    async def _get_playlist_metadata(self, playlist_id: str) -> PlaylistMetadata:
        """Fetch metadata for a playlist with caching."""
        cache_key = self._get_cache_key("playlist", playlist_id)

        # Check cache first
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return PlaylistMetadata(**cached_data)

        # Check quota (playlist + items call)
        if not self._check_quota(2):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="YouTube API quota exceeded",
            )

        try:
            # Fetch playlist info
            playlist_response = (
                self.youtube.playlists()
                .list(part="snippet,contentDetails", id=playlist_id)
                .execute()
            )

            if not playlist_response.get("items"):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Playlist {playlist_id} not found",
                )

            # Fetch playlist items
            items_response = (
                self.youtube.playlistItems()
                .list(
                    part="snippet,contentDetails", playlistId=playlist_id, maxResults=50
                )
                .execute()
            )

            self._use_quota(2)

            metadata = self._parse_playlist_metadata(
                playlist_response["items"][0], items_response.get("items", [])
            )

            # Cache the result
            self._set_cache(cache_key, metadata.model_dump(), self.playlist_cache_ttl)

            return metadata

        except HttpError as e:
            if e.resp.status == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="YouTube API quota exceeded or invalid API key",
                )
            elif e.resp.status == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Playlist {playlist_id} not found",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"YouTube API error: {str(e)}",
                )

    async def _batch_fetch_metadata(self, video_ids: List[str]) -> BatchFetchResponse:
        """Batch fetch metadata for multiple videos."""
        metadata_list = []
        failed_list = []

        # Process in chunks to stay within API limits
        chunk_size = 50
        for i in range(0, len(video_ids), chunk_size):
            chunk = video_ids[i : i + chunk_size]

            # Check quota for this chunk
            if not self._check_quota(1):
                # Add remaining videos to failed list
                for video_id in video_ids[i:]:
                    failed_list.append(
                        {"video_id": video_id, "error": "YouTube API quota exceeded"}
                    )
                break

            try:
                # Batch API call
                response = (
                    self.youtube.videos()
                    .list(
                        part="snippet,contentDetails,status,statistics",
                        id=",".join(chunk),
                    )
                    .execute()
                )

                self._use_quota(1)

                # Process successful results
                returned_videos = {
                    item["id"]: item for item in response.get("items", [])
                }

                for video_id in chunk:
                    if video_id in returned_videos:
                        try:
                            metadata = self._parse_video_metadata(
                                returned_videos[video_id]
                            )
                            metadata_list.append(metadata)

                            # Cache individual results
                            cache_key = self._get_cache_key("video", video_id)
                            self._set_cache(
                                cache_key, metadata.model_dump(), self.video_cache_ttl
                            )
                        except Exception as e:
                            failed_list.append(
                                {
                                    "video_id": video_id,
                                    "error": f"Failed to parse metadata: {str(e)}",
                                }
                            )
                    else:
                        failed_list.append(
                            {
                                "video_id": video_id,
                                "error": "Video not found or unavailable",
                            }
                        )

            except HttpError as e:
                # Add all videos in this chunk to failed list
                for video_id in chunk:
                    failed_list.append(
                        {"video_id": video_id, "error": f"YouTube API error: {str(e)}"}
                    )

        return BatchFetchResponse(metadata=metadata_list, failed=failed_list)

    async def _get_quota_status(self) -> QuotaStatus:
        """Get current quota status."""
        remaining = max(0, self.quota_limit - self.quota_used)

        return QuotaStatus(
            quota_limit=self.quota_limit,
            quota_used=self.quota_used,
            quota_remaining=remaining,
            reset_time=self.quota_reset_time,
            operations_available={
                "video_metadata": remaining,
                "playlist_metadata": remaining,
                "playlist_items": remaining,
                "captions": remaining // 50,
            },
        )

    def _parse_video_metadata(self, video_data: Dict[str, Any]) -> VideoMetadata:
        """Parse YouTube API video data into our VideoMetadata model."""
        snippet = video_data["snippet"]
        content_details = video_data["contentDetails"]
        statistics = video_data.get("statistics", {})

        # Parse duration from ISO 8601 format (PT4M13S -> 253 seconds)
        duration = self._parse_duration(content_details["duration"])

        # Parse upload date
        upload_date = datetime.fromisoformat(
            snippet["publishedAt"].replace("Z", "+00:00")
        )

        # Parse thumbnail URLs from nested structure
        thumbnail_urls = {}
        for quality, thumb_data in snippet["thumbnails"].items():
            thumbnail_urls[quality] = thumb_data["url"]

        return VideoMetadata(
            video_id=video_data["id"],
            title=snippet["title"],
            description=snippet["description"],
            duration=duration,
            upload_date=upload_date,
            channel_id=snippet["channelId"],
            channel_title=snippet["channelTitle"],
            thumbnail_urls=thumbnail_urls,
            view_count=int(statistics.get("viewCount", 0))
            if statistics.get("viewCount")
            else None,
            like_count=int(statistics.get("likeCount", 0))
            if statistics.get("likeCount")
            else None,
            fetched_at=datetime.now(timezone.utc),
        )

    def _parse_playlist_metadata(
        self, playlist_data: Dict[str, Any], items_data: List[Dict[str, Any]]
    ) -> PlaylistMetadata:
        """Parse YouTube API playlist data into our PlaylistMetadata model."""
        snippet = playlist_data["snippet"]
        content_details = playlist_data["contentDetails"]

        videos = []
        for i, item in enumerate(items_data):
            item_snippet = item["snippet"]
            videos.append(
                PlaylistVideo(
                    video_id=item_snippet["resourceId"]["videoId"],
                    position=i,
                    title=item_snippet["title"],
                    is_available=item_snippet.get("title") != "Private video",
                )
            )

        return PlaylistMetadata(
            playlist_id=playlist_data["id"],
            title=snippet["title"],
            description=snippet["description"],
            channel_id=snippet["channelId"],
            channel_title=snippet["channelTitle"],
            video_count=content_details["itemCount"],
            videos=videos,
            fetched_at=datetime.now(timezone.utc),
        )

    def _parse_duration(self, duration_str: str) -> int:
        """Parse ISO 8601 duration string to seconds."""
        import re

        # PT4M13S -> 4 minutes 13 seconds = 253 seconds
        pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
        match = re.match(pattern, duration_str)

        if not match:
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        return hours * 3600 + minutes * 60 + seconds


if __name__ == "__main__":
    settings = ServiceSettings(port=8001)  # Port for metadata service
    service = MetadataService("MetadataService", settings)
    service.run()
