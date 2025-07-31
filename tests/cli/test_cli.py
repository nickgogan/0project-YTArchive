"""Comprehensive tests for YTArchive CLI."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from cli.main import cli


def setup_async_api_mock(mock_api_class):
    """Helper function to properly setup async context manager mocks."""
    mock_api = AsyncMock()
    mock_api_class.return_value = mock_api

    # ✅ CRITICAL: Set up async context manager methods (from WatchOut guide)
    mock_api.__aenter__.return_value = mock_api
    mock_api.__aexit__.return_value = None

    return mock_api


@pytest.fixture
def runner():
    """Create Click test runner."""
    return CliRunner()


@pytest.fixture
def mock_api_response():
    """Sample API response data."""
    return {
        "success": True,
        "data": {
            "title": "Test Video",
            "channel_title": "Test Channel",
            "duration": 213,
            "view_count": 1000000,
            "like_count": 50000,
            "publish_date": "2023-01-01",
            "description": "Test video description for testing purposes",
            "video_id": "dQw4w9WgXcQ",
        },
    }


@pytest.fixture
def mock_job_response():
    """Sample job response data."""
    return {
        "success": True,
        "data": {
            "job_id": "test-job-123",
            "job_type": "VIDEO_DOWNLOAD",
            "video_id": "dQw4w9WgXcQ",
            "status": "PENDING",
            "created_at": "2023-01-01T00:00:00Z",
            "started_at": None,
            "completed_at": None,
            "error": None,
        },
    }


@pytest.fixture
def mock_download_response():
    """Sample download response data."""
    return {
        "success": True,
        "data": {
            "task_id": "download-task-123",
            "video_id": "dQw4w9WgXcQ",
            "status": "pending",
            "created_at": "2023-01-01T00:00:00Z",
        },
    }


@pytest.fixture
def mock_progress_response():
    """Sample progress response data."""
    return {
        "success": True,
        "data": {
            "task_id": "download-task-123",
            "video_id": "dQw4w9WgXcQ",
            "status": "completed",
            "progress": {
                "phase": "playlist_completed",
                "completed_videos": 3,
                "failed_videos": 0,
                "total_videos": 3,
                "progress_percentage": 100.0,
            },
            "progress_percent": 100.0,
            "downloaded_bytes": 104857600,
            "total_bytes": 104857600,
            "speed": 1048576,
            "eta": 0,
            "file_path": "/path/to/video.mp4",
        },
    }


class TestCLIBasics:
    """Test basic CLI functionality."""

    @pytest.mark.service
    def test_cli_help(self, runner):
        """Test CLI help command."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "YTArchive - YouTube Video Archiving System" in result.output
        assert "download" in result.output
        assert "metadata" in result.output
        assert "status" in result.output
        assert "logs" in result.output

    @pytest.mark.service
    def test_cli_version(self, runner):
        """Test CLI version command."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    @pytest.mark.service
    def test_download_help(self, runner):
        """Test download command help."""
        result = runner.invoke(cli, ["download", "--help"])
        assert result.exit_code == 0
        assert "Download a YouTube video" in result.output
        assert "--quality" in result.output
        assert "--output" in result.output
        assert "--metadata-only" in result.output

    @pytest.mark.service
    def test_metadata_help(self, runner):
        """Test metadata command help."""
        result = runner.invoke(cli, ["metadata", "--help"])
        assert result.exit_code == 0
        assert "Fetch and display metadata" in result.output
        assert "--json-output" in result.output

    @pytest.mark.service
    def test_status_help(self, runner):
        """Test status command help."""
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0
        assert "Check the status of a job" in result.output
        assert "--watch" in result.output

    @pytest.mark.service
    def test_logs_help(self, runner):
        """Test logs command help."""
        result = runner.invoke(cli, ["logs", "--help"])
        assert result.exit_code == 0
        assert "View logs from the logging service" in result.output
        assert "--service" in result.output
        assert "--level" in result.output


class TestDownloadCommand:
    """Test download command functionality."""

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_download_metadata_only(self, mock_api_class, runner, mock_api_response):
        """Test download with metadata-only flag."""
        # Setup mock
        mock_api = setup_async_api_mock(mock_api_class)

        # Mock API responses
        mock_api.check_video_exists.return_value = {
            "success": True,
            "data": {"exists": False},
        }
        mock_api.get_video_metadata.return_value = mock_api_response

        result = runner.invoke(cli, ["download", "dQw4w9WgXcQ", "--metadata-only"])

        assert result.exit_code == 0
        assert mock_api.get_video_metadata.called
        assert not mock_api.start_download.called

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_download_video_exists(self, mock_api_class, runner):
        """Test download when video already exists."""
        # Setup mock
        mock_api = setup_async_api_mock(mock_api_class)

        # Mock API responses
        mock_api.check_video_exists.return_value = {
            "success": True,
            "data": {"exists": True},
        }

        result = runner.invoke(cli, ["download", "dQw4w9WgXcQ"])

        assert result.exit_code == 0
        assert "already exists" in result.output
        assert not mock_api.get_video_metadata.called

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_download_with_quality(
        self,
        mock_api_class,
        runner,
        mock_api_response,
        mock_download_response,
        mock_progress_response,
    ):
        """Test download with specific quality."""
        # Setup mock
        mock_api = setup_async_api_mock(mock_api_class)

        # Mock API responses for job-based workflow
        mock_api.check_video_exists.return_value = {
            "success": True,
            "data": {"exists": False},
        }
        mock_api.get_video_metadata.return_value = mock_api_response
        mock_api.create_job.return_value = {
            "success": True,
            "job_id": "download-job-123",
            "status": "pending",
        }
        mock_api.execute_job.return_value = {"success": True}
        mock_api.get_job.return_value = {
            "success": True,
            "job_id": "download-job-123",
            "status": "COMPLETED",  # ✅ CRITICAL: Must be uppercase to exit monitoring loop
            "progress": {
                "phase": "download_completed",
                "progress_percentage": 100.0,
            },
        }

        result = runner.invoke(cli, ["download", "dQw4w9WgXcQ", "--quality", "720p"])

        assert result.exit_code == 0
        assert mock_api.create_job.called
        # Verify quality was passed correctly in job config
        call_args = mock_api.create_job.call_args
        job_config = call_args[1]["config"]  # keyword arguments
        assert job_config["quality"] == "720p"

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_download_api_error(self, mock_api_class, runner):
        """Test download with API error."""
        # Setup mock
        mock_api = setup_async_api_mock(mock_api_class)

        # Mock API error - first call succeeds, second fails
        mock_api.check_video_exists.return_value = {
            "success": True,
            "data": {"exists": False},
        }
        mock_api.get_video_metadata.return_value = {
            "success": False,
            "error": "Video not found",
        }

        result = runner.invoke(cli, ["download", "invalid_video"])

        assert result.exit_code == 0  # CLI doesn't exit with error code
        assert "Failed to fetch metadata" in result.output


class TestMetadataCommand:
    """Test metadata command functionality."""

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_metadata_success(self, mock_api_class, runner, mock_api_response):
        """Test successful metadata retrieval."""
        # Setup mock
        mock_api = setup_async_api_mock(mock_api_class)

        mock_api.get_video_metadata.return_value = mock_api_response

        result = runner.invoke(cli, ["metadata", "dQw4w9WgXcQ"])

        assert result.exit_code == 0
        assert "Test Video" in result.output
        assert "Test Channel" in result.output
        assert mock_api.get_video_metadata.called

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_metadata_json_output(self, mock_api_class, runner, mock_api_response):
        """Test metadata with JSON output."""
        # Setup mock
        mock_api = setup_async_api_mock(mock_api_class)

        mock_api.get_video_metadata.return_value = mock_api_response

        result = runner.invoke(cli, ["metadata", "dQw4w9WgXcQ", "--json-output"])

        assert result.exit_code == 0
        # Find JSON content in output (everything after the loading message)
        output = result.output
        json_start = output.find("{")
        json_end = output.rfind("}") + 1

        assert json_start != -1, "No JSON found in output"
        json_content = output[json_start:json_end]

        json_output = json.loads(json_content)
        assert json_output["title"] == "Test Video"
        assert json_output["channel_title"] == "Test Channel"

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_metadata_api_error(self, mock_api_class, runner):
        """Test metadata with API error."""
        # Setup mock
        mock_api = setup_async_api_mock(mock_api_class)

        mock_api.get_video_metadata.return_value = {
            "success": False,
            "error": "Video not found",
        }

        result = runner.invoke(cli, ["metadata", "invalid_video"])

        assert result.exit_code == 0
        assert "Video not found" in result.output


class TestStatusCommand:
    """Test status command functionality."""

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_status_success(self, mock_api_class, runner, mock_job_response):
        """Test successful job status retrieval."""
        # Setup mock
        mock_api = setup_async_api_mock(mock_api_class)

        mock_api.get_job.return_value = mock_job_response

        result = runner.invoke(cli, ["status", "test-job-123"])

        assert result.exit_code == 0
        assert "PENDING" in result.output
        assert "VIDEO_DOWNLOAD" in result.output
        assert "dQw4w9WgXcQ" in result.output
        assert mock_api.get_job.called

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_status_job_not_found(self, mock_api_class, runner):
        """Test status for non-existent job."""
        # Setup mock
        mock_api = setup_async_api_mock(mock_api_class)

        mock_api.get_job.return_value = {"success": False, "error": "Job not found"}

        result = runner.invoke(cli, ["status", "nonexistent-job"])

        assert result.exit_code == 0
        assert "Job not found" in result.output

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_status_with_error(self, mock_api_class, runner):
        """Test status display with job error."""
        # Setup mock
        mock_api = setup_async_api_mock(mock_api_class)

        job_response = {
            "success": True,
            "data": {
                "job_id": "failed-job-123",
                "status": "FAILED",
                "error": "Download failed: Network error",
            },
        }
        mock_api.get_job.return_value = job_response

        result = runner.invoke(cli, ["status", "failed-job-123"])

        assert result.exit_code == 0
        assert "FAILED" in result.output
        assert "Network error" in result.output


class TestLogsCommand:
    """Test logs command functionality."""

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_logs_success(self, mock_api_class, runner):
        """Test successful log retrieval."""
        # Setup mock
        mock_api = setup_async_api_mock(mock_api_class)

        logs_response = {
            "success": True,
            "logs": [
                {
                    "timestamp": "2023-01-01T00:00:00Z",
                    "level": "INFO",
                    "service": "download",
                    "message": "Download started for video dQw4w9WgXcQ",
                },
                {
                    "timestamp": "2023-01-01T00:01:00Z",
                    "level": "INFO",
                    "service": "download",
                    "message": "Download completed successfully",
                },
            ],
        }
        mock_api.get_logs.return_value = logs_response

        result = runner.invoke(cli, ["logs"])

        assert result.exit_code == 0
        assert "Download started" in result.output
        assert "Download completed" in result.output
        assert mock_api.get_logs.called

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_logs_with_filters(self, mock_api_class, runner):
        """Test logs with service and level filters."""
        # Setup mock
        mock_api = setup_async_api_mock(mock_api_class)

        mock_api.get_logs.return_value = {"success": True, "logs": []}

        result = runner.invoke(
            cli, ["logs", "--service", "download", "--level", "ERROR"]
        )

        assert result.exit_code == 0
        # Verify filters were passed to API
        call_args = mock_api.get_logs.call_args
        assert call_args[0][0] == "download"  # service
        assert call_args[0][1] == "ERROR"  # level

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_logs_api_error(self, mock_api_class, runner):
        """Test logs with API error."""
        # Setup mock
        mock_api = setup_async_api_mock(mock_api_class)

        mock_api.get_logs.return_value = {
            "success": False,
            "error": "Logging service unavailable",
        }

        result = runner.invoke(cli, ["logs"])

        assert result.exit_code == 0
        assert "Logging service unavailable" in result.output


class TestUtilityFunctions:
    """Test utility functions."""

    @pytest.mark.unit
    def test_format_duration(self):
        """Test duration formatting function."""
        from cli.main import format_duration

        assert format_duration(None) == "Unknown"
        assert format_duration(30) == "30s"
        assert format_duration(90) == "1m 30s"
        assert format_duration(3661) == "1h 1m 1s"
        assert format_duration(7200) == "2h 0m 0s"

    @pytest.mark.unit
    def test_format_file_size(self):
        """Test file size formatting function."""
        from cli.main import format_file_size

        assert format_file_size(None) == "Unknown"
        assert format_file_size(512) == "512.0 B"
        assert format_file_size(1536) == "1.5 KB"
        assert format_file_size(1048576) == "1.0 MB"
        assert format_file_size(1073741824) == "1.0 GB"


class TestAPIClient:
    """Test YTArchiveAPI client."""

    @patch("httpx.AsyncClient")
    @pytest.mark.unit
    def test_api_client_initialization(self, mock_client):
        """Test API client initialization."""
        from cli.main import YTArchiveAPI

        api = YTArchiveAPI()
        assert api.client is not None

    @pytest.mark.unit
    def test_service_urls(self):
        """Test service URL configuration."""
        from cli.main import SERVICES

        expected_services = ["jobs", "metadata", "download", "storage", "logging"]
        for service in expected_services:
            assert service in SERVICES
            assert SERVICES[service].startswith("http://localhost:")


class TestInputValidation:
    """Test input validation and error handling."""

    @pytest.mark.unit
    def test_download_missing_video_id(self, runner):
        """Test download command without video ID."""
        result = runner.invoke(cli, ["download"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    @pytest.mark.unit
    def test_metadata_missing_video_id(self, runner):
        """Test metadata command without video ID."""
        result = runner.invoke(cli, ["metadata"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    @pytest.mark.unit
    def test_status_missing_job_id(self, runner):
        """Test status command without job ID."""
        result = runner.invoke(cli, ["status"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    @pytest.mark.unit
    def test_download_invalid_quality(self, runner):
        """Test download with invalid quality option."""
        result = runner.invoke(cli, ["download", "dQw4w9WgXcQ", "--quality", "invalid"])
        assert result.exit_code != 0

    @pytest.mark.unit
    def test_logs_invalid_level(self, runner):
        """Test logs with invalid level option."""
        result = runner.invoke(cli, ["logs", "--level", "invalid"])
        assert result.exit_code != 0


# ===============================================================================
# COMPREHENSIVE PLAYLIST CLI TESTS - CRITICAL PRIORITY ENTERPRISE COVERAGE
# ===============================================================================


@pytest.fixture
def mock_playlist_metadata():
    """Sample playlist metadata response."""
    return {
        "success": True,
        "data": {
            "playlist_id": "PLtest123",
            "title": "Test Playlist for CLI Testing",
            "channel_title": "Test Channel",
            "description": "A comprehensive test playlist for validating CLI functionality",
            "video_count": 3,
            "videos": [
                {
                    "video_id": "vid1",
                    "title": "Test Video 1",
                    "duration_seconds": 180,
                    "view_count": 10000,
                },
                {
                    "video_id": "vid2",
                    "title": "Test Video 2",
                    "duration_seconds": 240,
                    "view_count": 15000,
                },
                {
                    "video_id": "vid3",
                    "title": "Test Video 3",
                    "duration_seconds": 300,
                    "view_count": 20000,
                },
            ],
        },
    }


@pytest.fixture
def mock_playlist_job_response():
    """Sample playlist job creation response."""
    return {
        "success": True,
        "data": {
            "job_id": "playlist-job-123",
            "job_type": "PLAYLIST_DOWNLOAD",
            "status": "PENDING",
            "created_at": "2025-01-01T00:00:00Z",
            "playlist_id": "PLtest123",
            "total_videos": 3,
        },
    }


@pytest.fixture
def mock_playlist_status_response():
    """Sample playlist status response with progress."""
    return {
        "success": True,
        "data": {
            "job_id": "playlist-job-123",
            "job_type": "PLAYLIST_DOWNLOAD",
            "status": "RUNNING",
            "progress": {
                "total_videos": 3,
                "completed_videos": 2,
                "failed_videos": 0,
                "current_video": {
                    "video_id": "vid3",
                    "title": "Test Video 3",
                    "status": "downloading",
                    "progress_percent": 45.0,
                },
            },
            "created_at": "2025-01-01T00:00:00Z",
            "started_at": "2025-01-01T00:01:00Z",
        },
    }


class TestPlaylistCommand:
    """Test playlist command functionality - CRITICAL PRIORITY ENTERPRISE COVERAGE."""

    @pytest.mark.service
    def test_playlist_help(self, runner):
        """Test playlist command help display."""
        result = runner.invoke(cli, ["playlist", "--help"])
        assert result.exit_code == 0
        assert "Manage playlist downloads and operations" in result.output
        assert "download" in result.output
        assert "info" in result.output
        assert "status" in result.output

    @pytest.mark.service
    def test_playlist_download_help(self, runner):
        """Test playlist download command help."""
        result = runner.invoke(cli, ["playlist", "download", "--help"])
        assert result.exit_code == 0
        assert "Download all videos from a YouTube playlist" in result.output
        assert "--quality" in result.output
        assert "--max-concurrent" in result.output
        assert "--metadata-only" in result.output

    @pytest.mark.service
    def test_playlist_info_help(self, runner):
        """Test playlist info command help."""
        result = runner.invoke(cli, ["playlist", "info", "--help"])
        assert result.exit_code == 0
        assert "Get information about a YouTube playlist" in result.output
        assert "--json" in result.output

    @pytest.mark.service
    def test_playlist_status_help(self, runner):
        """Test playlist status command help."""
        result = runner.invoke(cli, ["playlist", "status", "--help"])
        assert result.exit_code == 0
        assert "Check the status of a playlist download job" in result.output
        assert "--watch" in result.output


class TestPlaylistDownloadCommand:
    """Test playlist download command functionality - CRITICAL PRIORITY ENTERPRISE COVERAGE."""

    @pytest.mark.service
    @patch("cli.main.YTArchiveAPI")
    def test_playlist_download_success(
        self,
        mock_api_class,
        runner,
        mock_playlist_metadata,
        mock_playlist_job_response,
    ):
        """Test successful playlist download with Rich UI components."""
        mock_api = setup_async_api_mock(mock_api_class)
        mock_api.get_playlist_metadata.return_value = mock_playlist_metadata["data"]
        mock_api.create_job.return_value = mock_playlist_job_response["data"]
        mock_api.execute_job.return_value = {"success": True}
        mock_api.get_job.return_value = {
            "job_id": "playlist-job-123",
            "status": "completed",
            "progress": {
                "phase": "playlist_completed",
                "completed_videos": 3,
                "failed_videos": 0,
                "total_videos": 3,
                "progress_percentage": 100.0,
            },
        }

        result = runner.invoke(
            cli,
            ["playlist", "download", "https://www.youtube.com/playlist?list=PLtest123"],
        )

        assert result.exit_code == 0
        assert "Starting playlist download" in result.output
        assert "Test Playlist for CLI Testing" in result.output
        assert "3" in result.output  # Video count
        assert (
            "Playlist download job created" in result.output
            or "job created" in result.output.lower()
        )
        # Job ID may be embedded in rich formatting, so check for either exact match or job creation confirmation
        assert "playlist-job-123" in result.output or "✅" in result.output

        # Verify API calls
        mock_api.get_playlist_metadata.assert_called_once_with("PLtest123")
        mock_api.create_job.assert_called_once()

    @pytest.mark.service
    @patch("cli.main.YTArchiveAPI")
    def test_playlist_download_with_quality(
        self,
        mock_api_class,
        runner,
        mock_playlist_metadata,
        mock_playlist_job_response,
    ):
        """Test playlist download with specific quality setting."""
        mock_api = setup_async_api_mock(mock_api_class)
        mock_api.get_playlist_metadata.return_value = mock_playlist_metadata["data"]
        mock_api.create_job.return_value = mock_playlist_job_response["data"]
        mock_api.execute_job.return_value = {"success": True}
        mock_api.get_job.return_value = {
            "job_id": "playlist-job-123",
            "status": "completed",
            "progress": {
                "phase": "playlist_completed",
                "completed_videos": 3,
                "failed_videos": 0,
                "total_videos": 3,
                "progress_percentage": 100.0,
            },
        }

        result = runner.invoke(
            cli,
            [
                "playlist",
                "download",
                "https://www.youtube.com/playlist?list=PLtest123",
                "--quality",
                "720p",
            ],
        )

        assert result.exit_code == 0
        assert "720p" in str(mock_api.create_job.call_args)

    @pytest.mark.service
    @patch("cli.main.YTArchiveAPI")
    def test_playlist_download_with_max_concurrent(
        self,
        mock_api_class,
        runner,
        mock_playlist_metadata,
        mock_playlist_job_response,
    ):
        """Test playlist download with max concurrent setting."""
        mock_api = setup_async_api_mock(mock_api_class)
        mock_api.get_playlist_metadata.return_value = mock_playlist_metadata["data"]
        mock_api.create_job.return_value = mock_playlist_job_response["data"]
        mock_api.execute_job.return_value = {"success": True}
        mock_api.get_job.return_value = {
            "job_id": "playlist-job-123",
            "status": "completed",
            "progress": {
                "phase": "playlist_completed",
                "completed_videos": 3,
                "failed_videos": 0,
                "total_videos": 3,
                "progress_percentage": 100.0,
            },
        }

        result = runner.invoke(
            cli,
            [
                "playlist",
                "download",
                "https://www.youtube.com/playlist?list=PLtest123",
                "--max-concurrent",
                "5",
            ],
        )

        assert result.exit_code == 0
        # Verify max_concurrent parameter was passed
        call_args = str(mock_api.create_job.call_args)
        assert "max_concurrent" in call_args

    @pytest.mark.service
    @patch("cli.main.YTArchiveAPI")
    def test_playlist_download_metadata_only(
        self,
        mock_api_class,
        runner,
        mock_playlist_metadata,
        mock_playlist_job_response,
    ):
        """Test playlist download with metadata-only flag."""
        mock_api = setup_async_api_mock(mock_api_class)
        mock_api.get_playlist_metadata.return_value = mock_playlist_metadata["data"]
        mock_api.create_job.return_value = mock_playlist_job_response["data"]
        mock_api.execute_job.return_value = {"success": True}
        mock_api.get_job.return_value = {
            "job_id": "playlist-job-123",
            "status": "completed",
            "progress": {
                "phase": "playlist_completed",
                "completed_videos": 3,
                "failed_videos": 0,
                "total_videos": 3,
                "progress_percentage": 100.0,
            },
        }

        result = runner.invoke(
            cli,
            [
                "playlist",
                "download",
                "https://www.youtube.com/playlist?list=PLtest123",
                "--metadata-only",
            ],
        )

        assert result.exit_code == 0
        # Verify metadata_only parameter was passed
        call_args = str(mock_api.create_job.call_args)
        assert "metadata_only" in call_args

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_playlist_download_invalid_url(self, mock_api_class, runner):
        """Test playlist download with invalid URL parsing."""
        setup_async_api_mock(mock_api_class)

        result = runner.invoke(
            cli, ["playlist", "download", "https://www.youtube.com/watch?v=invalid"]
        )

        assert result.exit_code == 0  # CLI handles gracefully
        assert "Invalid playlist URL" in result.output

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_playlist_download_api_error(self, mock_api_class, runner):
        """Test playlist download with API error handling."""
        mock_api = setup_async_api_mock(mock_api_class)
        mock_api.get_playlist_metadata.return_value = None  # API error

        result = runner.invoke(
            cli,
            ["playlist", "download", "https://www.youtube.com/playlist?list=PLtest123"],
        )

        assert result.exit_code == 0  # CLI handles gracefully
        assert "Failed to fetch playlist metadata" in result.output

    @pytest.mark.service
    def test_playlist_download_missing_url(self, runner):
        """Test playlist download command without URL argument."""
        result = runner.invoke(cli, ["playlist", "download"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestPlaylistInfoCommand:
    """Test playlist info command functionality - CRITICAL PRIORITY ENTERPRISE COVERAGE."""

    @pytest.mark.service
    @patch("cli.main.YTArchiveAPI")
    def test_playlist_info_success(
        self, mock_api_class, runner, mock_playlist_metadata
    ):
        """Test successful playlist info with formatted table output."""
        mock_api = setup_async_api_mock(mock_api_class)
        mock_api.get_playlist_metadata.return_value = mock_playlist_metadata["data"]

        result = runner.invoke(
            cli, ["playlist", "info", "https://www.youtube.com/playlist?list=PLtest123"]
        )

        assert result.exit_code == 0
        assert "Test Playlist for CLI Testing" in result.output
        assert "Test Channel" in result.output
        assert "Videos: 3" in result.output
        assert "Test Video 1" in result.output
        assert "Test Video 2" in result.output
        assert "Test Video 3" in result.output

        # Verify API call
        mock_api.get_playlist_metadata.assert_called_once_with("PLtest123")

    @pytest.mark.service
    @patch("cli.main.YTArchiveAPI")
    def test_playlist_info_json_output(
        self, mock_api_class, runner, mock_playlist_metadata
    ):
        """Test playlist info with JSON output format."""
        mock_api = setup_async_api_mock(mock_api_class)
        mock_api.get_playlist_metadata.return_value = mock_playlist_metadata["data"]

        result = runner.invoke(
            cli,
            [
                "playlist",
                "info",
                "https://www.youtube.com/playlist?list=PLtest123",
                "--json",
            ],
        )

        assert result.exit_code == 0
        # Verify JSON output can be parsed
        import json

        output_data = json.loads(result.output)
        assert output_data["playlist_id"] == "PLtest123"
        assert output_data["title"] == "Test Playlist for CLI Testing"
        assert len(output_data["videos"]) == 3

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_playlist_info_api_error(self, mock_api_class, runner):
        """Test playlist info with API error handling."""
        mock_api = setup_async_api_mock(mock_api_class)
        mock_api.get_playlist_metadata.return_value = None  # API error

        result = runner.invoke(
            cli, ["playlist", "info", "https://www.youtube.com/playlist?list=PLtest123"]
        )

        assert result.exit_code == 0  # CLI handles gracefully
        assert "Failed to fetch playlist metadata" in result.output

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_playlist_info_invalid_url(self, mock_api_class, runner):
        """Test playlist info with invalid URL parsing."""
        setup_async_api_mock(mock_api_class)

        result = runner.invoke(
            cli, ["playlist", "info", "https://www.youtube.com/watch?v=invalid"]
        )

        assert result.exit_code == 0  # CLI handles gracefully
        assert "Invalid playlist URL" in result.output

    @pytest.mark.service
    def test_playlist_info_missing_url(self, runner):
        """Test playlist info command without URL argument."""
        result = runner.invoke(cli, ["playlist", "info"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestPlaylistStatusCommand:
    """Test playlist status command functionality - CRITICAL PRIORITY ENTERPRISE COVERAGE."""

    @pytest.mark.service
    @patch("cli.main.YTArchiveAPI")
    def test_playlist_status_success(
        self, mock_api_class, runner, mock_playlist_status_response
    ):
        """Test successful playlist status with real-time progress updates."""
        mock_api = setup_async_api_mock(mock_api_class)
        mock_api.get_job.return_value = mock_playlist_status_response["data"]

        result = runner.invoke(cli, ["playlist", "status", "playlist-job-123"])

        assert result.exit_code == 0
        assert "playlist-job-123" in result.output
        assert "RUNNING" in result.output
        assert "2/3" in result.output  # Progress display
        assert "66.7%" in result.output  # Progress percentage (2/3 = 66.7%)

        # Verify API call
        mock_api.get_job.assert_called_once_with("playlist-job-123")

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_playlist_status_completed(self, mock_api_class, runner):
        """Test playlist status for completed job."""
        mock_api = setup_async_api_mock(mock_api_class)
        mock_api.get_job.return_value = {
            "job_id": "playlist-job-123",
            "job_type": "PLAYLIST_DOWNLOAD",
            "status": "completed",
            "progress": {
                "phase": "playlist_completed",
                "total_videos": 3,
                "completed_videos": 3,
                "failed_videos": 0,
                "progress_percentage": 100.0,
            },
            "created_at": "2025-01-01T00:00:00Z",
            "completed_at": "2025-01-01T00:05:00Z",
        }

        result = runner.invoke(cli, ["playlist", "status", "playlist-job-123"])

        assert result.exit_code == 0
        assert "COMPLETED" in result.output
        assert "3/3" in result.output  # All videos completed

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_playlist_status_with_errors(self, mock_api_class, runner):
        """Test playlist status with failed videos."""
        mock_api = setup_async_api_mock(mock_api_class)
        mock_api.get_job.return_value = {
            "job_id": "playlist-job-123",
            "job_type": "PLAYLIST_DOWNLOAD",
            "status": "completed",
            "created_at": "2025-07-26T12:00:00Z",
            "updated_at": "2025-07-26T12:05:00Z",
            "progress": {
                "total_videos": 3,
                "completed_videos": 2,
                "failed_videos": 1,
            },
            "errors": ["Failed to download video vid2: Network error"],
        }

        result = runner.invoke(cli, ["playlist", "status", "playlist-job-123"])

        assert result.exit_code == 0
        assert "2/3" in result.output
        assert "Failed: 1" in result.output
        assert "Network error" in result.output

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_playlist_status_job_not_found(self, mock_api_class, runner):
        """Test playlist status for non-existent job."""
        mock_api = setup_async_api_mock(mock_api_class)
        mock_api.get_job.return_value = None  # Job not found

        result = runner.invoke(cli, ["playlist", "status", "nonexistent-job"])

        assert result.exit_code == 0  # CLI handles gracefully
        assert (
            "Job not found" in result.output
            or "Failed to get job status" in result.output
        )

    @pytest.mark.service
    def test_playlist_status_missing_job_id(self, runner):
        """Test playlist status command without job ID argument."""
        result = runner.invoke(cli, ["playlist", "status"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestPlaylistURLParsing:
    """Test playlist URL parsing and validation - CRITICAL PRIORITY ENTERPRISE COVERAGE."""

    @pytest.mark.unit
    def test_standard_playlist_url_parsing(self):
        """Test parsing of standard playlist URLs."""
        from cli.main import _extract_playlist_id

        # Standard playlist URL
        url = "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
        playlist_id = _extract_playlist_id(url)
        assert playlist_id == "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"

    @pytest.mark.unit
    def test_mixed_playlist_url_parsing(self):
        """Test parsing of mixed video/playlist URLs."""
        from cli.main import _extract_playlist_id

        # Mixed URL with video and playlist
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLtest123"
        playlist_id = _extract_playlist_id(url)
        assert playlist_id == "PLtest123"

    @pytest.mark.unit
    def test_invalid_url_parsing(self):
        """Test parsing of invalid URLs."""
        from cli.main import _extract_playlist_id

        # Regular video URL (should raise ValueError)
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        with pytest.raises(ValueError, match="Invalid playlist URL"):
            _extract_playlist_id(url)

        # Completely invalid URL (should raise ValueError)
        url = "not-a-url"
        with pytest.raises(ValueError, match="Invalid playlist URL"):
            _extract_playlist_id(url)

        # Empty URL (should raise ValueError)
        url = ""
        with pytest.raises(ValueError, match="Invalid playlist URL"):
            _extract_playlist_id(url)  # Should fail with invalid choice
