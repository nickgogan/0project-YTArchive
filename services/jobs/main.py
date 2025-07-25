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
        """Process playlist download job."""
        # For now, process each URL as individual video download
        # TODO: Add proper playlist expansion in future enhancement
        await self._process_video_download(job)

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
