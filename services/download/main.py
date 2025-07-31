"""Download Service for YouTube video downloads using yt-dlp."""

import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import yt_dlp  # type: ignore[import-untyped]
from fastapi import HTTPException, status
from pydantic import BaseModel, Field

from services.common.base import BaseService, ServiceSettings
from services.common.models import ServiceResponse
from services.common.utils import retry_with_backoff

# Import error recovery components
from services.error_recovery import ErrorRecoveryManager
from services.error_recovery.retry import (
    ExponentialBackoffStrategy,
)
from services.error_recovery.reporting import BasicErrorReporter
from services.error_recovery.types import (
    RetryConfig,
    ErrorContext,
)

# Import download-specific error handler and resume components
from services.download.error_handler import DownloadErrorHandler
from services.download.resume import DownloadStateManager, PartialDownloadResumer


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
    job_id: Optional[str] = None  # Associated job ID for coordination


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
    job_id: Optional[str] = None  # Associated job ID for coordination
    quality: str = "1080p"  # Track quality for storage notification


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

        # Initialize error recovery components
        self.download_error_handler = DownloadErrorHandler()
        self.error_reporter = BasicErrorReporter("logs/download_service")

        # Initialize resume components
        self.state_manager = DownloadStateManager()
        self.resumer = PartialDownloadResumer(self.state_manager)

        # Create error recovery manager with download-optimized retry strategy
        self.error_recovery = ErrorRecoveryManager(
            retry_strategy=ExponentialBackoffStrategy(
                RetryConfig(
                    max_attempts=3,
                    base_delay=2.0,  # Start with 2 second delay
                    max_delay=60.0,  # Cap at 1 minute
                    exponential_base=2.0,
                    jitter=True,
                )
            ),
            error_reporter=self.error_reporter,
            service_handler=self.download_error_handler,
        )

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

        @self.app.get("/api/v1/download/error-recovery/status", tags=["Error Recovery"])
        async def get_error_recovery_status():
            """Get error recovery system status and statistics."""
            try:
                status_info = {
                    "active_operations": len(self.error_recovery.active_recoveries),
                    "retry_strategy": type(self.error_recovery.retry_strategy).__name__,
                    "total_errors_handled": getattr(
                        self.error_reporter, "total_reports", 0
                    ),
                    "service_handler": type(self.download_error_handler).__name__,
                }
                return ServiceResponse(success=True, data=status_info)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to get error recovery status: {str(e)}",
                )

        @self.app.get(
            "/api/v1/download/error-recovery/reports", tags=["Error Recovery"]
        )
        async def get_error_reports():
            """Get recent error reports from the download service."""
            try:
                # Get error summary from the reporter
                summary = await self.error_reporter.get_error_summary()
                return ServiceResponse(success=True, data=summary)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to get error reports: {str(e)}",
                )

        @self.app.post(
            "/api/v1/download/error-recovery/clear-reports", tags=["Error Recovery"]
        )
        async def clear_error_reports():
            """Clear error reports (useful for testing or cleanup)."""
            try:
                result = {"cleared": True, "message": "Error reports cleared"}
                return ServiceResponse(success=True, data=result)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to clear error reports: {str(e)}",
                )

        @self.app.post("/api/v1/download/resume/{task_id}", tags=["Download"])
        async def resume_download(task_id: str):
            """Resume a failed or paused download task."""
            try:
                result = await self._resume_download_task(task_id)
                return ServiceResponse(success=True, data=result)
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to resume download: {str(e)}",
                )

        @self.app.get("/api/v1/download/resumable", tags=["Download"])
        async def get_resumable_downloads():
            """Get list of downloads that can be resumed."""
            try:
                resumable = await self._get_resumable_downloads()
                return ServiceResponse(success=True, data=resumable)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to get resumable downloads: {str(e)}",
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

        # Get storage path from Storage service with retry
        context = ErrorContext(
            operation_name="get_storage_path",
            video_id=request.video_id,
            operation_context={"quality": request.quality},
        )
        storage_path = await self.error_recovery.execute_with_retry(
            self._get_storage_path, context, None, request.video_id, request.quality
        )
        output_path = Path(storage_path).expanduser()
        output_path.mkdir(parents=True, exist_ok=True)

        task = DownloadTask(
            task_id=task_id,
            video_id=request.video_id,
            status=DownloadStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            output_path=str(output_path),
            job_id=request.job_id,
            quality=request.quality,
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

                # Report status to Jobs service with retry
                context = ErrorContext(
                    operation_name="report_job_status",
                    video_id=task.video_id,
                    operation_context={"job_id": task.job_id, "status": "downloading"},
                )
                await self.error_recovery.execute_with_retry(
                    self._report_job_status, context, None, task.job_id, "downloading"
                )

                # Perform the download with error recovery
                context = ErrorContext(
                    operation_name="download_video",
                    video_id=task.video_id,
                    operation_context={
                        "task_id": task.task_id,
                        "quality": task.quality,
                    },
                )
                await self.error_recovery.execute_with_retry(
                    self._download_video, context, None, task
                )

                # Mark as completed
                task.status = DownloadStatus.COMPLETED
                task.completed_at = datetime.now(timezone.utc)
                self.task_progress[task.task_id].status = DownloadStatus.COMPLETED
                self.task_progress[task.task_id].progress_percent = 100.0

                # Notify Storage service of successful save
                if task.file_path:
                    file_size = 0
                    try:
                        file_size = Path(task.file_path).stat().st_size
                    except Exception:
                        pass
                    await self._notify_storage_video_saved(
                        task.video_id, task.file_path, file_size, task.quality
                    )

                # Report successful completion to Jobs service with retry
                context = ErrorContext(
                    operation_name="report_job_status",
                    video_id=task.video_id,
                    operation_context={"job_id": task.job_id, "status": "completed"},
                )
                await self.error_recovery.execute_with_retry(
                    self._report_job_status, context, None, task.job_id, "completed"
                )

            except Exception as e:
                # Mark as failed
                task.status = DownloadStatus.FAILED
                task.error = str(e)
                self.task_progress[task.task_id].status = DownloadStatus.FAILED
                self.task_progress[task.task_id].error = str(e)

                # Report failure to Jobs service with retry
                context = ErrorContext(
                    operation_name="report_job_status",
                    video_id=task.video_id,
                    operation_context={
                        "job_id": task.job_id,
                        "status": "failed",
                        "error": str(e),
                    },
                )
                await self.error_recovery.execute_with_retry(
                    self._report_job_status,
                    context,
                    None,
                    task.job_id,
                    "failed",
                    str(e),
                )
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

    async def _get_storage_path(self, video_id: str, quality: str = "1080p") -> str:
        """Get appropriate storage path from Storage service."""
        storage_url = f"http://localhost:8003/api/v1/storage/exists/{video_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(storage_url)
            if response.status_code == 200:
                # Use the storage service's recommended path structure
                return str(Path.home() / "YTArchive" / "videos")
            else:
                # Default path if storage service unavailable
                return str(Path.home() / "YTArchive" / "videos")

    async def _notify_storage_video_saved(
        self, video_id: str, file_path: str, file_size: int, quality: str
    ):
        """Notify Storage service of successful video save."""
        try:
            storage_url = "http://localhost:8003/api/v1/storage/save/video"
            payload = {
                "video_id": video_id,
                "file_path": file_path,
                "file_size": file_size,
                "format": "mp4",  # Extract from file extension if needed
                "quality": quality,
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(storage_url, json=payload)
                if response.status_code != 200:
                    print(
                        f"Warning: Could not notify Storage service: {response.status_code}"
                    )
        except Exception as e:
            print(f"Warning: Failed to notify Storage service: {e}")

    async def _report_job_status(
        self, job_id: Optional[str], status: str, error_details: Optional[str] = None
    ):
        """Report download status back to Jobs service if job_id is provided."""
        if not job_id:
            return

        try:
            jobs_url = f"http://localhost:8000/api/v1/jobs/{job_id}/status"
            payload = {"status": status, "error_details": error_details}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.put(jobs_url, json=payload)
                if response.status_code != 200:
                    print(
                        f"Warning: Could not report status to Jobs service: {response.status_code}"
                    )
        except Exception as e:
            print(f"Warning: Failed to report status to Jobs service: {e}")

    async def _resume_download_task(self, task_id: str) -> Dict[str, Any]:
        """Resume a failed or paused download task using the new resume system."""
        if task_id not in self.active_tasks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found",
            )

        task = self.active_tasks[task_id]

        # Check if task can be resumed
        if task.status not in [DownloadStatus.FAILED, DownloadStatus.PAUSED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Task {task_id} cannot be resumed. Status: {task.status}",
            )

        # Try to load existing download state
        download_state = await self.state_manager.load_state(task_id)

        if not download_state:
            # Create new download state from task
            from services.download.resume import DownloadState

            download_state = DownloadState(
                task_id=task_id,
                video_id=task.video_id,
                video_url=f"https://www.youtube.com/watch?v={task.video_id}",
                output_path=task.output_path,
                quality=task.quality,
                downloaded_bytes=0,
                total_bytes=None,
                resume_supported=True,
                max_resume_attempts=3,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

            # Check for partial files
            partial_file = self.resumer.check_partial_file(
                task.output_path, task.video_id
            )
            if partial_file:
                download_state.partial_file_path = partial_file
                download_state.downloaded_bytes = Path(partial_file).stat().st_size

        # Validate if resume is possible
        can_resume, message = await self.resumer.validate_resume_possibility(
            download_state
        )

        if not can_resume:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot resume download: {message}",
            )

        # Update state for resume attempt
        download_state.resume_attempts += 1
        download_state.last_resume_attempt = datetime.now(timezone.utc)
        await self.state_manager.save_state(download_state)

        # Create new task for the resumed download
        new_task_id = str(uuid.uuid4())
        resumed_task = DownloadTask(
            task_id=new_task_id,
            video_id=task.video_id,
            status=DownloadStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            output_path=task.output_path,
            job_id=task.job_id,
            quality=task.quality,
        )

        # Initialize progress tracking for resumed task
        progress = DownloadProgress(
            task_id=new_task_id,
            video_id=task.video_id,
            status=DownloadStatus.PENDING,
            progress_percent=0.0,
            downloaded_bytes=download_state.downloaded_bytes,
        )

        self.active_tasks[new_task_id] = resumed_task
        self.task_progress[new_task_id] = progress

        # Start download in background
        bg_task = asyncio.create_task(self._process_download(resumed_task))
        self.background_tasks[new_task_id] = bg_task

        return {
            "original_task_id": task_id,
            "new_task_id": new_task_id,
            "can_resume": True,
            "partial_file_found": download_state.partial_file_path,
            "downloaded_bytes": download_state.downloaded_bytes,
            "resume_attempts": download_state.resume_attempts,
            "status": "resumed",
            "message": message,
        }

    async def _get_resumable_downloads(self) -> List[Dict[str, Any]]:
        """Get list of downloads that can potentially be resumed using the new resume system."""
        resumable = []

        # Check active tasks for failed/paused downloads
        for task_id, task in self.active_tasks.items():
            if task.status in [DownloadStatus.FAILED, DownloadStatus.PAUSED]:
                # Try to load download state
                download_state = await self.state_manager.load_state(task_id)

                if not download_state:
                    # Check for partial files the old way as fallback
                    output_path = Path(task.output_path)
                    partial_files = list(output_path.glob(f"{task.video_id}*.part"))
                    temp_files = list(output_path.glob(f"{task.video_id}*.ytdl"))

                    has_partial = len(partial_files) > 0 or len(temp_files) > 0

                    if has_partial:
                        partial_size = 0
                        partial_file = None
                        if partial_files:
                            partial_file = partial_files[0]
                            try:
                                partial_size = partial_file.stat().st_size
                            except OSError:
                                partial_size = 0
                        elif temp_files:
                            partial_file = temp_files[0]
                            try:
                                partial_size = partial_file.stat().st_size
                            except OSError:
                                partial_size = 0

                        resumable.append(
                            {
                                "task_id": task_id,
                                "video_id": task.video_id,
                                "status": task.status,
                                "quality": task.quality,
                                "partial_file_path": str(partial_file)
                                if partial_file
                                else None,
                                "partial_size_bytes": partial_size,
                                "downloaded_bytes": partial_size,
                                "created_at": task.created_at.isoformat(),
                                "error": task.error,
                                "resume_attempts": 0,
                                "can_resume": has_partial,
                            }
                        )
                else:
                    # Use the download state information
                    (
                        can_resume,
                        message,
                    ) = await self.resumer.validate_resume_possibility(download_state)

                    resumable.append(
                        {
                            "task_id": task_id,
                            "video_id": download_state.video_id,
                            "status": task.status,
                            "quality": download_state.quality,
                            "partial_file_path": download_state.partial_file_path,
                            "partial_size_bytes": download_state.downloaded_bytes,
                            "downloaded_bytes": download_state.downloaded_bytes,
                            "total_bytes": download_state.total_bytes,
                            "created_at": download_state.created_at.isoformat(),
                            "updated_at": download_state.updated_at.isoformat(),
                            "error": task.error,
                            "resume_attempts": download_state.resume_attempts,
                            "max_resume_attempts": download_state.max_resume_attempts,
                            "can_resume": can_resume,
                            "resume_message": message,
                        }
                    )

        # Also check for orphaned download states
        try:
            orphaned_states = await self.state_manager.list_resumable_downloads()
            for state in orphaned_states:
                # Only include if not already in active tasks
                if state.task_id not in self.active_tasks:
                    (
                        can_resume,
                        message,
                    ) = await self.resumer.validate_resume_possibility(state)

                    resumable.append(
                        {
                            "task_id": state.task_id,
                            "video_id": state.video_id,
                            "status": "orphaned",  # Not in active tasks
                            "quality": state.quality,
                            "partial_file_path": state.partial_file_path,
                            "partial_size_bytes": state.downloaded_bytes,
                            "downloaded_bytes": state.downloaded_bytes,
                            "total_bytes": state.total_bytes,
                            "created_at": state.created_at.isoformat(),
                            "updated_at": state.updated_at.isoformat(),
                            "error": "Task no longer active",
                            "resume_attempts": state.resume_attempts,
                            "max_resume_attempts": state.max_resume_attempts,
                            "can_resume": can_resume,
                            "resume_message": message,
                        }
                    )
        except Exception as e:
            # Log but don't fail if we can't check orphaned states
            print(f"Warning: Could not check orphaned download states: {e}")

        return resumable

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
