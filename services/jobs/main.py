"""Jobs Service for coordinating YouTube archiving tasks."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
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

        for url in job.urls:
            try:
                # Extract playlist ID from URL
                playlist_id = self._extract_playlist_id(url)
                if not playlist_id:
                    raise ValueError(f"Could not extract playlist ID from URL: {url}")

                print(f"Processing playlist {playlist_id} for job {job.job_id}")

                # Fetch playlist metadata via Metadata service
                playlist_metadata = await self._fetch_playlist_metadata(playlist_id)

                if not playlist_metadata or not playlist_metadata.get("videos"):
                    raise ValueError(f"Playlist {playlist_id} is empty or unavailable")

                videos = playlist_metadata["videos"]
                print(f"Found {len(videos)} videos in playlist {playlist_id}")

                # Create individual download jobs for each video
                video_jobs = await self._create_batch_video_jobs(
                    videos, job.options, f"playlist-{playlist_id}"
                )

                # Execute video downloads with concurrency control
                playlist_result = await self._execute_playlist_downloads(
                    video_jobs, job.options.get("max_concurrent", 3)
                )

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
                return response.json()["data"]
            else:
                raise Exception(
                    f"Playlist metadata service error: {response.status_code} - {response.text}"
                )

    async def _create_batch_video_jobs(
        self,
        videos: List[Dict[str, Any]],
        playlist_options: Dict[str, Any],
        batch_prefix: str,
    ) -> List[Dict[str, Any]]:
        """Create individual video download jobs for batch processing."""
        video_jobs = []

        for i, video in enumerate(videos):
            try:
                video_id = video.get("video_id")
                if not video_id:
                    print(
                        f"Warning: Video {i+1} in playlist missing video_id, skipping"
                    )
                    continue

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
                            "video_index": i + 1,
                            "total_videos": len(videos),
                            "video_title": video.get("title", "Unknown Title"),
                            "video_duration": video.get("duration_seconds", 0),
                        },
                    },
                )

                # Create the actual job
                created_job = await self._create_job(video_job_request)

                video_jobs.append(
                    {
                        "job_id": created_job.job_id,
                        "video_id": video_id,
                        "video_url": video_url,
                        "title": video.get("title", "Unknown Title"),
                        "duration": video.get("duration_seconds", 0),
                        "job_request": video_job_request,
                        "created_job": created_job,
                        "status": "created",
                    }
                )

                print(
                    f"Created job {created_job.job_id} for video {i+1}/{len(videos)}: {video.get('title', video_id)}"
                )

            except Exception as e:
                print(
                    f"Failed to create job for video {i+1} ({video.get('video_id', 'unknown')}): {e}"
                )
                video_jobs.append(
                    {
                        "video_id": video.get("video_id", "unknown"),
                        "title": video.get("title", "Unknown Title"),
                        "error": str(e),
                        "status": "failed_creation",
                    }
                )

        print(
            f"Created {len([job for job in video_jobs if job.get('job_id')])} jobs from {len(videos)} videos"
        )
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
            return {"successful": 0, "failed": len(video_jobs)}

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

    async def _store_playlist_results(
        self, job_id: str, playlist_results: List[Dict[str, Any]]
    ):
        """Store playlist processing results for progress tracking and analysis."""
        try:
            # Create playlist results directory if it doesn't exist
            playlist_results_dir = Path("playlist_results")
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
