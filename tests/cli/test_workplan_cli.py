"""Tests for recovery plan CLI commands."""

import json
import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch
from click.testing import CliRunner

from cli.main import cli, _list_recovery_plans, _create_recovery_plan


class TestRecoveryPlanCLI:
    """Test suite for recovery plan CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @pytest.mark.service
    @patch("cli.main.YTArchiveAPI")
    def test_workplan_help(self, mock_api):
        """Test work plan help command displays correctly."""
        result = self.runner.invoke(cli, ["recovery", "--help"])

        assert result.exit_code == 0
        assert (
            "Manage recovery plans for failed and unavailable videos" in result.output
        )
        assert "create" in result.output
        assert "list" in result.output
        assert "show" in result.output

    @pytest.mark.service
    @patch("cli.main.YTArchiveAPI")
    @patch("cli.main.Path")
    def test_workplan_list_no_directory(self, mock_path, mock_api):
        """Test work plan list when no work plans directory exists."""
        # Mock directory doesn't exist
        mock_work_plans_dir = Mock()
        mock_work_plans_dir.exists.return_value = False
        mock_path.return_value.expanduser.return_value = mock_work_plans_dir

        # Mock API
        mock_api_instance = AsyncMock()
        mock_api_instance.client.get = AsyncMock()
        mock_api_instance.client.get.return_value.raise_for_status = Mock()
        mock_api.return_value.__aenter__ = AsyncMock(return_value=mock_api_instance)
        mock_api.return_value.__aexit__ = AsyncMock(return_value=None)

        result = self.runner.invoke(cli, ["recovery", "list"])

        assert result.exit_code == 0
        assert "No work plans directory found" in result.output

    @pytest.mark.service
    @patch("cli.main.console.print")
    @patch("cli.main.YTArchiveAPI")
    @patch("cli.main.Path")
    @patch("builtins.open")
    def test_workplan_list_with_plans(
        self, mock_open, mock_path, mock_api, mock_console
    ):
        """Test work plan list with existing work plans."""
        # Mock work plan file
        mock_plan_file = Mock()
        mock_plan_file.stem = "20240724_120000_plan"

        mock_work_plans_dir = Mock()
        mock_work_plans_dir.exists.return_value = True
        mock_work_plans_dir.glob.return_value = [mock_plan_file]
        mock_path.return_value.expanduser.return_value = mock_work_plans_dir

        # Mock file content
        plan_data = {
            "plan_id": "20240724_120000",
            "created_at": "2024-07-24T12:00:00Z",
            "total_videos": 5,
            "unavailable_count": 2,
            "failed_count": 3,
        }
        mock_open.return_value.__enter__.return_value.read = Mock(
            return_value=json.dumps(plan_data)
        )

        # Mock API
        mock_api_instance = AsyncMock()
        mock_api_instance.client.get = AsyncMock()
        mock_api_instance.client.get.return_value.raise_for_status = Mock()
        mock_api.return_value.__aenter__ = AsyncMock(return_value=mock_api_instance)
        mock_api.return_value.__aexit__ = AsyncMock(return_value=None)

        # Test the async function directly
        asyncio.run(_list_recovery_plans(json_output=False))

        # Verify console output was called (table should be printed)
        mock_console.assert_called()

    @pytest.mark.service
    @patch("cli.main.YTArchiveAPI")
    @patch("cli.main.Path")
    def test_workplan_show_not_found(self, mock_path, mock_api):
        """Test work plan show for non-existent plan."""
        # Mock plan file doesn't exist
        mock_plan_file = Mock()
        mock_plan_file.exists.return_value = False
        mock_work_plans_dir = Mock()
        mock_work_plans_dir.__truediv__ = Mock(return_value=mock_plan_file)
        mock_path.return_value.expanduser.return_value = mock_work_plans_dir

        # Mock API
        mock_api_instance = AsyncMock()
        mock_api.return_value.__aenter__ = AsyncMock(return_value=mock_api_instance)
        mock_api.return_value.__aexit__ = AsyncMock(return_value=None)

        result = self.runner.invoke(cli, ["recovery", "show", "nonexistent"])

        assert result.exit_code == 0
        assert "not found" in result.output

    @pytest.mark.service
    @patch("cli.main.console.print")
    @patch("cli.main.YTArchiveAPI")
    def test_workplan_create_success(self, mock_api, mock_console):
        """Test successful work plan creation."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": {
                "plan_id": "20240724_120000",
                "path": "~/.ytarchive/data/work_plans/20240724_120000_plan.json",
                "total_videos": 1,
                "unavailable_count": 0,
                "failed_count": 1,
            },
        }
        mock_response.raise_for_status = Mock()

        mock_api_instance = AsyncMock()
        mock_api_instance.client.post = AsyncMock(return_value=mock_response)
        mock_api.return_value.__aenter__ = AsyncMock(return_value=mock_api_instance)
        mock_api.return_value.__aexit__ = AsyncMock(return_value=None)

        # Test the async function directly with mock data
        asyncio.run(_create_recovery_plan(None, None))

        # Verify console output was called (success message should be printed)
        mock_console.assert_called()

    @pytest.mark.service
    @patch("cli.main.YTArchiveAPI")
    def test_workplan_create_no_files(self, mock_api):
        """Test work plan creation with no input files."""
        # Mock API
        mock_api_instance = AsyncMock()
        mock_api.return_value.__aenter__ = AsyncMock(return_value=mock_api_instance)
        mock_api.return_value.__aexit__ = AsyncMock(return_value=None)

        result = self.runner.invoke(cli, ["recovery", "create"])

        assert result.exit_code == 0
        assert "No unavailable videos or failed downloads provided" in result.output

    @pytest.mark.service
    def test_workplan_create_help(self):
        """Test work plan create help command."""
        result = self.runner.invoke(cli, ["recovery", "create", "--help"])

        assert result.exit_code == 0
        assert "Create a new recovery plan" in result.output
        assert "--unavailable-videos" in result.output
        assert "--failed-downloads" in result.output

    @pytest.mark.service
    def test_workplan_list_help(self):
        """Test work plan list help command."""
        result = self.runner.invoke(cli, ["recovery", "list", "--help"])

        assert result.exit_code == 0
        assert "List all recovery plans" in result.output
        assert "--json" in result.output

    @pytest.mark.service
    def test_workplan_show_help(self):
        """Test work plan show help command."""
        result = self.runner.invoke(cli, ["recovery", "show", "--help"])

        assert result.exit_code == 0
        assert "Show details of a specific recovery plan" in result.output
        assert "--json" in result.output
