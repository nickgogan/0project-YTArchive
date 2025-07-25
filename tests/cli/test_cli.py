"""Comprehensive tests for YTArchive CLI."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from cli.main import cli


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
        mock_api = AsyncMock()
        mock_api.__aenter__.return_value = mock_api
        mock_api_class.return_value = mock_api

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
        mock_api = AsyncMock()
        mock_api.__aenter__.return_value = mock_api
        mock_api_class.return_value = mock_api

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
        mock_api = AsyncMock()
        mock_api.__aenter__.return_value = mock_api
        mock_api_class.return_value = mock_api

        # Mock API responses
        mock_api.check_video_exists.return_value = {
            "success": True,
            "data": {"exists": False},
        }
        mock_api.get_video_metadata.return_value = mock_api_response
        mock_api.start_download.return_value = mock_download_response
        mock_api.get_download_progress.return_value = mock_progress_response

        result = runner.invoke(cli, ["download", "dQw4w9WgXcQ", "--quality", "720p"])

        assert result.exit_code == 0
        assert mock_api.start_download.called
        # Verify quality was passed correctly
        call_args = mock_api.start_download.call_args
        assert call_args[0][1] == "720p"  # quality parameter

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_download_api_error(self, mock_api_class, runner):
        """Test download with API error."""
        # Setup mock
        mock_api = AsyncMock()
        mock_api.__aenter__.return_value = mock_api
        mock_api_class.return_value = mock_api

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
        mock_api = AsyncMock()
        mock_api.__aenter__.return_value = mock_api
        mock_api_class.return_value = mock_api

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
        mock_api = AsyncMock()
        mock_api.__aenter__.return_value = mock_api
        mock_api_class.return_value = mock_api

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
        mock_api = AsyncMock()
        mock_api.__aenter__.return_value = mock_api
        mock_api_class.return_value = mock_api

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
        mock_api = AsyncMock()
        mock_api.__aenter__.return_value = mock_api
        mock_api_class.return_value = mock_api

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
        mock_api = AsyncMock()
        mock_api.__aenter__.return_value = mock_api
        mock_api_class.return_value = mock_api

        mock_api.get_job.return_value = {"success": False, "error": "Job not found"}

        result = runner.invoke(cli, ["status", "nonexistent-job"])

        assert result.exit_code == 0
        assert "Job not found" in result.output

    @patch("cli.main.YTArchiveAPI")
    @pytest.mark.service
    def test_status_with_error(self, mock_api_class, runner):
        """Test status display with job error."""
        # Setup mock
        mock_api = AsyncMock()
        mock_api.__aenter__.return_value = mock_api
        mock_api_class.return_value = mock_api

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
        mock_api = AsyncMock()
        mock_api.__aenter__.return_value = mock_api
        mock_api_class.return_value = mock_api

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
        mock_api = AsyncMock()
        mock_api.__aenter__.return_value = mock_api
        mock_api_class.return_value = mock_api

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
        mock_api = AsyncMock()
        mock_api.__aenter__.return_value = mock_api
        mock_api_class.return_value = mock_api

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

    @pytest.mark.service
    def test_download_missing_video_id(self, runner):
        """Test download command without video ID."""
        result = runner.invoke(cli, ["download"])
        assert result.exit_code != 0  # Should fail with missing argument

    @pytest.mark.service
    def test_metadata_missing_video_id(self, runner):
        """Test metadata command without video ID."""
        result = runner.invoke(cli, ["metadata"])
        assert result.exit_code != 0  # Should fail with missing argument

    @pytest.mark.service
    def test_status_missing_job_id(self, runner):
        """Test status command without job ID."""
        result = runner.invoke(cli, ["status"])
        assert result.exit_code != 0  # Should fail with missing argument

    @pytest.mark.service
    def test_download_invalid_quality(self, runner):
        """Test download with invalid quality option."""
        result = runner.invoke(cli, ["download", "dQw4w9WgXcQ", "--quality", "invalid"])
        assert result.exit_code != 0  # Should fail with invalid choice

    @pytest.mark.service
    def test_logs_invalid_level(self, runner):
        """Test logs with invalid level option."""
        result = runner.invoke(cli, ["logs", "--level", "INVALID"])
        assert result.exit_code != 0  # Should fail with invalid choice
