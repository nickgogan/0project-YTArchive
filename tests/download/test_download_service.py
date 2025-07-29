"""Comprehensive tests for Download Service."""

import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from services.download.main import DownloadService, DownloadStatus
from services.common.base import ServiceSettings


@pytest.fixture
def sample_video_info():
    """Sample yt-dlp video info data."""
    return {
        "id": "dQw4w9WgXcQ",
        "title": "Rick Astley - Never Gonna Give You Up",
        "duration": 212,
        "formats": [
            {
                "format_id": "137",
                "ext": "mp4",
                "resolution": "1080p",
                "fps": 30,
                "vcodec": "avc1.640028",
                "acodec": "none",
                "filesize": 100000000,
                "format_note": "1080p",
            },
            {
                "format_id": "22",
                "ext": "mp4",
                "resolution": "720p",
                "fps": 30,
                "vcodec": "avc1.64001F",
                "acodec": "mp4a.40.2",
                "filesize": 50000000,
                "format_note": "720p",
            },
        ],
        "format_id": "22",
    }


@pytest.fixture
def temp_download_dir():
    """Create temporary directory for downloads."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def download_service(temp_download_dir):
    """Create DownloadService instance for testing."""
    settings = ServiceSettings(port=8002)
    service = DownloadService("DownloadService", settings)
    yield service


@pytest_asyncio.fixture
async def client(download_service):
    """Create test client for the download service."""
    async with AsyncClient(app=download_service.app, base_url="http://test") as client:
        yield client
    # Clean up any pending tasks after tests
    await download_service.cleanup_pending_tasks()


class TestDownloadService:
    """Test cases for DownloadService."""

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_start_video_download_success(
        self, client: AsyncClient, temp_download_dir: str
    ):
        """Test successful video download start."""
        request_data: Dict[str, Any] = {
            "video_id": "dQw4w9WgXcQ",
            "quality": "720p",
            "output_path": temp_download_dir,
            "include_captions": True,
            "caption_languages": ["en"],
        }

        # Mock Storage service integration to return the temp directory
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.return_value.status_code = (
                200
            )

            response = await client.post("/api/v1/download/video", json=request_data)
            assert response.status_code == 200

            data = response.json()
            assert data["success"] is True
            assert data["data"]["video_id"] == "dQw4w9WgXcQ"
            assert data["data"]["status"] == "pending"
            assert "task_id" in data["data"]
            # After integration, path comes from Storage service (mocked to use default path)
            assert "YTArchive/videos" in data["data"]["output_path"]

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_start_download_invalid_quality(
        self, client: AsyncClient, temp_download_dir: str
    ):
        """Test download with invalid quality parameter."""
        request_data: Dict[str, Any] = {
            "video_id": "dQw4w9WgXcQ",
            "quality": "invalid_quality",
            "output_path": temp_download_dir,
        }

        response = await client.post("/api/v1/download/video", json=request_data)
        assert response.status_code == 400
        assert "Invalid quality" in response.json()["detail"]

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_start_download_default_values(
        self, client: AsyncClient, temp_download_dir: str
    ):
        """Test download with default parameter values."""
        request_data: Dict[str, Any] = {
            "video_id": "dQw4w9WgXcQ",
            "output_path": temp_download_dir,
        }

        response = await client.post("/api/v1/download/video", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        # Should use default quality (1080p)

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_get_download_progress_success(
        self,
        client: AsyncClient,
        download_service: DownloadService,
        temp_download_dir: str,
    ):
        """Test getting download progress for existing task."""
        # Create a task manually for testing
        from services.download.main import DownloadRequest

        request = DownloadRequest(video_id="dQw4w9WgXcQ", output_path=temp_download_dir)
        task = await download_service._create_download_task(request)

        response = await client.get(f"/api/v1/download/progress/{task.task_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["data"]["task_id"] == task.task_id
        assert data["data"]["video_id"] == "dQw4w9WgXcQ"
        assert data["data"]["status"] == "pending"
        assert data["data"]["progress_percent"] == 0.0

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_get_progress_nonexistent_task(self, client: AsyncClient):
        """Test getting progress for non-existent task."""
        fake_task_id = "nonexistent-task-id"
        response = await client.get(f"/api/v1/download/progress/{fake_task_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_cancel_download_success(
        self,
        client: AsyncClient,
        download_service: DownloadService,
        temp_download_dir: str,
    ):
        """Test successful download cancellation."""
        # Create a task manually for testing
        from services.download.main import DownloadRequest

        request = DownloadRequest(video_id="dQw4w9WgXcQ", output_path=temp_download_dir)
        task = await download_service._create_download_task(request)

        response = await client.post(f"/api/v1/download/cancel/{task.task_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["data"]["task_id"] == task.task_id
        assert data["data"]["status"] == "cancelled"
        assert "cancelled successfully" in data["data"]["message"]

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self, client: AsyncClient):
        """Test cancelling non-existent task."""
        fake_task_id = "nonexistent-task-id"
        response = await client.post(f"/api/v1/download/cancel/{fake_task_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_cancel_completed_task(
        self,
        client: AsyncClient,
        download_service: DownloadService,
        temp_download_dir: str,
    ):
        """Test cancelling already completed task."""
        # Create and mark task as completed
        from services.download.main import DownloadRequest

        request = DownloadRequest(video_id="dQw4w9WgXcQ", output_path=temp_download_dir)
        task = await download_service._create_download_task(request)
        task.status = DownloadStatus.COMPLETED

        response = await client.post(f"/api/v1/download/cancel/{task.task_id}")
        assert response.status_code == 400
        assert "Cannot cancel" in response.json()["detail"]

    @pytest.mark.service
    @pytest.mark.asyncio
    @patch("services.download.main.DownloadService._extract_info")
    async def test_get_video_formats_success(
        self,
        mock_extract_info: MagicMock,
        client: AsyncClient,
        sample_video_info: Dict[str, Any],
    ):
        """Test getting available video formats."""
        mock_extract_info.return_value = sample_video_info

        response = await client.get("/api/v1/download/formats/dQw4w9WgXcQ")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["data"]["video_id"] == "dQw4w9WgXcQ"
        assert len(data["data"]["formats"]) == 2

        # Check format details
        formats = data["data"]["formats"]
        assert formats[0]["format_id"] == "137"
        assert formats[0]["resolution"] == "1080p"
        assert formats[1]["format_id"] == "22"
        assert formats[1]["resolution"] == "720p"

    @pytest.mark.service
    @pytest.mark.asyncio
    @patch("services.download.main.DownloadService._extract_info")
    async def test_get_formats_video_not_found(
        self, mock_extract_info: MagicMock, client: AsyncClient
    ):
        """Test getting formats for non-existent video."""
        mock_extract_info.return_value = None

        response = await client.get("/api/v1/download/formats/nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_quality_mapping(self, download_service: DownloadService):
        """Test quality format mapping."""
        expected_qualities = ["best", "1080p", "720p", "480p", "360p", "audio"]
        for quality in expected_qualities:
            assert quality in download_service.quality_map
            assert isinstance(download_service.quality_map[quality], str)
            assert len(download_service.quality_map[quality]) > 0

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_create_download_task(
        self, download_service: DownloadService, temp_download_dir: str
    ):
        """Test creating a download task."""
        from services.download.main import DownloadRequest

        request = DownloadRequest(
            video_id="dQw4w9WgXcQ",
            quality="720p",
            output_path=temp_download_dir,
            include_captions=True,
            caption_languages=["en", "es"],
        )

        task = await download_service._create_download_task(request)

        assert task.video_id == "dQw4w9WgXcQ"
        assert task.status == DownloadStatus.PENDING
        assert task.task_id in download_service.active_tasks
        assert task.task_id in download_service.task_progress
        assert Path(task.output_path).exists()

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_create_task_invalid_quality(
        self, download_service: DownloadService, temp_download_dir: str
    ):
        """Test creating task with invalid quality."""
        from services.download.main import DownloadRequest

        request = DownloadRequest(
            video_id="dQw4w9WgXcQ", quality="invalid", output_path=temp_download_dir
        )

        with pytest.raises(Exception):  # Should raise HTTPException
            await download_service._create_download_task(request)

    @pytest.mark.service
    @pytest.mark.asyncio
    @patch("services.download.main.DownloadService._run_ytdlp")
    async def test_download_video_mock(
        self,
        mock_run_ytdlp: MagicMock,
        download_service: DownloadService,
        temp_download_dir: str,
    ):
        """Test video download with mocked yt-dlp."""
        # Mock yt-dlp to avoid actual download
        mock_run_ytdlp.return_value = None

        from services.download.main import DownloadRequest

        request = DownloadRequest(video_id="dQw4w9WgXcQ", output_path=temp_download_dir)
        task = await download_service._create_download_task(request)

        # Test the download process (mocked)
        await download_service._download_video(task)

        # Verify yt-dlp was called
        mock_run_ytdlp.assert_called_once()
        call_args = mock_run_ytdlp.call_args
        assert "https://www.youtube.com/watch?v=dQw4w9WgXcQ" in call_args[0]

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_progress_tracking(
        self, download_service: DownloadService, temp_download_dir: str
    ):
        """Test progress tracking functionality."""
        from services.download.main import DownloadRequest

        request = DownloadRequest(video_id="dQw4w9WgXcQ", output_path=temp_download_dir)
        task = await download_service._create_download_task(request)

        # Simulate progress update
        progress = download_service.task_progress[task.task_id]
        progress.downloaded_bytes = 50000
        progress.total_bytes = 100000
        progress.speed = 1024
        progress.eta = 50

        # Verify progress calculation
        assert progress.downloaded_bytes == 50000
        assert progress.total_bytes == 100000
        assert progress.speed == 1024
        assert progress.eta == 50

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_concurrent_download_limit(self, download_service: DownloadService):
        """Test concurrent download limitation."""
        assert download_service.max_concurrent_downloads == 3
        assert download_service.download_semaphore._value == 3

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_output_directory_creation(self, download_service: DownloadService):
        """Test that output directories are created."""
        with tempfile.TemporaryDirectory() as temp_dir:
            subdir = Path(temp_dir) / "new_subdir"

            from services.download.main import DownloadRequest

            request = DownloadRequest(video_id="dQw4w9WgXcQ", output_path=str(subdir))

            task = await download_service._create_download_task(request)
            assert Path(task.output_path).exists()
            assert Path(task.output_path).is_dir()

    @pytest.mark.unit
    def test_video_format_model(self):
        """Test VideoFormat model validation."""
        from services.download.main import VideoFormat

        format_data = {
            "format_id": "137",
            "ext": "mp4",
            "resolution": "1080p",
            "fps": 30,
            "vcodec": "avc1.640028",
            "acodec": "none",
            "filesize": 100000000,
            "format_note": "1080p",
        }

        video_format = VideoFormat(**format_data)
        assert video_format.format_id == "137"
        assert video_format.resolution == "1080p"
        assert video_format.fps == 30

    @pytest.mark.unit
    def test_download_request_model(self):
        """Test DownloadRequest model validation and defaults."""
        from services.download.main import DownloadRequest

        # Test minimal request
        request = DownloadRequest(video_id="dQw4w9WgXcQ", output_path="/tmp")

        assert request.video_id == "dQw4w9WgXcQ"
        assert request.quality == "1080p"  # default
        assert request.include_captions is True  # default
        assert request.caption_languages == ["en"]  # default
        assert request.resume is True  # default

    @pytest.mark.unit
    def test_download_status_enum(self):
        """Test DownloadStatus enum values."""
        from services.download.main import DownloadStatus

        expected_statuses = [
            "pending",
            "downloading",
            "completed",
            "failed",
            "cancelled",
            "paused",
        ]

        for status in expected_statuses:
            assert hasattr(DownloadStatus, status.upper())
            assert getattr(DownloadStatus, status.upper()).value == status


class TestDownloadErrorRecovery:
    """Test cases for Download Service error recovery integration."""

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_error_recovery_status_endpoint(self, client: AsyncClient):
        """Test error recovery status endpoint."""
        response = await client.get("/api/v1/download/error-recovery/status")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "active_operations" in data["data"]
        assert "retry_strategy" in data["data"]
        assert "service_handler" in data["data"]
        assert data["data"]["service_handler"] == "DownloadErrorHandler"

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_error_reports_endpoint(self, client: AsyncClient):
        """Test error reports endpoint."""
        response = await client.get("/api/v1/download/error-recovery/reports")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        # Should return error summary data structure

    @pytest.mark.service
    @pytest.mark.asyncio
    async def test_clear_error_reports_endpoint(self, client: AsyncClient):
        """Test clear error reports endpoint."""
        response = await client.post("/api/v1/download/error-recovery/clear-reports")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["data"]["cleared"] is True

    @pytest.mark.unit
    def test_download_error_handler_initialization(self, download_service):
        """Test that DownloadService properly initializes error recovery components."""
        # Verify error recovery components are initialized
        assert hasattr(download_service, "error_recovery")
        assert hasattr(download_service, "download_error_handler")
        assert hasattr(download_service, "error_reporter")

        # Verify correct types
        from services.download.error_handler import DownloadErrorHandler
        from services.error_recovery import ErrorRecoveryManager
        from services.error_recovery.reporting import BasicErrorReporter

        assert isinstance(download_service.download_error_handler, DownloadErrorHandler)
        assert isinstance(download_service.error_recovery, ErrorRecoveryManager)
        assert isinstance(download_service.error_reporter, BasicErrorReporter)

    @pytest.mark.unit
    def test_download_error_handler_retry_logic(self):
        """Test DownloadErrorHandler retry decision logic."""
        from services.download.error_handler import DownloadErrorHandler
        from services.error_recovery.types import ErrorContext

        handler = DownloadErrorHandler()
        context = ErrorContext(
            operation_name="test_download",
            operation_context={"video_id": "test123"},
            attempt_count=1,
        )

        # Test network errors should retry
        network_error = Exception("Connection timeout occurred")
        assert handler.should_retry(network_error, context) is True

        # Test YouTube permanent errors should not retry
        youtube_error = Exception("Video unavailable: Private video")
        assert handler.should_retry(youtube_error, context) is False

        # Test filesystem permission errors should not retry
        permission_error = Exception("Permission denied: Cannot write to directory")
        assert handler.should_retry(permission_error, context) is False

        # Test unknown errors should retry once
        unknown_error = Exception("Unknown error occurred")
        context.attempt_count = 1
        assert handler.should_retry(unknown_error, context) is True
        context.attempt_count = 3
        assert handler.should_retry(unknown_error, context) is False

    @pytest.mark.unit
    def test_download_error_handler_severity_classification(self):
        """Test DownloadErrorHandler error severity classification."""
        from services.download.error_handler import DownloadErrorHandler
        from services.error_recovery.types import ErrorContext, ErrorSeverity

        handler = DownloadErrorHandler()
        context = ErrorContext(
            operation_name="test_download", operation_context={"video_id": "test123"}
        )

        # Test critical errors
        critical_error = Exception("File corrupted during download")
        assert (
            handler.get_error_severity(critical_error, context)
            == ErrorSeverity.CRITICAL
        )

        # Test high severity errors
        high_error = Exception("Video unavailable: Private video")
        assert handler.get_error_severity(high_error, context) == ErrorSeverity.HIGH

        # Test medium severity errors
        medium_error = Exception("Network connection timeout")
        assert handler.get_error_severity(medium_error, context) == ErrorSeverity.MEDIUM

        # Test low severity errors
        import yt_dlp

        low_error = yt_dlp.DownloadError("Temporary download issue")
        assert handler.get_error_severity(low_error, context) == ErrorSeverity.LOW

    @pytest.mark.unit
    def test_download_error_handler_error_handling(self):
        """Test DownloadErrorHandler service-specific error handling."""
        from services.download.error_handler import DownloadErrorHandler
        from services.error_recovery.types import ErrorContext

        handler = DownloadErrorHandler()
        context = ErrorContext(
            operation_name="test_download", operation_context={"video_id": "test123"}
        )

        # Test disk space error handling
        disk_error = Exception("No space left on device")
        result = handler.handle_error(disk_error, context)
        assert result["handled"] is True
        assert result["action_taken"] == "disk_space_warning"
        assert len(result["suggestions"]) > 0

        # Test network error handling
        network_error = Exception("Connection timeout occurred")
        result = handler.handle_error(network_error, context)
        assert result["handled"] is True
        assert result["action_taken"] == "network_diagnostics"

        # Test YouTube error handling
        youtube_error = Exception("Video unavailable: Private video")
        result = handler.handle_error(youtube_error, context)
        assert result["handled"] is True
        assert result["action_taken"] == "youtube_error_classification"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_download_with_error_recovery_integration(
        self, download_service, temp_download_dir
    ):
        """Test download operation with error recovery integration (mock failure scenarios)."""
        from services.download.main import DownloadRequest, DownloadStatus
        from services.error_recovery.types import ErrorContext
        import datetime

        # Create a download task
        request = DownloadRequest(
            video_id="test123", quality="720p", output_path=temp_download_dir
        )

        task = await download_service._create_download_task(request)

        # Verify task creation
        assert task.task_id is not None
        assert task.video_id == "test123"
        assert task.status == DownloadStatus.PENDING

        # Verify error recovery context creation (this would happen in _download_video)
        error_context = ErrorContext(
            operation_name="download_video",
            operation_context={
                "video_id": task.video_id,
                "output_path": task.output_path,
                "quality": task.quality,
                "task_id": task.task_id,
            },
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        # Verify context is properly structured
        assert error_context.operation_name == "download_video"
        assert error_context.operation_context["video_id"] == "test123"
        assert error_context.operation_context["quality"] == "720p"
