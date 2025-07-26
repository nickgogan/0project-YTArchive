"""Storage Service for managing file system organization and metadata storage."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from pydantic import BaseModel

from services.common.base import BaseService, ServiceSettings
from services.common.models import (
    ServiceResponse,
    UnavailableVideo,
    FailedDownload,
)


class SaveMetadataRequest(BaseModel):
    """Request model for saving video metadata."""

    video_id: str
    metadata: Dict[str, Any]


class SaveVideoRequest(BaseModel):
    """Request model for saving video information."""

    video_id: str
    video_path: str
    thumbnail_path: Optional[str] = None
    captions: Dict[str, str] = {}  # language -> path
    file_size: int
    download_completed_at: datetime


class VideoExistence(BaseModel):
    """Model for video existence check response."""

    exists: bool
    has_video: bool = False
    has_metadata: bool = False
    has_thumbnail: bool = False
    has_captions: List[str] = []
    paths: Dict[str, Optional[str]] = {}
    last_modified: Optional[datetime] = None


class RecoveryPlanRequest(BaseModel):
    """Request model for generating recovery plans."""

    unavailable_videos: List[UnavailableVideo] = []
    failed_downloads: List[FailedDownload] = []


class StorageStats(BaseModel):
    """Model for storage statistics."""

    total_videos: int
    total_size_bytes: int
    total_size_human: str
    metadata_count: int
    video_count: int
    thumbnail_count: int
    caption_count: int
    disk_usage: Dict[str, Any]
    oldest_file: Optional[datetime] = None
    newest_file: Optional[datetime] = None


class StorageService(BaseService):
    """Storage Service for managing archived content organization."""

    def __init__(self, service_name: str, settings: ServiceSettings):
        super().__init__(service_name, settings)

        # Initialize paths from configuration
        self.base_output_dir = Path("~/YTArchive").expanduser()
        self.metadata_dir = self.base_output_dir / "metadata"
        self.videos_dir = self.base_output_dir / "videos"
        self.recovery_plans_dir = Path("logs/recovery_plans")

        # Create directories
        self._ensure_directories()

        # Add API routes
        self._add_storage_routes()

    def _ensure_directories(self):
        """Create necessary directory structure."""
        directories = [
            self.metadata_dir / "videos",
            self.metadata_dir / "playlists",
            self.videos_dir,
            self.recovery_plans_dir,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def _add_storage_routes(self):
        """Add storage-specific API routes."""

        @self.app.post("/api/v1/storage/save/metadata", tags=["Storage"])
        async def save_metadata(request: SaveMetadataRequest):
            """Save video metadata to storage."""
            try:
                result = await self._save_metadata(request.video_id, request.metadata)
                return ServiceResponse(success=True, data=result)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to save metadata: {str(e)}",
                )

        @self.app.post("/api/v1/storage/save/video", tags=["Storage"])
        async def save_video_info(request: SaveVideoRequest):
            """Save video file information to storage."""
            try:
                result = await self._save_video_info(request)
                return ServiceResponse(success=True, data=result)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to save video info: {str(e)}",
                )

        @self.app.get("/api/v1/storage/exists/{video_id}", tags=["Storage"])
        async def check_video_exists(video_id: str):
            """Check if video exists in storage."""
            try:
                result = await self._check_video_exists(video_id)
                return ServiceResponse(success=True, data=result.model_dump())
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to check video existence: {str(e)}",
                )

        @self.app.get("/api/v1/storage/metadata/{video_id}", tags=["Storage"])
        async def get_stored_metadata(video_id: str):
            """Get stored metadata for a video."""
            try:
                result = await self._get_stored_metadata(video_id)
                return ServiceResponse(success=True, data=result)
            except HTTPException:
                raise  # Re-raise HTTPExceptions (like 404)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to get metadata: {str(e)}",
                )

        @self.app.post("/api/v1/storage/recovery", tags=["Storage"])
        async def generate_recovery_plan(request: RecoveryPlanRequest):
            """Generate recovery plan for failed or unavailable videos."""
            try:
                result = await self._generate_recovery_plan(
                    request.unavailable_videos, request.failed_downloads
                )
                return ServiceResponse(success=True, data=result)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to generate recovery plan: {str(e)}",
                )

        @self.app.get("/api/v1/storage/stats", tags=["Storage"])
        async def get_storage_stats():
            """Get storage statistics."""
            try:
                result = await self._get_storage_stats()
                return ServiceResponse(success=True, data=result.model_dump())
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to get storage stats: {str(e)}",
                )

    async def _save_metadata(
        self, video_id: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Save video metadata to file system."""
        metadata_file = self.metadata_dir / "videos" / f"{video_id}.json"

        # Add storage timestamp
        metadata_with_timestamp = {
            **metadata,
            "storage_info": {
                "stored_at": datetime.now(timezone.utc).isoformat(),
                "video_id": video_id,
            },
        }

        # Write metadata file
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata_with_timestamp, f, indent=2, ensure_ascii=False)

        return {
            "path": str(metadata_file),
            "size_bytes": metadata_file.stat().st_size,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _save_video_info(self, request: SaveVideoRequest) -> Dict[str, Any]:
        """Save video file information."""
        video_dir = self.videos_dir / request.video_id
        video_dir.mkdir(exist_ok=True)

        # Create video info file
        video_info = {
            "video_id": request.video_id,
            "video_path": request.video_path,
            "thumbnail_path": request.thumbnail_path,
            "captions": request.captions,
            "file_size": request.file_size,
            "download_completed_at": request.download_completed_at.isoformat(),
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }

        info_file = video_dir / f"{request.video_id}_info.json"
        with open(info_file, "w", encoding="utf-8") as f:
            json.dump(video_info, f, indent=2)

        return {
            "video_dir": str(video_dir),
            "info_file": str(info_file),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _check_video_exists(self, video_id: str) -> VideoExistence:
        """Check if video and related files exist."""
        metadata_file = self.metadata_dir / "videos" / f"{video_id}.json"
        video_dir = self.videos_dir / video_id

        existence = VideoExistence(exists=False)
        paths: Dict[str, Optional[str]] = {}

        # Check metadata
        if metadata_file.exists():
            existence.has_metadata = True
            paths["metadata"] = str(metadata_file)
            existence.last_modified = datetime.fromtimestamp(
                metadata_file.stat().st_mtime, tz=timezone.utc
            )

        # Check video directory and files
        if video_dir.exists():
            video_file = video_dir / f"{video_id}.mp4"
            thumbnail_file = video_dir / f"{video_id}_thumb.jpg"
            captions_dir = video_dir / "captions"

            if video_file.exists():
                existence.has_video = True
                paths["video"] = str(video_file)

            if thumbnail_file.exists():
                existence.has_thumbnail = True
                paths["thumbnail"] = str(thumbnail_file)

            # Check for caption files
            if captions_dir.exists():
                caption_files = list(captions_dir.glob(f"{video_id}_*.vtt"))
                for caption_file in caption_files:
                    # Extract language from filename
                    lang = caption_file.stem.split("_")[-1]
                    existence.has_captions.append(lang)
                    paths[f"caption_{lang}"] = str(caption_file)

        existence.exists = existence.has_metadata or existence.has_video
        existence.paths = paths

        return existence

    async def _get_stored_metadata(self, video_id: str) -> Dict[str, Any]:
        """Get stored metadata for a video."""
        metadata_file = self.metadata_dir / "videos" / f"{video_id}.json"

        if not metadata_file.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Metadata not found for video {video_id}",
            )

        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        # Also get video info if available
        video_dir = self.videos_dir / video_id
        info_file = video_dir / f"{video_id}_info.json"

        storage_info = metadata.get("storage_info", {})
        if info_file.exists():
            with open(info_file, "r", encoding="utf-8") as f:
                video_info = json.load(f)
                storage_info.update(video_info)

        return {
            "video_id": video_id,
            "metadata": metadata,
            "storage_info": storage_info,
        }

    async def _generate_recovery_plan(
        self,
        unavailable_videos: List[UnavailableVideo],
        failed_downloads: List[FailedDownload],
    ) -> Dict[str, Any]:
        """Generate recovery plan for failed or unavailable content."""
        now = datetime.now(timezone.utc)
        plan_id = now.strftime("%Y%m%d_%H%M%S")

        recovery_plan = {
            "plan_id": plan_id,
            "created_at": now.isoformat(),
            "unavailable_videos": [
                video.model_dump(mode="json") for video in unavailable_videos
            ],
            "failed_downloads": [
                download.model_dump(mode="json") for download in failed_downloads
            ],
            "total_videos": len(unavailable_videos) + len(failed_downloads),
            "unavailable_count": len(unavailable_videos),
            "failed_count": len(failed_downloads),
            "notes": f"Generated recovery plan for {len(unavailable_videos)} unavailable and {len(failed_downloads)} failed videos",
        }

        plan_file = self.recovery_plans_dir / f"{plan_id}_plan.json"
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(recovery_plan, f, indent=2)

        return {
            "plan_id": plan_id,
            "path": str(plan_file),
            "total_videos": recovery_plan["total_videos"],
            "unavailable_count": recovery_plan["unavailable_count"],
            "failed_count": recovery_plan["failed_count"],
        }

    async def _get_storage_stats(self) -> StorageStats:
        """Get comprehensive storage statistics."""
        metadata_files = list((self.metadata_dir / "videos").glob("*.json"))
        video_dirs = [d for d in self.videos_dir.iterdir() if d.is_dir()]

        total_size = 0
        video_count = 0
        thumbnail_count = 0
        caption_count = 0
        oldest_file = None
        newest_file = None

        # Calculate statistics
        for video_dir in video_dirs:
            video_file = video_dir / f"{video_dir.name}.mp4"
            thumbnail_file = video_dir / f"{video_dir.name}_thumb.jpg"
            captions_dir = video_dir / "captions"

            if video_file.exists():
                video_count += 1
                total_size += video_file.stat().st_size
                mtime = datetime.fromtimestamp(
                    video_file.stat().st_mtime, tz=timezone.utc
                )
                if oldest_file is None or mtime < oldest_file:
                    oldest_file = mtime
                if newest_file is None or mtime > newest_file:
                    newest_file = mtime

            if thumbnail_file.exists():
                thumbnail_count += 1
                total_size += thumbnail_file.stat().st_size

            if captions_dir.exists():
                caption_files = list(captions_dir.glob("*.vtt"))
                caption_count += len(caption_files)
                for caption_file in caption_files:
                    total_size += caption_file.stat().st_size

        # Get disk usage
        disk_usage = {}
        try:
            statvfs = os.statvfs(self.base_output_dir)
            total_bytes = statvfs.f_frsize * statvfs.f_blocks
            free_bytes = statvfs.f_frsize * statvfs.f_bavail
            used_bytes = total_bytes - free_bytes

            disk_usage = {
                "used_bytes": used_bytes,
                "free_bytes": free_bytes,
                "total_bytes": total_bytes,
                "usage_percent": round((used_bytes / total_bytes) * 100, 2)
                if total_bytes > 0
                else 0,
            }
        except (AttributeError, OSError):
            # Fallback for systems without statvfs
            disk_usage = {
                "used_bytes": 0,
                "free_bytes": 0,
                "total_bytes": 0,
                "usage_percent": 0,
            }

        # Format human readable size
        def format_bytes(bytes_value):
            for unit in ["B", "KB", "MB", "GB", "TB"]:
                if bytes_value < 1024.0:
                    return f"{bytes_value:.1f} {unit}"
                bytes_value /= 1024.0
            return f"{bytes_value:.1f} PB"

        return StorageStats(
            total_videos=len(video_dirs),
            total_size_bytes=total_size,
            total_size_human=format_bytes(total_size),
            metadata_count=len(metadata_files),
            video_count=video_count,
            thumbnail_count=thumbnail_count,
            caption_count=caption_count,
            disk_usage=disk_usage,
            oldest_file=oldest_file,
            newest_file=newest_file,
        )


if __name__ == "__main__":
    settings = ServiceSettings(port=8003)  # Port for storage service
    service = StorageService("StorageService", settings)
    service.run()
