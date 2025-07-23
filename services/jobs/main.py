"""Jobs Service for coordinating YouTube archiving tasks."""

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
            failed_job = await self._update_job_status(job_id, JobStatus.FAILED)
            if failed_job:
                job = failed_job
            # Log the error (in a real implementation, we'd use our logging service)
            print(f"Job {job_id} failed with error: {str(e)}")

        return job

    async def _update_job_status(
        self, job_id: str, new_status: JobStatus
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

        # Save updated job data
        with open(job_file, "w") as f:
            json.dump(job_data, f, indent=2)

        return JobResponse(**job_data)

    async def _process_job(self, job: JobResponse):
        """Process a job based on its type. This is a basic implementation."""
        import asyncio

        if job.job_type == JobType.VIDEO_DOWNLOAD:
            # Simulate video download processing
            print(f"Processing video download job for URLs: {job.urls}")
            await asyncio.sleep(1)  # Simulate work
            print(f"Video download completed for job {job.job_id}")

        elif job.job_type == JobType.PLAYLIST_DOWNLOAD:
            # Simulate playlist download processing
            print(f"Processing playlist download job for URLs: {job.urls}")
            await asyncio.sleep(2)  # Simulate more work
            print(f"Playlist download completed for job {job.job_id}")

        elif job.job_type == JobType.METADATA_ONLY:
            # Simulate metadata extraction
            print(f"Processing metadata extraction for URLs: {job.urls}")
            await asyncio.sleep(0.5)  # Simulate quick work
            print(f"Metadata extraction completed for job {job.job_id}")

        else:
            raise ValueError(f"Unknown job type: {job.job_type}")

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


if __name__ == "__main__":
    settings = ServiceSettings(port=8000)  # Port for jobs service
    service = JobsService("JobsService", settings)
    service.run()
