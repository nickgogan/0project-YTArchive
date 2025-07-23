"""Tests for the JobsService."""

import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from services.common.base import ServiceSettings
from services.jobs.main import JobsService


@pytest.fixture
def jobs_service():
    """Create a JobsService instance for testing."""
    settings = ServiceSettings(port=8000)
    return JobsService("TestJobsService", settings)


@pytest.mark.asyncio
async def test_create_job(jobs_service: JobsService):
    """Test creating a new job."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        job_data = {
            "job_type": "VIDEO_DOWNLOAD",
            "urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
            "options": {"quality": "1080p"},
        }

        response = await client.post("/api/v1/jobs", json=job_data)
        assert response.status_code == 200

        result = response.json()
        assert "job_id" in result
        assert result["job_type"] == "VIDEO_DOWNLOAD"
        assert result["status"] == "PENDING"
        assert result["urls"] == job_data["urls"]
        assert result["options"] == job_data["options"]
        assert "created_at" in result
        assert "updated_at" in result


@pytest.mark.asyncio
async def test_get_job(jobs_service: JobsService):
    """Test retrieving a job by ID."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        # First create a job
        job_data = {
            "job_type": "VIDEO_DOWNLOAD",
            "urls": ["https://www.youtube.com/watch?v=test"],
            "options": {},
        }

        create_response = await client.post("/api/v1/jobs", json=job_data)
        job_id = create_response.json()["job_id"]

        # Then retrieve it
        get_response = await client.get(f"/api/v1/jobs/{job_id}")
        assert get_response.status_code == 200

        result = get_response.json()
        assert result["job_id"] == job_id
        assert result["job_type"] == "VIDEO_DOWNLOAD"
        assert result["urls"] == job_data["urls"]


@pytest.mark.asyncio
async def test_get_nonexistent_job(jobs_service: JobsService):
    """Test retrieving a job that doesn't exist."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        response = await client.get("/api/v1/jobs/nonexistent-id")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_jobs(jobs_service: JobsService):
    """Test listing jobs."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        # Create a couple of jobs
        job_data_1 = {
            "job_type": "VIDEO_DOWNLOAD",
            "urls": ["https://www.youtube.com/watch?v=test1"],
            "options": {},
        }
        job_data_2 = {
            "job_type": "PLAYLIST_DOWNLOAD",
            "urls": ["https://www.youtube.com/playlist?list=test"],
            "options": {},
        }

        await client.post("/api/v1/jobs", json=job_data_1)
        await client.post("/api/v1/jobs", json=job_data_2)

        # List all jobs
        response = await client.get("/api/v1/jobs")
        assert response.status_code == 200

        result = response.json()
        assert "jobs" in result
        assert "count" in result
        assert result["count"] >= 2


@pytest.mark.asyncio
async def test_list_jobs_with_status_filter(jobs_service: JobsService):
    """Test listing jobs with status filtering."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        # Create a job
        job_data = {
            "job_type": "VIDEO_DOWNLOAD",
            "urls": ["https://www.youtube.com/watch?v=filter_test"],
            "options": {},
        }

        await client.post("/api/v1/jobs", json=job_data)

        # List jobs with PENDING status
        response = await client.get("/api/v1/jobs?status_filter=PENDING")
        assert response.status_code == 200

        result = response.json()
        assert result["count"] >= 1
        # All returned jobs should be PENDING
        for job in result["jobs"]:
            assert job["status"] == "PENDING"


@pytest.mark.asyncio
async def test_job_file_persistence(jobs_service: JobsService):
    """Test that jobs are properly persisted to files."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        job_data = {
            "job_type": "VIDEO_DOWNLOAD",
            "urls": ["https://www.youtube.com/watch?v=persistence_test"],
            "options": {"test": "value"},
        }

        response = await client.post("/api/v1/jobs", json=job_data)
        job_id = response.json()["job_id"]

        # Check that the job file was created
        job_file = Path("jobs") / f"{job_id}.json"
        assert job_file.exists()

        # Verify the file contents
        with open(job_file, "r") as f:
            saved_data = json.load(f)

        assert saved_data["job_id"] == job_id
        assert saved_data["job_type"] == "VIDEO_DOWNLOAD"
        assert saved_data["urls"] == job_data["urls"]
        assert saved_data["options"] == job_data["options"]


@pytest.mark.asyncio
async def test_register_service(jobs_service: JobsService):
    """Test registering a service in the registry."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        registration_data = {
            "service_name": "test-service",
            "host": "localhost",
            "port": 8001,
            "health_endpoint": "/health",
            "description": "Test service",
            "tags": ["test", "microservice"],
        }

        response = await client.post(
            "/api/v1/registry/register", json=registration_data
        )
        assert response.status_code == 200

        result = response.json()
        assert result["message"] == "Service registered successfully"
        assert "service" in result
        service = result["service"]
        assert service["service_name"] == "test-service"
        assert service["host"] == "localhost"
        assert service["port"] == 8001
        assert service["is_healthy"] is True


@pytest.mark.asyncio
async def test_list_services(jobs_service: JobsService):
    """Test listing registered services."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        # Register a service first
        registration_data = {
            "service_name": "list-test-service",
            "host": "localhost",
            "port": 8002,
            "description": "Service for list testing",
        }

        await client.post("/api/v1/registry/register", json=registration_data)

        # List services
        response = await client.get("/api/v1/registry/services")
        assert response.status_code == 200

        result = response.json()
        assert "services" in result
        assert "count" in result
        assert result["count"] >= 1

        # Check that our service is in the list
        service_names = [s["service_name"] for s in result["services"]]
        assert "list-test-service" in service_names


@pytest.mark.asyncio
async def test_unregister_service(jobs_service: JobsService):
    """Test unregistering a service from the registry."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        # Register a service first
        registration_data = {
            "service_name": "unregister-test-service",
            "host": "localhost",
            "port": 8003,
        }

        await client.post("/api/v1/registry/register", json=registration_data)

        # Unregister the service
        response = await client.delete(
            "/api/v1/registry/services/unregister-test-service"
        )
        assert response.status_code == 200

        result = response.json()
        assert "unregistered successfully" in result["message"]

        # Verify the service is no longer in the list
        list_response = await client.get("/api/v1/registry/services")
        service_names = [s["service_name"] for s in list_response.json()["services"]]
        assert "unregister-test-service" not in service_names


@pytest.mark.asyncio
async def test_unregister_nonexistent_service(jobs_service: JobsService):
    """Test unregistering a service that doesn't exist."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        response = await client.delete("/api/v1/registry/services/nonexistent-service")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_service_registry_file_persistence(jobs_service: JobsService):
    """Test that services are properly persisted to files."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        registration_data = {
            "service_name": "persistence-test",
            "host": "localhost",
            "port": 8004,
            "tags": ["persistence", "test"],
        }

        response = await client.post(
            "/api/v1/registry/register", json=registration_data
        )
        service_name = response.json()["service"]["service_name"]

        # Check that the service file was created
        service_file = Path("registry") / f"{service_name}.json"
        assert service_file.exists()

        # Verify the file contents
        with open(service_file, "r") as f:
            saved_data = json.load(f)

        assert saved_data["service_name"] == "persistence-test"
        assert saved_data["host"] == "localhost"
        assert saved_data["port"] == 8004
        assert saved_data["tags"] == ["persistence", "test"]


@pytest.mark.asyncio
async def test_execute_job(jobs_service: JobsService):
    """Test executing a job."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        # Create a job first
        job_data = {
            "job_type": "VIDEO_DOWNLOAD",
            "urls": ["https://www.youtube.com/watch?v=execute_test"],
            "options": {},
        }

        create_response = await client.post("/api/v1/jobs", json=job_data)
        job_id = create_response.json()["job_id"]

        # Execute the job
        execute_response = await client.put(f"/api/v1/jobs/{job_id}/execute")
        assert execute_response.status_code == 200

        result = execute_response.json()
        assert result["job_id"] == job_id
        assert result["status"] == "COMPLETED"  # Should be completed after execution
        assert "updated_at" in result


@pytest.mark.asyncio
async def test_execute_nonexistent_job(jobs_service: JobsService):
    """Test executing a job that doesn't exist."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        response = await client.put("/api/v1/jobs/nonexistent-id/execute")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_job_status_updates(jobs_service: JobsService):
    """Test that job status is properly updated during execution."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        # Create a job
        job_data = {
            "job_type": "METADATA_ONLY",
            "urls": ["https://www.youtube.com/watch?v=status_test"],
            "options": {},
        }

        create_response = await client.post("/api/v1/jobs", json=job_data)
        job_id = create_response.json()["job_id"]

        # Initial status should be PENDING
        get_response = await client.get(f"/api/v1/jobs/{job_id}")
        assert get_response.json()["status"] == "PENDING"

        # Execute the job
        execute_response = await client.put(f"/api/v1/jobs/{job_id}/execute")
        assert execute_response.status_code == 200

        # Final status should be COMPLETED
        final_response = await client.get(f"/api/v1/jobs/{job_id}")
        assert final_response.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_execute_already_completed_job(jobs_service: JobsService):
    """Test executing a job that's already completed."""
    async with AsyncClient(app=jobs_service.app, base_url="http://test") as client:
        # Create and execute a job
        job_data = {
            "job_type": "VIDEO_DOWNLOAD",
            "urls": ["https://www.youtube.com/watch?v=already_completed"],
            "options": {},
        }

        create_response = await client.post("/api/v1/jobs", json=job_data)
        job_id = create_response.json()["job_id"]

        # Execute the job first time
        first_execute = await client.put(f"/api/v1/jobs/{job_id}/execute")
        assert first_execute.status_code == 200
        assert first_execute.json()["status"] == "COMPLETED"

        # Execute the job again - should return the same result without re-processing
        second_execute = await client.put(f"/api/v1/jobs/{job_id}/execute")
        assert second_execute.status_code == 200
        assert second_execute.json()["status"] == "COMPLETED"
