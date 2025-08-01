"""Comprehensive tests for download command flag functionality."""

import json
import pytest
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

# Import the command we want to test
from cli.main import download


@pytest.mark.unit
@pytest.mark.cli
class TestDownloadCommandFlags:
    """Test suite for download command flags functionality."""

    @pytest.fixture
    def mock_video_formats(self):
        """Mock video formats data."""
        return {
            "video_id": "test_video_id",
            "formats": [
                {"format_id": "137", "resolution": "1080p", "format_note": "Premium"},
                {"format_id": "136", "resolution": "720p", "format_note": "High"},
            ],
            "audio_formats": [
                {
                    "format_id": "140",
                    "quality": "audio_128k",
                    "format_note": "High quality audio",
                }
            ],
        }

    @pytest.mark.service
    def test_format_list_displays_table(self, mock_video_formats):
        """Test --format-list flag triggers API call and displays a table."""
        runner = CliRunner()
        with patch("cli.main.YTArchiveAPI", autospec=True) as mock_api_class:
            mock_api_instance = mock_api_class.return_value
            # ✅ CRITICAL: Set up async context manager methods following WatchOut pattern
            mock_api_instance.__aenter__.return_value = mock_api_instance
            mock_api_instance.__aexit__.return_value = None
            mock_api_instance.get_video_formats = AsyncMock(
                return_value=mock_video_formats
            )

            result = runner.invoke(download, ["--format-list", "test_video_id"])

            assert result.exit_code == 0, result.output
            mock_api_instance.get_video_formats.assert_called_once_with("test_video_id")
            assert "Available Formats" in result.output
            assert "1080p" in result.output
            assert "Premium" in result.output
            assert "Audio Formats" in result.output

    @pytest.mark.service
    def test_format_list_displays_json(self, mock_video_formats):
        """Test --format-list with --json flag produces correct JSON output."""
        runner = CliRunner()
        with patch("cli.main.YTArchiveAPI", autospec=True) as mock_api_class:
            mock_api_instance = mock_api_class.return_value
            # ✅ CRITICAL: Set up async context manager methods following WatchOut pattern
            mock_api_instance.__aenter__.return_value = mock_api_instance
            mock_api_instance.__aexit__.return_value = None
            mock_api_instance.get_video_formats = AsyncMock(
                return_value=mock_video_formats
            )

            result = runner.invoke(
                download, ["--format-list", "--json", "test_video_id"]
            )

            assert result.exit_code == 0, result.output
            mock_api_instance.get_video_formats.assert_called_once_with("test_video_id")

            output_json = json.loads(result.output)
            assert output_json == mock_video_formats

    @pytest.mark.parametrize(
        "strategy_param, expected_retry_config",
        [
            (
                "exponential:max_attempts=5,base_delay=2",
                {"retry_strategy": "exponential", "max_attempts": 5, "base_delay": 2},
            ),
            (
                "circuit_breaker:failure_threshold=10",
                {"retry_strategy": "circuit_breaker", "failure_threshold": 10},
            ),
            ("adaptive", {"retry_strategy": "adaptive"}),
            (
                "fixed_delay:delay=5,max_attempts=3",
                {"retry_strategy": "fixed_delay", "delay": 5, "max_attempts": 3},
            ),
        ],
    )
    @pytest.mark.service
    def test_retry_config_flag_passes_correct_config(
        self, strategy_param, expected_retry_config
    ):
        """Test that --retry-config correctly configures the API call."""
        runner = CliRunner()
        with patch("cli.main.YTArchiveAPI", autospec=True) as mock_api_class:
            mock_api_instance = mock_api_class.return_value
            # ✅ CRITICAL: Set up async context manager methods following WatchOut pattern
            mock_api_instance.__aenter__.return_value = mock_api_instance
            mock_api_instance.__aexit__.return_value = None

            # Mock required API methods for download workflow
            mock_api_instance.check_video_exists = AsyncMock(
                return_value={"success": True, "data": {"exists": False}}
            )
            mock_api_instance.get_video_metadata = AsyncMock(
                return_value={"success": True, "data": {"title": "Test Video"}}
            )
            mock_api_instance.create_job = AsyncMock(
                return_value={"job_id": "job-123", "status": "pending"}
            )
            mock_api_instance.get_job = AsyncMock(
                return_value={
                    "success": True,
                    "data": {"job_id": "job-123", "status": "COMPLETED"},
                }
            )
            mock_api_instance.monitor_job = AsyncMock(
                return_value={"job_id": "job-123", "status": "completed"}
            )
            # ✅ WatchOut Pattern: Mock all async API methods that get called
            mock_api_instance.execute_job = AsyncMock(
                return_value={"task_id": "task-456", "status": "started"}
            )
            mock_api_instance.get_download_progress = AsyncMock(
                return_value={
                    "state": "SUCCESS",
                    "result": {"output_path": "/tmp/video.mp4"},
                }
            )

            result = runner.invoke(
                download, ["--retry-config", strategy_param, "test_video_id"]
            )

            assert result.exit_code == 0, result.output
            mock_api_instance.create_job.assert_called_once()

            call_kwargs = mock_api_instance.create_job.call_args.kwargs
            job_config = call_kwargs.get("config", {})

            # Check that the retry config is properly merged into the job config
            for key, value in expected_retry_config.items():
                assert (
                    job_config.get(key) == value
                ), f"Expected {key}={value}, got {job_config.get(key)}"

            # Verify standard job config fields are present
            assert job_config.get("quality") == "best"  # Default quality
            assert "output_path" in job_config

    @pytest.mark.service
    def test_retry_config_flag_invalid_strategy(self):
        """Test --retry-config flag with invalid strategy."""
        runner = CliRunner()
        result = runner.invoke(
            download, ["--retry-config", "invalid_strategy:foo=bar", "test_video_id"]
        )

        assert result.exit_code != 0
        assert "Invalid value for '--retry-config'" in result.output

    @pytest.mark.service
    def test_format_list_flag_api_error_handling(self):
        """Test --format-list flag with API error handling."""
        runner = CliRunner()
        with patch("cli.main.YTArchiveAPI", autospec=True) as mock_api_class:
            mock_api_instance = mock_api_class.return_value
            # ✅ CRITICAL: Set up async context manager methods following WatchOut pattern
            mock_api_instance.__aenter__.return_value = mock_api_instance
            mock_api_instance.__aexit__.return_value = None
            mock_api_instance.get_video_formats = AsyncMock(
                side_effect=Exception("API is down")
            )

            result = runner.invoke(download, ["--format-list", "test_video_id"])

            assert result.exit_code != 0
            assert "API is down" in result.output
