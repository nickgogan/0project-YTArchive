"""Download Service for YouTube video downloads using yt-dlp."""

import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yt_dlp
from fastapi import HTTPException, status
from pydantic import BaseModel, Field

from services.common.base import BaseService, ServiceSettings
from services.common.models import ServiceResponse
from services.common.utils import retry_with_backoff


class DownloadStatus(str, Enum):
    """Enum for download task status."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class DownloadRequest(BaseModel):
    """Request model for starting a video download."""

    video_id: str
    quality: str = "1080p"  # "best", "1080p", "720p", "480p", "360p", "audio"
    output_path: str
    include_captions: bool = True
    caption_languages: List[str] = Field(default_factory=lambda: ["en"])
    resume: bool = True  # Resume partial downloads


class DownloadTask(BaseModel):
    """Model for download task information."""

    task_id: str
    video_id: str
    status: DownloadStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output_path: str
    file_path: Optional[str] = None
    error: Optional[str] = None


class DownloadProgress(BaseModel):
    """Model for download progress information."""

    task_id: str
    video_id: str
    status: DownloadStatus
    progress_percent: float
    downloaded_bytes: int
    total_bytes: Optional[int] = None
    speed: Optional[float] = None  # bytes/sec
    eta: Optional[int] = None  # seconds
    file_path: Optional[str] = None
    error: Optional[str] = None


class VideoFormat(BaseModel):
    """Model for video format information from yt-dlp."""

    format_id: str
    ext: str
    resolution: Optional[str] = None
    fps: Optional[int] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    filesize: Optional[int] = None
    format_note: Optional[str] = None


class AvailableFormats(BaseModel):
    """Model for available video formats response."""

    video_id: str
    formats: List[VideoFormat]
    best_format: str
    requested_quality: Optional[str] = None


class DownloadService(BaseService):
    """Service for managing YouTube video downloads with yt-dlp."""

    def __init__(self, service_name: str, settings: ServiceSettings):
        super().__init__(service_name, settings)

        # Quality format mapping for yt-dlp
        self.quality_map = {
            "best": "bestvideo+bestaudio/best",
            "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
            "audio": "bestaudio/best",
        }

        # Download management
        self.active_tasks: Dict[str, DownloadTask] = {}
        self.task_progress: Dict[str, DownloadProgress] = {}
        self.background_tasks: Dict[str, asyncio.Task] = {}  # Track background tasks
        self.max_concurrent_downloads = 3
        self.download_semaphore = asyncio.Semaphore(self.max_concurrent_downloads)

        # Add API routes
        self._add_download_routes()

    def _add_download_routes(self):
        """Add download-specific API routes."""

        @self.app.post("/api/v1/download/video", tags=["Download"])
        async def start_video_download(request: DownloadRequest):
            """Start a video download task."""
            try:
                task = await self._create_download_task(request)
                # Start download in background and track the task
                bg_task = asyncio.create_task(self._process_download(task))
                self.background_tasks[task.task_id] = bg_task
                return ServiceResponse(success=True, data=task.model_dump())
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to start download: {str(e)}",
                )

        @self.app.get("/api/v1/download/progress/{task_id}", tags=["Download"])
        async def get_download_progress(task_id: str):
            """Get progress information for a download task."""
            try:
                progress = await self._get_task_progress(task_id)
                return ServiceResponse(success=True, data=progress.model_dump())
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to get progress: {str(e)}",
                )

        @self.app.post("/api/v1/download/cancel/{task_id}", tags=["Download"])
        async def cancel_download(task_id: str):
            """Cancel an active download task."""
            try:
                result = await self._cancel_download_task(task_id)
                return ServiceResponse(success=True, data=result)
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to cancel download: {str(e)}",
                )

        @self.app.get("/api/v1/download/formats/{video_id}", tags=["Download"])
        async def get_available_formats(video_id: str):
            """Get available formats for a video."""
            try:
                formats = await self._get_video_formats(video_id)
                return ServiceResponse(success=True, data=formats.model_dump())
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to get formats: {str(e)}",
                )

    async def _create_download_task(self, request: DownloadRequest) -> DownloadTask:
        """Create a new download task."""
        task_id = str(uuid.uuid4())

        # Validate quality
        if request.quality not in self.quality_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid quality: {request.quality}. Available: {list(self.quality_map.keys())}",
            )

        # Create output directory
        output_path = Path(request.output_path).expanduser()
        output_path.mkdir(parents=True, exist_ok=True)

        task = DownloadTask(
            task_id=task_id,
            video_id=request.video_id,
            status=DownloadStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            output_path=str(output_path),
        )

        # Initialize progress tracking
        progress = DownloadProgress(
            task_id=task_id,
            video_id=request.video_id,
            status=DownloadStatus.PENDING,
            progress_percent=0.0,
            downloaded_bytes=0,
        )

        self.active_tasks[task_id] = task
        self.task_progress[task_id] = progress

        return task

    async def _process_download(self, task: DownloadTask):
        """Process a download task asynchronously."""
        async with self.download_semaphore:
            try:
                # Update status to downloading
                task.status = DownloadStatus.DOWNLOADING
                task.started_at = datetime.now(timezone.utc)
                self.task_progress[task.task_id].status = DownloadStatus.DOWNLOADING

                # Perform the download
                await self._download_video(task)

                # Mark as completed
                task.status = DownloadStatus.COMPLETED
                task.completed_at = datetime.now(timezone.utc)
                self.task_progress[task.task_id].status = DownloadStatus.COMPLETED
                self.task_progress[task.task_id].progress_percent = 100.0

            except Exception as e:
                # Mark as failed
                task.status = DownloadStatus.FAILED
                task.error = str(e)
                self.task_progress[task.task_id].status = DownloadStatus.FAILED
                self.task_progress[task.task_id].error = str(e)
            finally:
                # Clean up background task reference
                self.background_tasks.pop(task.task_id, None)

    async def _download_video(self, task: DownloadTask):
        """Download video using yt-dlp."""
        output_path = Path(task.output_path)
        video_url = f"https://www.youtube.com/watch?v={task.video_id}"

        # Create progress callback
        def progress_hook(d):
            if d["status"] == "downloading":
                progress = self.task_progress[task.task_id]
                progress.downloaded_bytes = d.get("downloaded_bytes", 0)
                progress.total_bytes = d.get("total_bytes") or d.get(
                    "total_bytes_estimate"
                )
                progress.speed = d.get("speed")
                progress.eta = d.get("eta")

                # Calculate progress percentage
                if progress.total_bytes and progress.total_bytes > 0:
                    progress.progress_percent = (
                        progress.downloaded_bytes / progress.total_bytes
                    ) * 100

            elif d["status"] == "finished":
                progress = self.task_progress[task.task_id]
                progress.file_path = d.get("filename")
                task.file_path = d.get("filename")

        # Configure yt-dlp options
        ydl_opts = {
            "format": self.quality_map.get("1080p"),  # Default to 1080p
            "outtmpl": str(output_path / f"{task.video_id}.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "writesubtitles": True,
            "subtitleslangs": ["en"],
            "subtitlesformat": "vtt",
            "writethumbnail": True,
            "merge_output_format": "mp4",
            "postprocessors": [
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "mp4",
                }
            ],
            "progress_hooks": [progress_hook],
        }

        # Run yt-dlp in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._run_ytdlp, video_url, ydl_opts)

    def _run_ytdlp(self, url: str, opts: Dict[str, Any]):
        """Run yt-dlp synchronously in thread pool."""
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

    async def _get_task_progress(self, task_id: str) -> DownloadProgress:
        """Get progress for a download task."""
        if task_id not in self.task_progress:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found",
            )

        return self.task_progress[task_id]

    async def _cancel_download_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel a download task."""
        if task_id not in self.active_tasks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found",
            )

        task = self.active_tasks[task_id]

        if task.status in [
            DownloadStatus.COMPLETED,
            DownloadStatus.FAILED,
            DownloadStatus.CANCELLED,
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel task in {task.status} status",
            )

        # Cancel the background task if it exists
        bg_task = self.background_tasks.get(task_id)
        if bg_task and not bg_task.done():
            bg_task.cancel()

        # Update status
        task.status = DownloadStatus.CANCELLED
        self.task_progress[task_id].status = DownloadStatus.CANCELLED

        # Clean up background task reference
        self.background_tasks.pop(task_id, None)

        return {
            "task_id": task_id,
            "status": "cancelled",
            "message": "Download cancelled successfully",
        }

    @retry_with_backoff(retries=3, base_delay=1.0)
    async def _get_video_formats(self, video_id: str) -> AvailableFormats:
        """Get available formats for a video using yt-dlp."""
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        # Run yt-dlp info extraction in thread pool
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, self._extract_info, video_url, ydl_opts)

        if not info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video {video_id} not found or unavailable",
            )

        # Parse formats
        formats = []
        for fmt in info.get("formats", []):
            formats.append(
                VideoFormat(
                    format_id=fmt.get("format_id", ""),
                    ext=fmt.get("ext", ""),
                    resolution=fmt.get("resolution"),
                    fps=fmt.get("fps"),
                    vcodec=fmt.get("vcodec"),
                    acodec=fmt.get("acodec"),
                    filesize=fmt.get("filesize"),
                    format_note=fmt.get("format_note"),
                )
            )

        return AvailableFormats(
            video_id=video_id,
            formats=formats,
            best_format=info.get("format_id", "best"),
        )

    def _extract_info(self, url: str, opts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract video info using yt-dlp synchronously."""
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception:
            return None

    async def cleanup_pending_tasks(self):
        """Clean up any pending background tasks. Useful for testing."""
        for task_id, bg_task in list(self.background_tasks.items()):
            if not bg_task.done():
                bg_task.cancel()
                try:
                    await bg_task
                except asyncio.CancelledError:
                    pass
        self.background_tasks.clear()


if __name__ == "__main__":
    settings = ServiceSettings(port=8002)  # Port for download service
    service = DownloadService("DownloadService", settings)
    service.run()
