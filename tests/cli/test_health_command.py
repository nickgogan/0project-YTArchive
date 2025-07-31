"""Comprehensive tests for the health command functionality."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from rich.console import Console
from click.testing import CliRunner

# Import the functions we want to test
from cli.main import _check_system_health, _display_health_status


@pytest.mark.unit
@pytest.mark.cli
class TestHealthCommand:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    """Test suite for health command functionality."""

    @pytest.fixture
    def mock_ytarchive_api(self):
        """Mock YTArchiveAPI for testing."""
        api_mock = AsyncMock()
        api_mock.client = AsyncMock()
        return api_mock

    @pytest.fixture
    def mock_health_response(self):
        """Mock successful health response."""
        return MagicMock(
            status_code=200,
            elapsed=MagicMock(total_seconds=MagicMock(return_value=0.05)),
            json=MagicMock(return_value={"status": "healthy", "service": "test"}),
        )

    @pytest.fixture
    def mock_unhealthy_response(self):
        """Mock unhealthy service response."""
        return MagicMock(
            status_code=500,
            elapsed=MagicMock(total_seconds=MagicMock(return_value=0.1)),
        )

    @pytest.mark.asyncio
    async def test_check_system_health_all_services_healthy(
        self, mock_ytarchive_api, mock_health_response
    ):
        """Test health check when all services are healthy."""
        # Set up async context manager properly
        mock_ytarchive_api.__aenter__.return_value = mock_ytarchive_api
        mock_ytarchive_api.__aexit__.return_value = None

        # Mock the API client get method to return healthy responses
        mock_ytarchive_api.client.get.return_value = mock_health_response

        with patch("cli.main.YTArchiveAPI", return_value=mock_ytarchive_api):
            with patch("cli.main.console.print") as mock_print:
                await _check_system_health(json_output=True, detailed=False)

                # Verify all services were checked
                assert mock_ytarchive_api.client.get.call_count == 5

                # Verify print was called with JSON output
                mock_print.assert_called_once()
                call_args = mock_print.call_args[0][0]

                # Parse the JSON output
                health_data = json.loads(call_args)
                assert health_data["overall_status"] == "healthy"
                assert len(health_data["services"]) == 5
                assert len(health_data["issues"]) == 0

                # Check each service is marked as healthy
                for service_name in [
                    "jobs",
                    "metadata",
                    "storage",
                    "download",
                    "logging",
                ]:
                    assert service_name in health_data["services"]
                    assert health_data["services"][service_name]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_check_system_health_service_unavailable(self, mock_ytarchive_api):
        """Test health check when a service is unavailable."""
        # Set up async context manager properly
        mock_ytarchive_api.__aenter__.return_value = mock_ytarchive_api
        mock_ytarchive_api.__aexit__.return_value = None

        # Mock one service to raise an exception (unavailable)
        def mock_get_side_effect(url, **kwargs):
            if "8002" in url:  # metadata service
                raise ConnectionError("Connection refused")
            return MagicMock(
                status_code=200,
                elapsed=MagicMock(total_seconds=MagicMock(return_value=0.05)),
                json=MagicMock(return_value={"status": "healthy"}),
            )

        mock_ytarchive_api.client.get.side_effect = mock_get_side_effect

        with patch("cli.main.YTArchiveAPI", return_value=mock_ytarchive_api):
            with patch("cli.main.console.print") as mock_print:
                await _check_system_health(json_output=True, detailed=False)

                # Verify print was called
                mock_print.assert_called_once()
                call_args = mock_print.call_args[0][0]

                # Parse the JSON output
                health_data = json.loads(call_args)
                # May be degraded if some services are unavailable
                assert health_data["overall_status"] in ["unhealthy", "degraded"]
                assert len(health_data["issues"]) == 1
                assert "metadata service unavailable" in health_data["issues"][0]

                # Check metadata service is marked as unavailable
                assert health_data["services"]["metadata"]["status"] == "unavailable"
                assert (
                    "Connection refused" in health_data["services"]["metadata"]["error"]
                )

    @pytest.mark.asyncio
    async def test_check_system_health_service_unhealthy_status(
        self, mock_ytarchive_api, mock_unhealthy_response
    ):
        """Test health check when a service returns unhealthy status."""
        # Set up async context manager properly
        mock_ytarchive_api.__aenter__.return_value = mock_ytarchive_api
        mock_ytarchive_api.__aexit__.return_value = None

        def mock_get_side_effect(url, **kwargs):
            if "8003" in url:  # storage service
                return mock_unhealthy_response
            return MagicMock(
                status_code=200,
                elapsed=MagicMock(total_seconds=MagicMock(return_value=0.05)),
                json=MagicMock(return_value={"status": "healthy"}),
            )

        mock_ytarchive_api.client.get.side_effect = mock_get_side_effect

        with patch("cli.main.YTArchiveAPI", return_value=mock_ytarchive_api):
            with patch("cli.main.console.print") as mock_print:
                await _check_system_health(json_output=True, detailed=False)

                # Verify print was called
                mock_print.assert_called_once()
                call_args = mock_print.call_args[0][0]

                # Parse the JSON output
                health_data = json.loads(call_args)
                assert health_data["overall_status"] == "degraded"
                assert len(health_data["issues"]) == 1
                assert "storage service returned 500" in health_data["issues"][0]

                # Check storage service is marked as unhealthy
                assert health_data["services"]["storage"]["status"] == "unhealthy"
                assert "HTTP 500" in health_data["services"]["storage"]["error"]

    @pytest.mark.asyncio
    @patch("cli.main.psutil", autospec=True)
    async def test_check_system_health_detailed_mode(
        self, mock_psutil, mock_ytarchive_api, mock_health_response
    ):
        """Test health check with detailed system information."""
        # Arrange: Configure the mocks to simulate a healthy system
        mock_psutil.cpu_percent.return_value = 25.5
        mock_psutil.virtual_memory.return_value.percent = 60.2
        mock_psutil.disk_usage.return_value.free = 100 * (1024**3)
        mock_psutil.pids.return_value = list(range(150))

        mock_ytarchive_api.__aenter__.return_value.client.get.return_value = (
            mock_health_response
        )

        with patch("cli.main.YTArchiveAPI", return_value=mock_ytarchive_api):
            # Act: Call the function directly
            health_data = await _check_system_health(json_output=False, detailed=True)

        # Assert: Check the returned data
        assert "system" in health_data
        assert health_data["system"]["cpu_percent"] == 25.5

    @pytest.mark.asyncio
    async def test_check_system_health_missing_critical_directories(
        self, mock_ytarchive_api, mock_health_response
    ):
        """Test health check when critical directories are missing."""
        # Set up async context manager properly
        mock_ytarchive_api.__aenter__.return_value = mock_ytarchive_api
        mock_ytarchive_api.__aexit__.return_value = None

        mock_ytarchive_api.client.get.return_value = mock_health_response

        with patch("cli.main.YTArchiveAPI", return_value=mock_ytarchive_api):
            with patch(
                "pathlib.Path.exists", return_value=False
            ):  # All directories missing
                with patch("cli.main.console.print") as mock_print:
                    await _check_system_health(json_output=True, detailed=True)

                    # Verify print was called
                    mock_print.assert_called_once()
                    call_args = mock_print.call_args[0][0]

                    # Parse the JSON output
                    health_data = json.loads(call_args)
                    assert health_data["overall_status"] == "degraded"
                    assert len(health_data["issues"]) >= 2  # Missing logs and logs/temp

                    # Check for critical directory issues
                    issues_text = " ".join(health_data["issues"])
                    assert "Critical directory missing: logs" in issues_text
                    assert "Critical directory missing: logs/temp" in issues_text

    @pytest.mark.asyncio
    async def test_check_system_health_exception_handling(self, mock_ytarchive_api):
        """Test health check exception handling."""
        with patch(
            "cli.main.YTArchiveAPI", side_effect=Exception("API initialization failed")
        ):
            with patch("cli.main.console.print") as mock_print:
                await _check_system_health(json_output=True, detailed=False)

                # Verify error handling
                mock_print.assert_called_once()
                call_args = mock_print.call_args[0][0]

                # Parse the JSON output
                error_data = json.loads(call_args)
                assert error_data["overall_status"] == "error"
                assert "API initialization failed" in error_data["error"]

    def test_display_health_status_healthy_system(self):
        """Test display of healthy system status."""
        health_data = {
            "overall_status": "healthy",
            "services": {
                "jobs": {"status": "healthy", "response_time_ms": 45.2},
                "metadata": {"status": "healthy", "response_time_ms": 32.1},
            },
            "issues": [],
        }

        with patch("cli.main.console.print") as mock_print:
            _display_health_status(health_data)

            # Verify console.print was called multiple times
            assert mock_print.call_count >= 3

            # Check that healthy status is displayed
            calls = [str(call) for call in mock_print.call_args_list]
            status_calls = [call for call in calls if "System Status: HEALTHY" in call]
            assert len(status_calls) == 1

    def test_display_health_status_with_issues(self):
        """Test display of system status with issues."""
        health_data = {
            "overall_status": "unhealthy",
            "services": {
                "jobs": {"status": "healthy", "response_time_ms": 45.2},
                "metadata": {"status": "unavailable", "error": "Connection refused"},
            },
            "issues": ["metadata service unavailable: Connection refused"],
        }

        with patch("cli.main.console.print") as mock_print:
            _display_health_status(health_data)

            # Verify console.print was called multiple times
            assert mock_print.call_count >= 3

            # Check that issues are displayed
            calls = [str(call) for call in mock_print.call_args_list]
            issue_calls = [call for call in calls if "Issues Detected" in call]
            assert len(issue_calls) == 1

    def test_display_health_status_with_system_info(self):
        """Test display of system status with detailed system information."""
        health_data = {
            "overall_status": "healthy",
            "services": {"jobs": {"status": "healthy", "response_time_ms": 45.2}},
            "system": {
                "cpu_percent": 35.5,
                "memory_percent": 45.2,
                "disk_usage": {"free_space_gb": 150.5, "logs": 25 * 1024 * 1024},
                "process_count": 120,
            },
            "issues": [],
        }

        test_console = Console(record=True, width=120)
        _display_health_status(health_data, console=test_console)

        output = test_console.export_text()
        assert "System Resources" in output
