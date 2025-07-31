"""Comprehensive tests for the diagnostics command functionality."""

import json
import pytest
from unittest.mock import AsyncMock, patch
from click.testing import CliRunner
from rich.console import Console

# Import the functions we want to test
from cli.main import _display_diagnostics_results, diagnostics


@pytest.mark.unit
@pytest.mark.cli
class TestDiagnosticsCommand:
    """Test suite for diagnostics command functionality."""

    @pytest.fixture
    def runner(self):
        """Create Click test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_system_info(self):
        """Mock system information."""
        return {
            "platform": "macOS-13.0-arm64-arm-64bit",
            "python_version": "3.13.3",
            "architecture": "64bit",
            "cpu_count": 8,
            "total_memory_gb": 16.0,
            "hostname": "test-machine",
        }

    @pytest.fixture
    def mock_pip_list_output(self):
        """Mock pip list JSON output."""
        return json.dumps(
            [
                {"name": "httpx", "version": "0.25.2"},
                {"name": "pydantic", "version": "2.9.0"},
                {"name": "click", "version": "8.1.7"},
                {"name": "yt-dlp", "version": "2023.11.16"},
                {"name": "rich", "version": "13.7.0"},
                {"name": "psutil", "version": "7.0.0"},
                {"name": "pytest", "version": "7.4.3"},
            ]
        )

    @pytest.fixture
    def mock_performance_metrics(self):
        """Mock system performance metrics."""
        return {
            "cpu_percent": 25.5,
            "memory_percent": 60.2,
            "disk_usage_percent": 45.8,
            "load_average": [1.2, 1.1, 1.0],
            "boot_time": 1640995200.0,
        }

    @pytest.fixture
    def base_diagnostics_data(self):
        """Provide a base structure for diagnostics data."""
        return {
            "timestamp": "2023-01-01T00:00:00",
            "system_info": {},
            "python_environment": {},
            "ytarchive_config": {},
            "testing_infrastructure": {},
            "directory_structure": {},
            "performance_metrics": {},
            "recommendations": [],
            "overall_status": "healthy",
        }

    @patch("cli.main._run_system_diagnostics", new_callable=AsyncMock)
    def test_run_system_diagnostics_basic(
        self, mock_run_diagnostics, runner, base_diagnostics_data, mock_system_info
    ):
        """Test basic system diagnostics without additional flags."""
        base_diagnostics_data["system_info"] = mock_system_info
        mock_run_diagnostics.return_value = base_diagnostics_data

        result = runner.invoke(diagnostics, ["--json"])

        assert result.exit_code == 0
        mock_run_diagnostics.assert_awaited_once()

    @patch("cli.main._run_system_diagnostics", new_callable=AsyncMock)
    def test_run_system_diagnostics_with_pip_packages(
        self, mock_run_diagnostics, runner, base_diagnostics_data, mock_pip_list_output
    ):
        """Test diagnostics with Python environment information."""
        pip_data = {"pip_packages": json.loads(mock_pip_list_output)}
        base_diagnostics_data["python_environment"] = pip_data
        mock_run_diagnostics.return_value = base_diagnostics_data

        result = runner.invoke(diagnostics, ["--json"])

        assert result.exit_code == 0
        mock_run_diagnostics.assert_awaited_once()

    @patch("cli.main._run_system_diagnostics", new_callable=AsyncMock)
    def test_run_system_diagnostics_with_config_check(
        self, mock_run_diagnostics, runner, base_diagnostics_data
    ):
        """Test diagnostics with configuration validation."""
        config_data = {"issues": ["Missing 'config.toml'"], "overall_status": "warning"}
        base_diagnostics_data["ytarchive_config"] = config_data
        base_diagnostics_data["overall_status"] = "warning"
        mock_run_diagnostics.return_value = base_diagnostics_data

        result = runner.invoke(diagnostics, ["--json", "--check-config"])

        assert result.exit_code == 0
        mock_run_diagnostics.assert_awaited_once()

    @patch("cli.main._run_system_diagnostics", new_callable=AsyncMock)
    def test_run_system_diagnostics_with_test_execution(
        self, mock_run_diagnostics, runner, base_diagnostics_data
    ):
        """Test diagnostics with test execution."""
        test_infra = {
            "unit_tests": {"status": "passing", "exit_code": 0, "summary": "15 passed"}
        }
        base_diagnostics_data["testing_infrastructure"] = test_infra
        mock_run_diagnostics.return_value = base_diagnostics_data

        result = runner.invoke(diagnostics, ["--json", "--run-tests"])

        assert result.exit_code == 0
        mock_run_diagnostics.assert_awaited_once()

    @patch("cli.main._run_system_diagnostics", new_callable=AsyncMock)
    def test_run_system_diagnostics_failed_tests(
        self, mock_run_diagnostics, runner, base_diagnostics_data
    ):
        """Test diagnostics with failed test execution."""
        test_infra = {
            "unit_tests": {"status": "failed", "exit_code": 1, "summary": "1 failed"}
        }
        base_diagnostics_data["testing_infrastructure"] = test_infra
        base_diagnostics_data["overall_status"] = "error"
        mock_run_diagnostics.return_value = base_diagnostics_data

        result = runner.invoke(diagnostics, ["--json", "--run-tests"])

        assert result.exit_code == 0
        mock_run_diagnostics.assert_awaited_once()

    @patch("cli.main._run_system_diagnostics", new_callable=AsyncMock)
    def test_run_system_diagnostics_performance_warnings(
        self, mock_run_diagnostics, runner, base_diagnostics_data
    ):
        """Test diagnostics with high resource usage generating warnings."""
        perf_data = {
            "performance_metrics": {
                "cpu_percent": 95.0,
                "memory_percent": 85.0,
                "disk_usage_percent": 95.0,
            },
            "recommendations": ["High CPU usage detected", "Low disk space"],
            "overall_status": "attention_needed",
        }
        base_diagnostics_data.update(perf_data)
        mock_run_diagnostics.return_value = base_diagnostics_data

        result = runner.invoke(diagnostics, ["--json"])

        assert result.exit_code == 0
        mock_run_diagnostics.assert_awaited_once()

    @patch(
        "cli.main._run_system_diagnostics",
        new_callable=AsyncMock,
        side_effect=Exception("Platform error"),
    )
    def test_run_system_diagnostics_exception_handling(
        self, mock_run_diagnostics, runner
    ):
        """Test diagnostics command exception handling."""
        result = runner.invoke(diagnostics, ["--json"], catch_exceptions=True)

        assert result.exit_code == 1
        assert isinstance(result.exception, Exception)
        assert "Platform error" in str(result.exception)

    @patch("cli.main._run_system_diagnostics", new_callable=AsyncMock)
    def test_run_system_diagnostics_directory_analysis(
        self, mock_run_diagnostics, runner, base_diagnostics_data
    ):
        """Test directory structure analysis in diagnostics."""
        dir_data = {
            "directory_structure": {
                "services": {"exists": True, "file_count": 10},
                "tests": {"exists": True, "file_count": 50},
            }
        }
        base_diagnostics_data.update(dir_data)
        mock_run_diagnostics.return_value = base_diagnostics_data

        result = runner.invoke(diagnostics, ["--json"])

        assert result.exit_code == 0
        mock_run_diagnostics.assert_awaited_once()

    def test_display_diagnostics_results_healthy_status(self):
        """Test display of healthy diagnostics results."""
        diagnostics_data = {
            "overall_status": "healthy",
            "system_info": {
                "platform": "macOS-13.0-arm64-arm-64bit",
                "python_version": "3.13.3",
                "architecture": "64bit",
                "cpu_count": 8,
                "total_memory_gb": 16.0,
            },
            "performance_metrics": {
                "cpu_percent": 25.5,
                "memory_percent": 60.2,
                "disk_usage_percent": 45.8,
            },
            "recommendations": [],
        }

        test_console = Console(record=True, width=120)
        _display_diagnostics_results(diagnostics_data, console=test_console)

        output = test_console.export_text()
        assert "System Diagnostics: HEALTHY" in output

    def test_display_diagnostics_results_with_testing_infrastructure(self):
        """Test display of diagnostics with testing infrastructure info."""
        diagnostics_data = {
            "overall_status": "healthy",
            "system_info": {
                "platform": "test",
                "python_version": "3.13.3",
                "architecture": "64bit",
                "cpu_count": 8,
                "total_memory_gb": 16.0,
            },
            "performance_metrics": {
                "cpu_percent": 25.5,
                "memory_percent": 60.2,
                "disk_usage_percent": 45.8,
            },
            "testing_infrastructure": {
                "unit_tests": {"status": "passing", "exit_code": 0},
                "memory_leak_detection": {"status": "available"},
                "integration_tests": {"status": "available", "test_files_count": 12},
            },
            "recommendations": [],
        }

        test_console = Console(record=True, width=120)
        _display_diagnostics_results(diagnostics_data, console=test_console)

        output = test_console.export_text()
        assert "Testing Infrastructure" in output

    def test_display_diagnostics_results_with_recommendations(self):
        """Test display of diagnostics with recommendations."""
        diagnostics_data = {
            "overall_status": "attention_needed",
            "system_info": {
                "platform": "test",
                "python_version": "3.13.3",
                "architecture": "64bit",
                "cpu_count": 8,
                "total_memory_gb": 16.0,
            },
            "performance_metrics": {
                "cpu_percent": 95.0,
                "memory_percent": 85.0,
                "disk_usage_percent": 95.0,
            },
            "recommendations": [
                "High CPU usage detected - system may be under heavy load",
                "High memory usage detected - consider closing other applications",
                "Low disk space - consider cleaning up logs or temporary files",
            ],
        }

        with patch("cli.main.console.print") as mock_print:
            _display_diagnostics_results(diagnostics_data)

            # Verify console.print was called multiple times
            assert mock_print.call_count >= 4

            # Check that recommendations are displayed
            calls = [str(call) for call in mock_print.call_args_list]
            recommendation_calls = [call for call in calls if "Recommendations" in call]
            assert len(recommendation_calls) == 1
