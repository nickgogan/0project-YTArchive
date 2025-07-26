"""Jobs Service for coordinating YouTube archiving tasks."""

import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, status
from pydantic import BaseModel

from services.common.base import BaseService, ServiceSettings
from services.common.models import (
    JobStatus,
    JobType,
    RegisteredService,
    ServiceRegistration,
)


class CreateJobRequest(BaseModel):
    """Request model for creating a new job."""

    job_type: JobType
    urls: List[str]
    options: Dict[str, Any] = {}


class JobResponse(BaseModel):
    """Response model for job operations."""

    job_id: str
    job_type: JobType
    status: JobStatus
    urls: List[str]
    created_at: str
    updated_at: str
    options: Dict[str, Any] = {}
    error_details: Optional[str] = None


class JobsService(BaseService):
    """Central service for managing and coordinating archiving jobs."""

    def __init__(self, service_name: str, settings: ServiceSettings):
        super().__init__(service_name, settings)
        self.jobs_dir = Path("jobs")
        self.registry_dir = Path("registry")
        self.jobs_dir.mkdir(exist_ok=True)
        self.registry_dir.mkdir(exist_ok=True)
        self._add_jobs_routes()
        self._add_registry_routes()

    def _add_jobs_routes(self):
        """Add job management routes."""

        @self.app.post("/api/v1/jobs", tags=["Jobs"], response_model=JobResponse)
        async def create_job(request: CreateJobRequest):
            """Create a new archiving job."""
            try:
                job = await self._create_job(request)
                return job
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create job: {str(e)}",
                )

        @self.app.get(
            "/api/v1/jobs/{job_id}", tags=["Jobs"], response_model=JobResponse
        )
        async def get_job(job_id: str):
            """Get job details by ID."""
            try:
                job = await self._get_job(job_id)
                if not job:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Job {job_id} not found",
                    )
                return job
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to get job: {str(e)}",
                )

        @self.app.get("/api/v1/jobs", tags=["Jobs"])
        async def list_jobs(
            status_filter: Optional[JobStatus] = None, limit: int = 100
        ):
            """List jobs with optional filtering."""
            try:
                jobs = await self._list_jobs(status_filter, limit)
                return {"jobs": jobs, "count": len(jobs)}
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to list jobs: {str(e)}",
                )

        @self.app.put(
            "/api/v1/jobs/{job_id}/execute", tags=["Jobs"], response_model=JobResponse
        )
        async def execute_job(job_id: str):
            """Execute a job by ID."""
            try:
                result = await self._execute_job(job_id)
                if not result:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Job {job_id} not found",
                    )
                return result
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to execute job: {str(e)}",
                )

    def _add_registry_routes(self):
        """Add service registry routes."""

        @self.app.post("/api/v1/registry/register", tags=["Registry"])
        async def register_service(registration: ServiceRegistration):
            """Register a service in the registry."""
            try:
                service = await self._register_service(registration)
                return {
                    "message": "Service registered successfully",
                    "service": service,
                }
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to register service: {str(e)}",
                )

        @self.app.get("/api/v1/registry/services", tags=["Registry"])
        async def list_services():
            """List all registered services."""
            try:
                services = await self._list_services()
                return {"services": services, "count": len(services)}
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to list services: {str(e)}",
                )

        @self.app.delete("/api/v1/registry/services/{service_name}", tags=["Registry"])
        async def unregister_service(service_name: str):
            """Unregister a service from the registry."""
            try:
                success = await self._unregister_service(service_name)
                if not success:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Service {service_name} not found",
                    )
                return {"message": f"Service {service_name} unregistered successfully"}
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to unregister service: {str(e)}",
                )

    async def _create_job(self, request: CreateJobRequest) -> JobResponse:
        """Create and persist a new job."""
        from datetime import datetime, timezone

        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        job_data = {
            "job_id": job_id,
            "job_type": request.job_type.value,
            "status": JobStatus.PENDING.value,
            "urls": request.urls,
            "created_at": now,
            "updated_at": now,
            "options": request.options,
        }

        # Save job to file
        job_file = self.jobs_dir / f"{job_id}.json"
        with open(job_file, "w") as f:
            json.dump(job_data, f, indent=2)

        return JobResponse(**job_data)

    async def _get_job(self, job_id: str) -> Optional[JobResponse]:
        """Retrieve a job by ID."""
        job_file = self.jobs_dir / f"{job_id}.json"
        if not job_file.exists():
            return None

        with open(job_file, "r") as f:
            job_data = json.load(f)

        return JobResponse(**job_data)

    async def _list_jobs(
        self, status_filter: Optional[JobStatus], limit: int
    ) -> List[JobResponse]:
        """List jobs with optional filtering."""
        jobs: List[JobResponse] = []

        for job_file in self.jobs_dir.glob("*.json"):
            if len(jobs) >= limit:
                break

            try:
                with open(job_file, "r") as f:
                    job_data = json.load(f)

                # Apply status filter if provided
                if status_filter and job_data["status"] != status_filter.value:
                    continue

                jobs.append(JobResponse(**job_data))
            except (json.JSONDecodeError, KeyError):
                # Skip malformed job files
                continue

        # Sort by created_at (newest first)
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        return jobs

    async def _execute_job(self, job_id: str) -> Optional[JobResponse]:
        """Execute a job with basic synchronous processing."""
        # Get the current job
        job = await self._get_job(job_id)
        if not job:
            return None

        # Check if job is already running or completed
        if job.status not in [JobStatus.PENDING, JobStatus.FAILED]:
            return job

        try:
            # Update job status to RUNNING
            updated_job = await self._update_job_status(job_id, JobStatus.RUNNING)
            if not updated_job:
                return None
            job = updated_job

            # Basic synchronous job execution logic
            await self._process_job(job)

            # Update job status to COMPLETED
            updated_job = await self._update_job_status(job_id, JobStatus.COMPLETED)
            if not updated_job:
                return None
            job = updated_job

        except Exception as e:
            # Update job status to FAILED on error
            failed_job = await self._update_job_status(job_id, JobStatus.FAILED, str(e))
            if failed_job:
                job = failed_job
            # Log the error (in a real implementation, we'd use our logging service)
            print(f"Job {job_id} failed with error: {str(e)}")

        return job

    async def _update_job_status(
        self, job_id: str, new_status: JobStatus, error_details: Optional[str] = None
    ) -> Optional[JobResponse]:
        """Update the status of a job and persist changes."""
        job_file = self.jobs_dir / f"{job_id}.json"
        if not job_file.exists():
            return None

        # Read current job data
        with open(job_file, "r") as f:
            job_data = json.load(f)

        # Update status and timestamp
        job_data["status"] = new_status.value
        job_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Add error details if provided
        if error_details:
            job_data["error_details"] = error_details

        # If job failed, add to work plan for tracking
        if new_status == JobStatus.FAILED:
            await self._add_to_work_plan(job_data, error_details)

        # Save updated job data
        with open(job_file, "w") as f:
            json.dump(job_data, f, indent=2)

        return JobResponse(**job_data)

    async def _update_job_progress(
        self, job_id: str, progress_data: Dict[str, Any]
    ) -> Optional[JobResponse]:
        """Update job progress data without changing status."""
        job_file = self.jobs_dir / f"{job_id}.json"
        if not job_file.exists():
            return None

        # Read current job data
        with open(job_file, "r") as f:
            job_data = json.load(f)

        # Update progress data and timestamp
        job_data["progress"] = progress_data
        job_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Save updated job data
        with open(job_file, "w") as f:
            json.dump(job_data, f, indent=2)

        return JobResponse(**job_data)

    async def _process_job(self, job: JobResponse):
        """Process a job by coordinating with appropriate services."""
        if job.job_type == JobType.VIDEO_DOWNLOAD:
            await self._process_video_download(job)
        elif job.job_type == JobType.PLAYLIST_DOWNLOAD:
            await self._process_playlist_download(job)
        elif job.job_type == JobType.METADATA_ONLY:
            await self._process_metadata_only(job)
        else:
            raise ValueError(f"Unknown job type: {job.job_type}")

    async def _process_video_download(self, job: JobResponse):
        """Process video download job by coordinating with Download and Storage services."""
        for url in job.urls:
            try:
                # Extract video ID from URL
                video_id = self._extract_video_id(url)
                if not video_id:
                    raise ValueError(f"Could not extract video ID from URL: {url}")

                # Get Storage service path for the video
                storage_path = await self._get_storage_path(video_id)

                # Start download via Download service
                download_result = await self._start_download(
                    video_id, storage_path, job.options
                )

                # Monitor download progress and wait for completion
                await self._monitor_download(download_result["task_id"])

                # Notify Storage service of successful video save
                await self._notify_storage_video_saved(video_id, storage_path)

                print(f"Successfully downloaded video {video_id} for job {job.job_id}")

            except Exception as e:
                print(f"Failed to download video from {url} in job {job.job_id}: {e}")
                raise  # Re-raise to mark job as failed

    async def _process_playlist_download(self, job: JobResponse):
        """Process playlist download job by expanding playlist and creating batch download jobs."""
        playlist_results = []
        total_videos_across_playlists = 0
        completed_videos = 0
        failed_videos = 0
        start_time = datetime.now(timezone.utc)

        # Initialize progress tracking
        await self._update_job_progress(
            job.job_id,
            {
                "phase": "initializing",
                "total_playlists": len(job.urls),
                "processed_playlists": 0,
                "total_videos": 0,
                "completed_videos": 0,
                "failed_videos": 0,
                "current_playlist": None,
                "start_time": start_time.isoformat(),
                "estimated_completion": None,
                "download_speed": 0.0,
                "current_phase_details": "Initializing playlist processing...",
            },
        )

        for playlist_index, url in enumerate(job.urls):
            try:
                # Extract playlist ID from URL
                playlist_id = self._extract_playlist_id(url)
                if not playlist_id:
                    raise ValueError(f"Could not extract playlist ID from URL: {url}")

                print(f"Processing playlist {playlist_id} for job {job.job_id}")

                # Update progress for metadata fetching
                await self._update_job_progress(
                    job.job_id,
                    {
                        "phase": "fetching_metadata",
                        "total_playlists": len(job.urls),
                        "processed_playlists": playlist_index,
                        "total_videos": total_videos_across_playlists,
                        "completed_videos": completed_videos,
                        "failed_videos": failed_videos,
                        "current_playlist": {
                            "id": playlist_id,
                            "url": url,
                            "status": "fetching_metadata",
                        },
                        "start_time": start_time.isoformat(),
                        "current_phase_details": f"Fetching metadata for playlist {playlist_id}...",
                    },
                )

                # Fetch playlist metadata via Metadata service
                playlist_metadata = await self._fetch_playlist_metadata(playlist_id)

                if not playlist_metadata or not playlist_metadata.get("videos"):
                    raise ValueError(f"Playlist {playlist_id} is empty or unavailable")

                videos = playlist_metadata["videos"]
                total_videos_across_playlists += len(videos)
                print(f"Found {len(videos)} videos in playlist {playlist_id}")

                # Update progress with total video count
                await self._update_job_progress(
                    job.job_id,
                    {
                        "phase": "creating_jobs",
                        "total_playlists": len(job.urls),
                        "processed_playlists": playlist_index,
                        "total_videos": total_videos_across_playlists,
                        "completed_videos": completed_videos,
                        "failed_videos": failed_videos,
                        "current_playlist": {
                            "id": playlist_id,
                            "title": playlist_metadata.get("title", "Unknown Playlist"),
                            "total_videos": len(videos),
                            "status": "creating_jobs",
                        },
                        "start_time": start_time.isoformat(),
                        "current_phase_details": f"Creating download jobs for {len(videos)} videos...",
                    },
                )

                # Create individual download jobs for each video
                video_jobs = await self._create_batch_video_jobs(
                    videos, job.options, f"playlist-{playlist_id}"
                )

                # Update progress for download execution
                await self._update_job_progress(
                    job.job_id,
                    {
                        "phase": "downloading",
                        "total_playlists": len(job.urls),
                        "processed_playlists": playlist_index,
                        "total_videos": total_videos_across_playlists,
                        "completed_videos": completed_videos,
                        "failed_videos": failed_videos,
                        "current_playlist": {
                            "id": playlist_id,
                            "title": playlist_metadata.get("title", "Unknown Playlist"),
                            "total_videos": len(videos),
                            "status": "downloading",
                        },
                        "start_time": start_time.isoformat(),
                        "current_phase_details": f"Downloading {len(videos)} videos from playlist...",
                    },
                )

                # Execute video downloads with concurrency control and progress tracking
                playlist_result = await self._execute_playlist_downloads_with_progress(
                    job.job_id,
                    video_jobs,
                    job.options.get("max_concurrent", 3),
                    playlist_index,
                    len(job.urls),
                    total_videos_across_playlists,
                    start_time,
                )

                # Update counters
                completed_videos += playlist_result["successful"]
                failed_videos += playlist_result["failed"]

                playlist_results.append(
                    {
                        "playlist_id": playlist_id,
                        "title": playlist_metadata.get("title", "Unknown Playlist"),
                        "total_videos": len(videos),
                        "successful_downloads": playlist_result["successful"],
                        "failed_downloads": playlist_result["failed"],
                        "video_jobs": video_jobs,
                    }
                )

                print(
                    f"Completed playlist {playlist_id}: {playlist_result['successful']}/{len(videos)} successful"
                )

            except Exception as e:
                print(f"Failed to process playlist from {url} in job {job.job_id}: {e}")
                playlist_results.append(
                    {
                        "playlist_url": url,
                        "error": str(e),
                        "total_videos": 0,
                        "successful_downloads": 0,
                        "failed_downloads": 0,
                    }
                )

        # Store playlist processing results for progress tracking
        await self._store_playlist_results(job.job_id, playlist_results)

        # Check if any playlist processing failed completely
        total_failed_playlists = sum(
            1 for result in playlist_results if "error" in result
        )
        if total_failed_playlists == len(playlist_results):
            raise Exception(f"All {total_failed_playlists} playlists failed to process")

    async def _process_metadata_only(self, job: JobResponse):
        """Process metadata-only job by fetching and storing metadata."""
        for url in job.urls:
            try:
                video_id = self._extract_video_id(url)
                if not video_id:
                    raise ValueError(f"Could not extract video ID from URL: {url}")

                # Fetch metadata via Metadata service
                metadata = await self._fetch_metadata(video_id)

                # Store metadata via Storage service
                await self._store_metadata(video_id, metadata)

                print(
                    f"Successfully processed metadata for video {video_id} in job {job.job_id}"
                )

            except Exception as e:
                print(f"Failed to process metadata for {url} in job {job.job_id}: {e}")
                raise

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        if "youtube.com/watch?v=" in url:
            return url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            return url.split("/")[-1].split("?")[0]
        return None

    def _extract_playlist_id(self, url: str) -> Optional[str]:
        """Extract playlist ID from YouTube URL."""
        if "youtube.com/playlist?list=" in url:
            return url.split("list=")[1].split("&")[0]
        elif "youtube.com/watch?" in url and "list=" in url:
            # Handle playlist URLs that also contain a video ID
            return url.split("list=")[1].split("&")[0]
        return None

    async def _get_storage_path(self, video_id: str) -> str:
        """Get appropriate storage path from Storage service."""
        try:
            storage_url = "http://localhost:8003/api/v1/storage/exists/" + video_id
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(storage_url)
                if response.status_code == 200:
                    # Use the storage service's recommended path structure
                    return str(Path.home() / "YTArchive" / "videos")
                else:
                    # Default path if storage service unavailable
                    return str(Path.home() / "YTArchive" / "videos")
        except Exception as e:
            print(f"Warning: Could not contact Storage service for path: {e}")
            return str(Path.home() / "YTArchive" / "videos")

    async def _start_download(
        self, video_id: str, output_path: str, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Start download via Download service."""
        download_url = "http://localhost:8002/api/v1/download/video"
        payload = {
            "video_id": video_id,
            "quality": options.get("quality", "1080p"),
            "output_path": output_path,
            "include_captions": options.get("include_captions", True),
            "caption_languages": options.get("caption_languages", ["en"]),
            "resume": options.get("resume", True),
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(download_url, json=payload)
            if response.status_code == 200:
                return response.json()["data"]
            else:
                raise Exception(
                    f"Download service error: {response.status_code} - {response.text}"
                )

    async def _monitor_download(self, task_id: str, timeout_seconds: int = 3600):
        """Monitor download progress until completion."""
        import time

        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            try:
                progress_url = (
                    f"http://localhost:8002/api/v1/download/progress/{task_id}"
                )
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(progress_url)
                    if response.status_code == 200:
                        progress = response.json()["data"]
                        status = progress["status"]

                        if status == "completed":
                            return  # Download successful
                        elif status == "failed":
                            error = progress.get("error", "Unknown download error")
                            raise Exception(f"Download failed: {error}")
                        elif status == "cancelled":
                            raise Exception("Download was cancelled")

                        # Still downloading, wait and check again
                        await asyncio.sleep(5)
                    else:
                        raise Exception(
                            f"Could not get download progress: {response.status_code}"
                        )
            except Exception as e:
                if "Download failed" in str(e) or "cancelled" in str(e):
                    raise
                # For other errors, wait and retry
                await asyncio.sleep(10)

        raise Exception(f"Download timeout after {timeout_seconds} seconds")

    async def _notify_storage_video_saved(self, video_id: str, file_path: str):
        """Notify Storage service that video was successfully saved."""
        try:
            storage_url = "http://localhost:8003/api/v1/storage/save/video"
            payload = {
                "video_id": video_id,
                "file_path": file_path,
                "file_size": 0,  # Would be filled by Download service in real implementation
                "format": "mp4",  # Default format
                "quality": "1080p",  # Would be passed from job options
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(storage_url, json=payload)
                if response.status_code == 200:
                    print(f"Notified Storage service of video save: {video_id}")
                else:
                    print(
                        f"Warning: Could not notify Storage service: {response.status_code}"
                    )
        except Exception as e:
            print(f"Warning: Failed to notify Storage service: {e}")

    async def _fetch_metadata(self, video_id: str) -> Dict[str, Any]:
        """Fetch metadata via Metadata service."""
        metadata_url = f"http://localhost:8001/api/v1/metadata/video/{video_id}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(metadata_url)
            if response.status_code == 200:
                return response.json()["data"]
            else:
                raise Exception(
                    f"Metadata service error: {response.status_code} - {response.text}"
                )

    async def _fetch_playlist_metadata(self, playlist_id: str) -> Dict[str, Any]:
        """Fetch playlist metadata via Metadata service."""
        metadata_url = f"http://localhost:8001/api/v1/metadata/playlist/{playlist_id}"
        async with httpx.AsyncClient(
            timeout=60.0
        ) as client:  # Longer timeout for playlists
            response = await client.get(metadata_url)
            if response.status_code == 200:
                json_data = await response.json()
                return json_data["data"]
            else:
                response_text = await response.text()
                raise Exception(
                    f"Playlist metadata service error: {response.status_code} - {response_text}"
                )

    async def _create_batch_video_jobs(
        self,
        videos: List[Dict[str, Any]],
        playlist_options: Dict[str, Any],
        batch_prefix: str,
    ) -> List[Dict[str, Any]]:
        """Create individual video download jobs for batch processing with large playlist optimizations."""
        video_jobs = []

        # Large playlist optimization: Dynamic concurrency and batch processing
        total_videos = len(videos)
        is_large_playlist = total_videos >= 100

        # Optimize processing based on playlist size
        if is_large_playlist:
            print(
                f"⚡ Large playlist detected ({total_videos} videos) - applying optimizations..."
            )

            # Process videos in chunks to manage memory usage
            chunk_size = min(50, max(10, total_videos // 10))  # Adaptive chunk size
            video_chunks = [
                videos[i : i + chunk_size] for i in range(0, total_videos, chunk_size)
            ]

            print(
                f"📦 Processing {total_videos} videos in {len(video_chunks)} chunks of ~{chunk_size} videos each"
            )

            for chunk_index, video_chunk in enumerate(video_chunks):
                print(
                    f"🔄 Processing chunk {chunk_index + 1}/{len(video_chunks)} ({len(video_chunk)} videos)"
                )

                chunk_jobs = await self._create_video_jobs_chunk(
                    video_chunk,
                    playlist_options,
                    batch_prefix,
                    chunk_index * chunk_size,
                    total_videos,
                )
                video_jobs.extend(chunk_jobs)

                # Brief pause between chunks to prevent overwhelming the system
                if chunk_index < len(video_chunks) - 1:
                    await asyncio.sleep(0.1)
        else:
            # Standard processing for smaller playlists
            video_jobs = await self._create_video_jobs_chunk(
                videos, playlist_options, batch_prefix, 0, total_videos
            )

        print(f"✅ Created {len(video_jobs)} video jobs for playlist {batch_prefix}")
        return video_jobs

    async def _create_video_jobs_chunk(
        self,
        videos: List[Dict[str, Any]],
        playlist_options: Dict[str, Any],
        batch_prefix: str,
        start_index: int,
        total_videos: int,
    ) -> List[Any]:
        """Create video jobs for a chunk of videos with optimized processing."""
        video_jobs = []

        # Concurrent job creation for better performance
        semaphore = asyncio.Semaphore(
            min(10, len(videos))
        )  # Limit concurrent job creation

        async def create_single_video_job(i: int, video: Dict[str, Any]):
            """Create a single video job with error handling."""
            async with semaphore:
                try:
                    video_id = video.get("video_id")
                    if not video_id:
                        print(
                            f"Warning: Video {start_index + i + 1} in playlist missing video_id, skipping"
                        )
                        return None

                    # Create video URL from video_id
                    video_url = f"https://www.youtube.com/watch?v={video_id}"

                    # Create job request for individual video
                    video_job_request = CreateJobRequest(
                        job_type=JobType.VIDEO_DOWNLOAD,
                        urls=[video_url],
                        options={
                            **playlist_options,  # Inherit playlist options
                            "playlist_context": {
                                "batch_prefix": batch_prefix,
                                "video_index": start_index + i + 1,
                                "total_videos": total_videos,
                                "video_title": video.get("title", "Unknown Title"),
                                "video_duration": video.get("duration_seconds", 0),
                            },
                        },
                    )

                    # Create the actual job
                    created_job = await self._create_job(video_job_request)

                    return {
                        "job_id": created_job.job_id,
                        "video_id": video_id,
                        "video_url": video_url,
                        "title": video.get("title", "Unknown Title"),
                        "duration": video.get("duration_seconds", 0),
                        "job_request": video_job_request,
                        "created_job": created_job,
                        "status": "created",
                    }

                except Exception as e:
                    print(
                        f"Failed to create job for video {start_index + i + 1}/{total_videos}: {e}"
                    )
                    return {
                        "video_id": video.get("video_id", f"unknown_{i}"),
                        "video_url": f"https://www.youtube.com/watch?v={video.get('video_id', '')}",
                        "title": video.get("title", "Unknown Title"),
                        "duration": video.get("duration_seconds", 0),
                        "status": "failed_creation",
                        "error": str(e),
                    }

        # Create all video jobs concurrently
        job_tasks = [
            create_single_video_job(i, video) for i, video in enumerate(videos)
        ]
        job_results = await asyncio.gather(*job_tasks, return_exceptions=True)

        # Filter out None results and exceptions
        for result in job_results:
            if result is not None and not isinstance(result, Exception):
                video_jobs.append(result)

        successful_jobs = len(
            [
                job
                for job in video_jobs
                if isinstance(job, dict) and job.get("status") == "created"
            ]
        )
        failed_jobs = len(
            [
                job
                for job in video_jobs
                if isinstance(job, dict) and job.get("status") == "failed_creation"
            ]
        )

        print(f"📊 Chunk complete: {successful_jobs} jobs created, {failed_jobs} failed")
        return video_jobs

    async def _execute_playlist_downloads(
        self, video_jobs: List[Dict[str, Any]], max_concurrent: int = 3
    ) -> Dict[str, int]:
        """Execute video downloads concurrently with controlled parallelism."""
        semaphore = asyncio.Semaphore(max_concurrent)
        successful_downloads = 0
        failed_downloads = 0

        async def execute_single_video_job(job_info: Dict[str, Any]):
            """Execute a single video download job with semaphore control."""
            nonlocal successful_downloads, failed_downloads

            # Skip jobs that failed during creation
            if job_info.get("status") == "failed_creation":
                failed_downloads += 1
                return

            async with semaphore:
                try:
                    job_id = job_info["job_id"]
                    video_title = job_info.get(
                        "title", job_info.get("video_id", "Unknown")
                    )

                    print(f"Starting download: {video_title} (job {job_id})")

                    # Execute the individual video job
                    result = await self._execute_job(job_id)

                    if result and result.status == JobStatus.COMPLETED:
                        successful_downloads += 1
                        job_info["status"] = "completed"
                        job_info["result"] = result
                        print(f"✅ Completed: {video_title}")
                    else:
                        failed_downloads += 1
                        job_info["status"] = "failed"
                        job_info["error"] = (
                            result.error_details if result else "Job execution failed"
                        )
                        print(
                            f"❌ Failed: {video_title} - {job_info.get('error', 'Unknown error')}"
                        )

                except Exception as e:
                    failed_downloads += 1
                    job_info["status"] = "failed"
                    job_info["error"] = str(e)
                    print(f"❌ Exception during {job_info.get('title', 'unknown')}: {e}")

        # Filter out jobs that have valid job_ids
        executable_jobs = [job for job in video_jobs if job.get("job_id")]

        if not executable_jobs:
            print("No executable jobs found in playlist")
            return {
                "successful": 0,
                "failed": len(video_jobs),
                "total_jobs": len(video_jobs),
            }

        print(
            f"Executing {len(executable_jobs)} video downloads with max_concurrent={max_concurrent}"
        )

        # Execute all jobs concurrently with semaphore control
        tasks = [execute_single_video_job(job) for job in executable_jobs]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Account for jobs that failed during creation
        failed_creation_count = len(
            [job for job in video_jobs if job.get("status") == "failed_creation"]
        )
        failed_downloads += failed_creation_count

        print(
            f"Playlist download completed: {successful_downloads} successful, {failed_downloads} failed"
        )

        return {
            "successful": successful_downloads,
            "failed": failed_downloads,
            "total_jobs": len(video_jobs),
        }

    async def _execute_playlist_downloads_with_progress(
        self,
        job_id: str,
        video_jobs: List[Dict[str, Any]],
        max_concurrent: int = 3,
        playlist_index: int = 0,
        total_playlists: int = 1,
        total_videos_across_playlists: int = 0,
        start_time: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Execute video downloads concurrently with real-time progress tracking and large playlist optimizations."""
        if start_time is None:
            start_time = datetime.now(timezone.utc)

        # Large playlist optimization: Dynamic concurrency adjustment
        total_videos = len(video_jobs)
        is_large_playlist = total_videos >= 100

        if is_large_playlist:
            # Increase concurrency for large playlists while being conservative
            optimized_concurrency = min(max_concurrent * 2, 8, total_videos // 10)
            print(
                f"⚡ Large playlist optimization: Increasing concurrency from {max_concurrent} to {optimized_concurrency}"
            )
            max_concurrent = max(optimized_concurrency, max_concurrent)

        semaphore = asyncio.Semaphore(max_concurrent)
        successful_downloads = 0
        failed_downloads = 0
        completed_downloads = 0

        # Calculate ETA and download speed
        def calculate_progress_metrics():
            current_time = datetime.now(timezone.utc)
            elapsed_seconds = (current_time - start_time).total_seconds()

            if elapsed_seconds > 0 and completed_downloads > 0:
                download_speed = (
                    completed_downloads / elapsed_seconds
                )  # downloads per second
                remaining_downloads = len(executable_jobs) - completed_downloads
                estimated_completion_seconds = (
                    remaining_downloads / download_speed if download_speed > 0 else 0
                )
                estimated_completion = current_time + timedelta(
                    seconds=estimated_completion_seconds
                )
            else:
                download_speed = 0.0
                estimated_completion = None

            return download_speed, estimated_completion

        async def execute_single_video_job_with_progress(job_info: Dict[str, Any]):
            """Execute a single video download job with progress updates."""
            nonlocal successful_downloads, failed_downloads, completed_downloads

            # Skip jobs that failed during creation
            if job_info.get("status") == "failed_creation":
                failed_downloads += 1
                completed_downloads += 1
                return

            async with semaphore:
                try:
                    job_id_video = job_info["job_id"]
                    video_title = job_info.get(
                        "title", job_info.get("video_id", "Unknown")
                    )

                    print(f"Starting download: {video_title} (job {job_id_video})")

                    # Optimized progress updates for large playlists
                    should_update_progress = True
                    if is_large_playlist:
                        # For large playlists, update progress less frequently to reduce overhead
                        update_interval = max(
                            5, total_videos // 20
                        )  # Update every 5-50 videos depending on size
                        should_update_progress = (
                            completed_downloads % update_interval == 0
                        ) or completed_downloads == len(executable_jobs)

                    if should_update_progress:
                        # Update progress with detailed metrics
                        (
                            download_speed,
                            estimated_completion,
                        ) = calculate_progress_metrics()

                        await self._update_job_progress(
                            job_id,
                            {
                                "phase": "downloading",
                                "total_playlists": total_playlists,
                                "processed_playlists": playlist_index,
                                "total_videos": total_videos_across_playlists
                                + len(executable_jobs),
                                "completed_videos": completed_downloads,
                                "failed_videos": failed_downloads,
                                "current_playlist": {
                                    "index": playlist_index + 1,
                                    "videos_completed": completed_downloads,
                                    "videos_total": len(executable_jobs),
                                    "success_rate": (
                                        successful_downloads / completed_downloads * 100
                                    )
                                    if completed_downloads > 0
                                    else 0,
                                },
                                "start_time": start_time.isoformat()
                                if start_time
                                else None,
                                "estimated_completion": estimated_completion.isoformat()
                                if estimated_completion
                                else None,
                                "download_speed": round(
                                    download_speed * 60, 2
                                ),  # Convert to videos per minute
                                "current_video": {
                                    "title": video_title,
                                    "video_id": job_info.get("video_id", ""),
                                    "duration": job_info.get("duration", 0),
                                    "index": job_info.get("job_request", {})
                                    .get("options", {})
                                    .get("playlist_context", {})
                                    .get("video_index", 0),
                                },
                                "current_phase_details": f"Downloaded {successful_downloads}/{len(executable_jobs)} videos ({failed_downloads} failed)",
                            },
                        )

                    # Execute the individual video job
                    result = await self._execute_job(job_id_video)

                    if result and result.status == JobStatus.COMPLETED:
                        successful_downloads += 1
                        job_info["status"] = "completed"
                        job_info["result"] = result
                        print(f"✅ Completed: {video_title}")
                    else:
                        failed_downloads += 1
                        job_info["status"] = "failed"
                        job_info["error"] = (
                            result.error_details if result else "Job execution failed"
                        )
                        print(
                            f"❌ Failed: {video_title} - {job_info.get('error', 'Unknown error')}"
                        )

                except Exception as e:
                    failed_downloads += 1
                    job_info["status"] = "failed"
                    job_info["error"] = str(e)
                    print(f"❌ Exception during {job_info.get('title', 'unknown')}: {e}")

                finally:
                    completed_downloads += 1

                    # Update progress after completing video download
                    download_speed, estimated_completion = calculate_progress_metrics()
                    await self._update_job_progress(
                        job_id,
                        {
                            "phase": "downloading",
                            "total_playlists": total_playlists,
                            "processed_playlists": playlist_index,
                            "total_videos": total_videos_across_playlists,
                            "completed_videos": completed_downloads,
                            "failed_videos": failed_downloads,
                            "current_video": {
                                "title": video_title,
                                "job_id": job_info.get("job_id"),
                                "status": job_info.get("status", "unknown"),
                            },
                            "start_time": start_time.isoformat()
                            if start_time
                            else None,
                            "estimated_completion": estimated_completion.isoformat()
                            if estimated_completion
                            else None,
                            "download_speed": round(
                                download_speed * 60, 2
                            ),  # downloads per minute
                            "progress_percentage": round(
                                (completed_downloads / len(executable_jobs)) * 100, 1
                            )
                            if executable_jobs
                            else 0,
                            "current_phase_details": f"Completed {completed_downloads}/{len(executable_jobs)} videos ({successful_downloads} successful, {failed_downloads} failed)",
                        },
                    )

        # Filter out jobs that have valid job_ids
        executable_jobs = [job for job in video_jobs if job.get("job_id")]

        if not executable_jobs:
            print("No executable jobs found in playlist")
            # Update final progress
            await self._update_job_progress(
                job_id,
                {
                    "phase": "completed",
                    "total_playlists": total_playlists,
                    "processed_playlists": playlist_index + 1,
                    "total_videos": total_videos_across_playlists,
                    "completed_videos": 0,
                    "failed_videos": len(video_jobs),
                    "start_time": start_time.isoformat(),
                    "progress_percentage": 100,
                    "current_phase_details": "No executable jobs found - playlist processing completed",
                },
            )
            return {
                "successful": 0,
                "failed": len(video_jobs),
                "total_jobs": len(video_jobs),
            }

        print(
            f"Executing {len(executable_jobs)} video downloads with max_concurrent={max_concurrent}"
        )

        # Execute all jobs concurrently with semaphore control and progress tracking
        tasks = [execute_single_video_job_with_progress(job) for job in executable_jobs]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Account for jobs that failed during creation
        failed_creation_count = len(
            [job for job in video_jobs if job.get("status") == "failed_creation"]
        )
        failed_downloads += failed_creation_count

        print(
            f"Playlist download completed: {successful_downloads} successful, {failed_downloads} failed"
        )

        # Final progress update for this playlist
        download_speed, _ = calculate_progress_metrics()
        await self._update_job_progress(
            job_id,
            {
                "phase": "playlist_completed",
                "total_playlists": total_playlists,
                "processed_playlists": playlist_index + 1,
                "total_videos": total_videos_across_playlists,
                "completed_videos": completed_downloads,
                "failed_videos": failed_downloads,
                "start_time": start_time.isoformat(),
                "download_speed": round(download_speed * 60, 2),  # downloads per minute
                "progress_percentage": 100,
                "current_phase_details": f"Playlist {playlist_index + 1}/{total_playlists} completed: {successful_downloads}/{len(executable_jobs)} videos successful",
            },
        )

        return {
            "successful": successful_downloads,
            "failed": failed_downloads,
            "total_jobs": len(video_jobs),
        }

    async def _store_playlist_results(
        self, job_id: str, playlist_results: List[Dict[str, Any]]
    ):
        """Store playlist processing results for progress tracking and analysis."""
        try:
            # Create playlist results directory if it doesn't exist
            playlist_results_dir = Path("logs/playlist_results")
            playlist_results_dir.mkdir(exist_ok=True)

            # Generate comprehensive playlist summary
            total_playlists = len(playlist_results)
            successful_playlists = len(
                [r for r in playlist_results if "error" not in r]
            )
            failed_playlists = total_playlists - successful_playlists

            total_videos = sum(r.get("total_videos", 0) for r in playlist_results)
            total_successful_downloads = sum(
                r.get("successful_downloads", 0) for r in playlist_results
            )
            total_failed_downloads = sum(
                r.get("failed_downloads", 0) for r in playlist_results
            )

            playlist_summary = {
                "job_id": job_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": {
                    "total_playlists": total_playlists,
                    "successful_playlists": successful_playlists,
                    "failed_playlists": failed_playlists,
                    "total_videos": total_videos,
                    "total_successful_downloads": total_successful_downloads,
                    "total_failed_downloads": total_failed_downloads,
                    "overall_success_rate": round(
                        (total_successful_downloads / total_videos * 100)
                        if total_videos > 0
                        else 0,
                        2,
                    ),
                },
                "playlist_results": playlist_results,
            }

            # Save results to file
            results_file = playlist_results_dir / f"playlist_{job_id}.json"
            with open(results_file, "w") as f:
                json.dump(playlist_summary, f, indent=2, default=str)

            print(f"Stored playlist results for job {job_id}:")
            print(f"  Playlists: {successful_playlists}/{total_playlists} successful")
            summary = playlist_summary.get("summary", {})
            success_rate = (
                summary.get("overall_success_rate", 0)
                if isinstance(summary, dict)
                else 0
            )
            print(
                f"  Videos: {total_successful_downloads}/{total_videos} downloaded successfully ({success_rate}%)"
            )

            # Also try to store summary in Storage service for centralized tracking
            await self._store_playlist_summary_in_storage(job_id, playlist_summary)

        except Exception as e:
            print(f"Warning: Failed to store playlist results for job {job_id}: {e}")

    async def _store_playlist_summary_in_storage(
        self, job_id: str, playlist_summary: Dict[str, Any]
    ):
        """Store playlist summary in Storage service for centralized tracking."""
        try:
            storage_url = "http://localhost:8003/api/v1/storage/save/metadata"
            payload = {
                "video_id": f"playlist_job_{job_id}",
                "metadata": {
                    "type": "playlist_job_summary",
                    "job_id": job_id,
                    "summary": playlist_summary["summary"],
                    "timestamp": playlist_summary["timestamp"],
                },
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(storage_url, json=payload)
                if response.status_code == 200:
                    print(
                        f"Stored playlist summary in Storage service for job {job_id}"
                    )
                else:
                    print(
                        f"Warning: Could not store playlist summary in Storage service: {response.status_code}"
                    )

        except Exception as e:
            print(f"Warning: Failed to store playlist summary in Storage service: {e}")

    async def _store_metadata(self, video_id: str, metadata: Dict[str, Any]):
        """Store metadata via Storage service."""
        storage_url = "http://localhost:8003/api/v1/storage/save/metadata"
        payload = {"video_id": video_id, "metadata": metadata}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(storage_url, json=payload)
            if response.status_code == 200:
                print(f"Stored metadata for video {video_id}")
            else:
                raise Exception(
                    f"Storage service error: {response.status_code} - {response.text}"
                )

    async def _register_service(
        self, registration: ServiceRegistration
    ) -> RegisteredService:
        """Register a service and persist it."""
        now = datetime.now(timezone.utc)

        service_data = {
            "service_name": registration.service_name,
            "host": registration.host,
            "port": registration.port,
            "health_endpoint": registration.health_endpoint,
            "description": registration.description,
            "tags": registration.tags,
            "registered_at": now.isoformat(),
            "last_health_check": None,
            "is_healthy": True,
        }

        # Save service to file
        service_file = self.registry_dir / f"{registration.service_name}.json"
        with open(service_file, "w") as f:
            json.dump(service_data, f, indent=2)

        return RegisteredService(**service_data)

    async def _list_services(self) -> List[RegisteredService]:
        """List all registered services."""
        services = []

        for service_file in self.registry_dir.glob("*.json"):
            try:
                with open(service_file, "r") as f:
                    service_data = json.load(f)
                services.append(RegisteredService(**service_data))
            except (json.JSONDecodeError, KeyError):
                # Skip malformed service files
                continue

        # Sort by service name
        services.sort(key=lambda x: x.service_name)
        return services

    async def _unregister_service(self, service_name: str) -> bool:
        """Unregister a service by removing its file."""
        service_file = self.registry_dir / f"{service_name}.json"
        if not service_file.exists():
            return False

        service_file.unlink()
        return True

    async def _health_check_service(self, service: RegisteredService) -> bool:
        """Perform a health check on a registered service."""
        url = f"http://{service.host}:{service.port}{service.health_endpoint}"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception:
            return False

    async def _add_to_work_plan(
        self, job_data: Dict[str, Any], error_details: Optional[str] = None
    ):
        """Add failed job to work plan for tracking and potential retry."""
        try:
            # Extract video IDs from job URLs
            video_ids = []
            for url in job_data.get("urls", []):
                # Extract video ID from YouTube URL
                if "youtube.com/watch?v=" in url:
                    video_id = url.split("v=")[1].split("&")[0]
                    video_ids.append(video_id)
                elif "youtu.be/" in url:
                    video_id = url.split("/")[-1].split("?")[0]
                    video_ids.append(video_id)

            if not video_ids:
                return  # No valid video IDs found

            # Prepare failed downloads data
            failed_downloads = []
            for video_id in video_ids:
                failed_download = {
                    "video_id": video_id,
                    "title": f"Failed Job {job_data.get('job_id', 'Unknown')}",
                    "attempts": 1,  # This could be tracked better in future
                    "last_attempt": job_data.get(
                        "updated_at", datetime.now(timezone.utc).isoformat()
                    ),
                    "job_id": job_data.get("job_id"),
                    "job_type": job_data.get("job_type"),
                    "errors": [error_details]
                    if error_details
                    else ["Job execution failed"],
                }
                failed_downloads.append(failed_download)

            # Call Storage Service to create/update work plan
            storage_url = "http://localhost:8003/api/v1/storage/work-plan"
            payload = {"unavailable_videos": [], "failed_downloads": failed_downloads}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(storage_url, json=payload)
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        print(
                            f"Added failed job {job_data.get('job_id')} to work plan {result.get('data', {}).get('plan_id')}"
                        )
                    else:
                        print(f"Failed to add job to work plan: {result.get('error')}")
                else:
                    print(f"Storage service returned status {response.status_code}")

        except Exception as e:
            # Don't fail the job update if work plan addition fails
            print(f"Warning: Failed to add job to work plan: {e}")


if __name__ == "__main__":
    settings = ServiceSettings(port=8000)  # Port for jobs service
    service = JobsService("JobsService", settings)
    service.run()
