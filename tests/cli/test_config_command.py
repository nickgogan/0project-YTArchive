import json
import pytest
from unittest.mock import patch
import toml

from cli.main import _validate_configuration
from tests.common.config_test_utils import (
    create_complete_valid_environment,
    create_missing_files_environment,
    create_valid_pyproject_data,
    create_config_environment,
    create_valid_pytest_ini_content,
)


@pytest.mark.unit
@pytest.mark.cli
class TestConfigCommand:
    """Test suite for config command functionality using WatchOut established patterns."""

    async def run_validation_with_mocks(self, mock_environment, **kwargs):
        """Helper to run validation with standardized mock environment."""
        with mock_environment, patch("cli.main.console.print") as mock_print:
            await _validate_configuration(json_output=True, **kwargs)
            mock_print.assert_called_once()
            return json.loads(mock_print.call_args[0][0])

    @pytest.mark.asyncio
    async def test_validate_configuration_all_valid(self):
        """Test configuration validation with all settings being valid.

        Following WatchOut pattern: complete valid environment using standardized helper.
        """
        mock_env = create_complete_valid_environment()
        validation_data = await self.run_validation_with_mocks(mock_env, fix=False)

        assert validation_data["overall_status"] == "valid"
        assert not validation_data["issues"]
        assert not validation_data["warnings"]
        assert (
            validation_data["configuration_files"]["pyproject.toml"]["exists"] is True
        )
        assert validation_data["configuration_files"]["pytest.ini"]["exists"] is True
        assert (
            validation_data["environment_variables"]["YOUTUBE_API_KEY"]["set"] is True
        )

    @pytest.mark.asyncio
    async def test_validate_configuration_missing_pyproject(self):
        """Test configuration validation with missing pyproject.toml.

        Following WatchOut pattern: focused test scenario with missing files helper.
        """
        mock_env = create_missing_files_environment(["pyproject.toml"])
        validation_data = await self.run_validation_with_mocks(mock_env, fix=False)

        assert validation_data["overall_status"] == "issues_found"
        assert "Missing pyproject.toml file" in validation_data["issues"]
        assert (
            validation_data["configuration_files"]["pyproject.toml"]["exists"] is False
        )

    @pytest.mark.asyncio
    async def test_validate_configuration_missing_dependencies(self):
        """Test configuration validation with missing required dependencies.

        Following WatchOut pattern: realistic mock data with incomplete dependencies.
        """
        incomplete_pyproject_data = {"project": {"dependencies": ["click"]}}

        mock_env = create_config_environment(
            files_exist={"pyproject.toml": True},
            file_contents={"pyproject.toml": toml.dumps(incomplete_pyproject_data)},
            toml_data=incomplete_pyproject_data,
            env_vars={"YOUTUBE_API_KEY": "test_key"},
        )

        validation_data = await self.run_validation_with_mocks(mock_env, fix=False)

        assert validation_data["overall_status"] == "issues_found"
        assert (
            "Missing required dependencies: httpx, pydantic, yt-dlp, rich, psutil"
            in validation_data["issues"][0]
        )

    @pytest.mark.asyncio
    async def test_validate_configuration_missing_pytest_markers(self):
        """Test configuration validation with missing pytest markers.

        Following WatchOut pattern: warning scenario with incomplete config.
        """
        incomplete_pytest_content = "[pytest]\n# No markers section"
        valid_pyproject = create_valid_pyproject_data()

        mock_env = create_config_environment(
            files_exist={"pyproject.toml": True, "pytest.ini": True},
            file_contents={
                "pytest.ini": incomplete_pytest_content,
                "pyproject.toml": toml.dumps(valid_pyproject),
            },
            toml_data=valid_pyproject,
            env_vars={"YOUTUBE_API_KEY": "test_key"},
        )

        validation_data = await self.run_validation_with_mocks(mock_env, fix=False)

        assert validation_data["overall_status"] == "warnings_only"
        assert (
            "Missing test markers: unit, integration, e2e, memory"
            in validation_data["warnings"][0]
        )

    @pytest.mark.asyncio
    async def test_validate_configuration_missing_critical_directories(self):
        """Test configuration validation with missing critical directories.

        Following WatchOut pattern: focused missing files scenario.
        """
        mock_env = create_missing_files_environment(["logs", "logs/temp"])
        validation_data = await self.run_validation_with_mocks(mock_env, fix=False)

        assert validation_data["overall_status"] == "issues_found"
        assert "Missing critical directory: logs" in validation_data["issues"]
        assert "Missing critical directory: logs/temp" in validation_data["issues"]
        assert validation_data["directory_structure"]["logs"]["exists"] is False
        assert validation_data["directory_structure"]["logs/temp"]["exists"] is False

    @pytest.mark.asyncio
    async def test_validate_configuration_with_fix_flag(self):
        """Test configuration validation with auto-fix enabled.

        Following WatchOut pattern: testing fix behavior with mocked directory creation.
        """
        # Start with missing directories
        files_exist = {
            "pyproject.toml": True,
            "pytest.ini": True,
            "logs": False,
            "logs/temp": False,
        }
        valid_pyproject = create_valid_pyproject_data()

        mock_env = create_config_environment(
            files_exist=files_exist,
            file_contents={"pyproject.toml": toml.dumps(valid_pyproject)},
            toml_data=valid_pyproject,
            env_vars={"YOUTUBE_API_KEY": "test_key"},
        )

        validation_data = await self.run_validation_with_mocks(mock_env, fix=True)

        # With fix=True, directories should be "created" and fixes_applied should be populated
        assert "Created directory: logs" in validation_data["fixes_applied"]
        assert "Created directory: logs/temp" in validation_data["fixes_applied"]
        # Directory status should be updated after fix
        assert validation_data["directory_structure"]["logs"]["exists"] is True
        assert validation_data["directory_structure"]["logs/temp"]["exists"] is True

    @pytest.mark.asyncio
    async def test_validate_configuration_missing_env_var(self):
        """Test configuration validation with missing environment variables.

        Following WatchOut pattern: single consistent mock environment approach.
        """
        # WatchOut pattern: Use create_config_environment with empty env_vars to simulate missing environment variable
        valid_pyproject = create_valid_pyproject_data()

        mock_env = create_config_environment(
            files_exist={
                "pyproject.toml": True,
                "pytest.ini": True,
                # Include service config files to avoid additional warnings
                "services/jobs/config.py": True,
                "services/storage/config.py": True,
                "services/metadata/config.py": True,
                "services/download/config.py": True,
                "services/logging/config.py": True,
            },
            file_contents={
                "pyproject.toml": toml.dumps(valid_pyproject),
                "pytest.ini": create_valid_pytest_ini_content(),
            },
            toml_data=valid_pyproject,
            env_vars={},  # Empty env_vars to simulate missing YOUTUBE_API_KEY
        )

        validation_data = await self.run_validation_with_mocks(mock_env, fix=False)

        assert validation_data["overall_status"] == "warnings_only"
        assert (
            "Environment variable YOUTUBE_API_KEY not set"
            in validation_data["warnings"]
        )
        assert (
            validation_data["environment_variables"]["YOUTUBE_API_KEY"]["set"] is False
        )

    @pytest.mark.asyncio
    async def test_validate_configuration_service_configs(self):
        """Test configuration validation of service configuration files.

        Following WatchOut pattern: selective file existence testing.
        """
        # Most services have config files, but metadata is missing
        service_files = {
            f"services/{service}/config.py": True
            for service in ["jobs", "storage", "download", "logging"]
        }
        service_files["services/metadata/config.py"] = False

        files_exist = {"pyproject.toml": True, "pytest.ini": True}
        files_exist.update(service_files)

        valid_pyproject = create_valid_pyproject_data()

        mock_env = create_config_environment(
            files_exist=files_exist,
            file_contents={"pyproject.toml": toml.dumps(valid_pyproject)},
            toml_data=valid_pyproject,
            env_vars={"YOUTUBE_API_KEY": "test_key"},
        )

        validation_data = await self.run_validation_with_mocks(mock_env, fix=False)

        assert validation_data["overall_status"] == "warnings_only"
        assert validation_data["services_config"]["jobs"]["config_exists"] is True
        assert validation_data["services_config"]["metadata"]["config_exists"] is False
        assert (
            "Missing service config: services/metadata/config.py"
            in validation_data["warnings"]
        )

    @pytest.mark.asyncio
    async def test_validate_configuration_exception_handling(self):
        """Test configuration validation exception handling.

        Following WatchOut pattern: exception scenario testing.
        """
        # Force an exception by making Path construction fail
        with patch("pathlib.Path", side_effect=Exception("File system error")), patch(
            "cli.main.console.print"
        ) as mock_print:
            await _validate_configuration(json_output=True, fix=False)
            mock_print.assert_called_once()
            validation_data = json.loads(mock_print.call_args[0][0])

            assert validation_data["overall_status"] == "error"
            assert "File system error" in validation_data["error"]
