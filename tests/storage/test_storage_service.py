"""Tests for the StorageService."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient

from services.common.base import ServiceSettings
from services.common.models import UnavailableVideo, FailedDownload
from services.storage.main import StorageService


@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for storage testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def storage_service(temp_storage_dir):
    """Create a StorageService instance for testing."""
    settings = ServiceSettings(port=8003)
    service = StorageService("TestStorageService", settings)

    # Override paths to use temp directory
    service.base_output_dir = temp_storage_dir / "YTArchive"
    service.metadata_dir = service.base_output_dir / "metadata"
    service.videos_dir = service.base_output_dir / "videos"
    service.work_plans_dir = temp_storage_dir / "work_plans"

    # Recreate directories with new paths
    service._ensure_directories()

    return service


@pytest.mark.asyncio
async def test_save_metadata(storage_service: StorageService):
    """Test saving video metadata."""
    async with AsyncClient(app=storage_service.app, base_url="http://test") as client:
        metadata = {
            "title": "Test Video",
            "description": "A test video",
            "duration": 120,
            "upload_date": "2024-01-01T00:00:00Z",
        }

        request_data = {"video_id": "test123", "metadata": metadata}

        response = await client.post("/api/v1/storage/save/metadata", json=request_data)
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True
        assert "path" in result["data"]
        assert "size_bytes" in result["data"]
        assert "saved_at" in result["data"]

        # Verify file was created
        metadata_file = storage_service.metadata_dir / "videos" / "test123.json"
        assert metadata_file.exists()

        # Verify content
        with open(metadata_file, "r") as f:
            saved_data = json.load(f)

        assert saved_data["title"] == metadata["title"]
        assert saved_data["description"] == metadata["description"]
        assert "storage_info" in saved_data
        assert saved_data["storage_info"]["video_id"] == "test123"


@pytest.mark.asyncio
async def test_save_video_info(storage_service: StorageService):
    """Test saving video file information."""
    async with AsyncClient(app=storage_service.app, base_url="http://test") as client:
        video_data = {
            "video_id": "test456",
            "video_path": "/path/to/video.mp4",
            "thumbnail_path": "/path/to/thumb.jpg",
            "captions": {"en": "/path/to/en.vtt"},
            "file_size": 1024000,
            "download_completed_at": datetime.now(timezone.utc).isoformat(),
        }

        response = await client.post("/api/v1/storage/save/video", json=video_data)
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True
        assert "video_dir" in result["data"]
        assert "info_file" in result["data"]
        assert "saved_at" in result["data"]

        # Verify directory and file were created
        video_dir = storage_service.videos_dir / "test456"
        assert video_dir.exists()

        info_file = video_dir / "test456_info.json"
        assert info_file.exists()

        # Verify content
        with open(info_file, "r") as f:
            saved_data = json.load(f)

        assert saved_data["video_id"] == "test456"
        assert saved_data["video_path"] == video_data["video_path"]
        assert saved_data["file_size"] == video_data["file_size"]


@pytest.mark.asyncio
async def test_check_video_exists_not_found(storage_service: StorageService):
    """Test checking for video that doesn't exist."""
    async with AsyncClient(app=storage_service.app, base_url="http://test") as client:
        response = await client.get("/api/v1/storage/exists/nonexistent")
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True
        assert result["data"]["exists"] is False
        assert result["data"]["has_video"] is False
        assert result["data"]["has_metadata"] is False
        assert result["data"]["has_thumbnail"] is False
        assert result["data"]["has_captions"] == []


@pytest.mark.asyncio
async def test_check_video_exists_with_metadata(storage_service: StorageService):
    """Test checking for video with metadata."""
    # First create metadata
    metadata_file = storage_service.metadata_dir / "videos" / "test789.json"
    metadata = {"title": "Test Video", "description": "Test"}

    with open(metadata_file, "w") as f:
        json.dump(metadata, f)

    async with AsyncClient(app=storage_service.app, base_url="http://test") as client:
        response = await client.get("/api/v1/storage/exists/test789")
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True
        assert result["data"]["exists"] is True
        assert result["data"]["has_metadata"] is True
        assert result["data"]["has_video"] is False
        assert "metadata" in result["data"]["paths"]


@pytest.mark.asyncio
async def test_check_video_exists_with_video_files(storage_service: StorageService):
    """Test checking for video with all files present."""
    # Create video directory and files
    video_dir = storage_service.videos_dir / "test101"
    video_dir.mkdir(parents=True)

    # Create mock files
    video_file = video_dir / "test101.mp4"
    thumbnail_file = video_dir / "test101_thumb.jpg"
    captions_dir = video_dir / "captions"
    captions_dir.mkdir()
    caption_file = captions_dir / "test101_en.vtt"

    for file in [video_file, thumbnail_file, caption_file]:
        file.write_text("mock content")

    async with AsyncClient(app=storage_service.app, base_url="http://test") as client:
        response = await client.get("/api/v1/storage/exists/test101")
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True
        assert result["data"]["exists"] is True
        assert result["data"]["has_video"] is True
        assert result["data"]["has_thumbnail"] is True
        assert "en" in result["data"]["has_captions"]
        assert "video" in result["data"]["paths"]
        assert "thumbnail" in result["data"]["paths"]
        assert "caption_en" in result["data"]["paths"]


@pytest.mark.asyncio
async def test_get_stored_metadata_not_found(storage_service: StorageService):
    """Test getting metadata for non-existent video."""
    async with AsyncClient(app=storage_service.app, base_url="http://test") as client:
        response = await client.get("/api/v1/storage/metadata/nonexistent")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_stored_metadata_success(storage_service: StorageService):
    """Test getting stored metadata successfully."""
    # Create metadata file
    metadata_file = storage_service.metadata_dir / "videos" / "test202.json"
    test_metadata = {
        "title": "Test Video",
        "description": "Test description",
        "storage_info": {"stored_at": "2024-01-01T00:00:00Z", "video_id": "test202"},
    }

    with open(metadata_file, "w") as f:
        json.dump(test_metadata, f)

    async with AsyncClient(app=storage_service.app, base_url="http://test") as client:
        response = await client.get("/api/v1/storage/metadata/test202")
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True
        assert result["data"]["video_id"] == "test202"
        assert result["data"]["metadata"]["title"] == "Test Video"
        assert "storage_info" in result["data"]


@pytest.mark.asyncio
async def test_generate_work_plan(storage_service: StorageService):
    """Test generating work plan."""
    unavailable_video = UnavailableVideo(
        video_id="private123",
        title="Private Video",
        reason="private",
        detected_at=datetime.now(timezone.utc),
    )

    failed_download = FailedDownload(
        video_id="failed456",
        title="Failed Video",
        attempts=3,
        last_attempt=datetime.now(timezone.utc),
        errors=[{"error": "network timeout"}],
    )

    request_data = {
        "unavailable_videos": [unavailable_video.model_dump(mode="json")],
        "failed_downloads": [failed_download.model_dump(mode="json")],
    }

    async with AsyncClient(app=storage_service.app, base_url="http://test") as client:
        response = await client.post("/api/v1/storage/work-plan", json=request_data)
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True
        assert "plan_id" in result["data"]
        assert result["data"]["total_videos"] == 2
        assert result["data"]["unavailable_count"] == 1
        assert result["data"]["failed_count"] == 1

        # Verify file was created
        plan_files = list(storage_service.work_plans_dir.glob("*_plan.json"))
        assert len(plan_files) >= 1


@pytest.mark.asyncio
async def test_get_storage_stats_empty(storage_service: StorageService):
    """Test getting storage stats for empty storage."""
    async with AsyncClient(app=storage_service.app, base_url="http://test") as client:
        response = await client.get("/api/v1/storage/stats")
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True
        assert result["data"]["total_videos"] == 0
        assert result["data"]["total_size_bytes"] == 0
        assert result["data"]["metadata_count"] == 0
        assert result["data"]["video_count"] == 0
        assert result["data"]["thumbnail_count"] == 0
        assert result["data"]["caption_count"] == 0
        assert "disk_usage" in result["data"]


@pytest.mark.asyncio
async def test_get_storage_stats_with_content(storage_service: StorageService):
    """Test getting storage stats with some content."""
    # Create some metadata files
    for i in range(3):
        metadata_file = storage_service.metadata_dir / "videos" / f"test{i}.json"
        with open(metadata_file, "w") as f:
            json.dump({"title": f"Test Video {i}"}, f)

    # Create some video directories with files
    for i in range(2):
        video_dir = storage_service.videos_dir / f"test{i}"
        video_dir.mkdir(parents=True)

        video_file = video_dir / f"test{i}.mp4"
        video_file.write_text("mock video content")

        thumbnail_file = video_dir / f"test{i}_thumb.jpg"
        thumbnail_file.write_text("mock thumbnail")

    async with AsyncClient(app=storage_service.app, base_url="http://test") as client:
        response = await client.get("/api/v1/storage/stats")
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True
        assert result["data"]["total_videos"] == 2  # Number of video directories
        assert result["data"]["metadata_count"] == 3
        assert result["data"]["video_count"] == 2
        assert result["data"]["thumbnail_count"] == 2
        assert result["data"]["total_size_bytes"] > 0
        assert result["data"]["total_size_human"] != "0.0 B"


@pytest.mark.asyncio
async def test_health_check(storage_service: StorageService):
    """Test the health check endpoint."""
    async with AsyncClient(app=storage_service.app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200

        result = response.json()
        assert result["service"] == "TestStorageService"
        assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_error_handling_invalid_json(storage_service: StorageService):
    """Test error handling with invalid JSON in request."""
    async with AsyncClient(app=storage_service.app, base_url="http://test") as client:
        # Send invalid JSON
        response = await client.post(
            "/api/v1/storage/save/metadata",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422  # Validation error


def test_storage_directory_creation(storage_service: StorageService):
    """Test that storage directories are created properly."""
    expected_dirs = [
        storage_service.metadata_dir / "videos",
        storage_service.metadata_dir / "playlists",
        storage_service.videos_dir,
        storage_service.work_plans_dir,
    ]

    for directory in expected_dirs:
        assert directory.exists()
        assert directory.is_dir()


def test_storage_service_initialization(temp_storage_dir):
    """Test StorageService initialization."""
    settings = ServiceSettings(port=8003)
    service = StorageService("TestStorageService", settings)

    assert service.service_name == "TestStorageService"
    assert hasattr(service, "base_output_dir")
    assert hasattr(service, "metadata_dir")
    assert hasattr(service, "videos_dir")
    assert hasattr(service, "work_plans_dir")
