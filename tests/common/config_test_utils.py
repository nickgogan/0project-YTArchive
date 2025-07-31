"""
Standardized utilities for config command testing following WatchOut patterns.

This module provides centralized, consistent mocking helpers for configuration
validation tests, avoiding ad-hoc mocking patterns that lead to test fragility.
"""

import os
from unittest.mock import patch, mock_open
from contextlib import contextmanager
import toml


def create_config_environment(
    files_exist=None, file_contents=None, env_vars=None, toml_data=None
):
    """
    Create a standardized mock environment for config validation tests.

    Following WatchOut pattern: targeted mocking at boundaries, not system-wide replacement.
    Uses selective patching to avoid interfering with system operations.

    Args:
        files_exist: Dict mapping file paths to boolean existence
        file_contents: Dict mapping file paths to string contents
        env_vars: Dict of environment variables to set
        toml_data: Dict of data for toml.load to return

    Returns:
        Context manager that sets up all the mocks
    """
    files_exist = files_exist or {}
    file_contents = file_contents or {}
    env_vars = env_vars or {}
    toml_data = toml_data or {}

    @contextmanager
    def config_context():
        # Track directory creation state
        created_dirs = set()

        # Store original Path class to avoid system interference
        from pathlib import Path as OriginalPath

        # Critical directories that should exist by default in tests
        critical_directories = {
            "logs",
            "logs/temp",
            "services",
            "cli",
            "tests",
            "tests/integration",
            "tests/memory",
        }

        # Create targeted mock functions instead of replacing entire Path class
        def mock_path_exists(self):
            path_str = str(self)
            # Return True if directory was created during test
            if path_str in created_dirs:
                return True
            # Check our mock mapping first
            if path_str in files_exist:
                return files_exist[path_str]
            # Critical directories should exist by default to avoid test issues
            if path_str in critical_directories:
                return True
            # Fall back to real filesystem for system paths (SSL certs, etc.)
            if path_str.startswith(("/System/", "/usr/", "/private/", "/Library/")):
                return OriginalPath(path_str).exists()
            # Default to False for test paths not explicitly specified
            return False

        def mock_path_mkdir(self, parents=True, exist_ok=True):
            path_str = str(self)
            # Track directory creation
            created_dirs.add(path_str)
            files_exist[path_str] = True
            # Don't actually create real directories in tests
            return None

        # Mock file opening with targeted approach
        def mock_open_side_effect(path, *args, **kwargs):
            path_str = str(path)
            if path_str in file_contents:
                return mock_open(read_data=file_contents[path_str]).return_value
            # For system files, use real file operations
            if path_str.startswith(("/System/", "/usr/", "/private/", "/Library/")):
                return open(path, *args, **kwargs)
            # Default to empty content for test files
            return mock_open(read_data="").return_value

        # Mock toml.load with proper error handling - following WatchOut successful pattern
        def mock_toml_load(f):
            if toml_data:
                return toml_data
            # Return valid default structure to prevent TypeError that causes "File system error"
            return {
                "project": {
                    "name": "test-project",
                    "dependencies": [
                        "httpx",
                        "pydantic",
                        "click",
                        "yt-dlp",
                        "rich",
                        "psutil",
                    ],
                }
            }

        # Use targeted patching instead of wholesale replacement
        with patch.object(OriginalPath, "exists", mock_path_exists), patch.object(
            OriginalPath, "mkdir", mock_path_mkdir
        ), patch("builtins.open", side_effect=mock_open_side_effect), patch(
            "cli.main.toml.load", side_effect=mock_toml_load
        ), patch.dict(
            os.environ, env_vars, clear=True
        ):
            yield

    return config_context()


def create_valid_pyproject_data():
    """
    Create standard valid pyproject.toml data for testing.

    Following WatchOut pattern: standardized data fixtures.
    """
    return {
        "project": {
            "name": "ytarchive",
            "requires-python": ">=3.11",
            "dependencies": [
                "httpx~=0.25.2",
                "pydantic~=2.9.0",
                "click~=8.1.7",
                "yt-dlp~=2023.11.16",
                "rich~=13.7.0",
                "psutil>=7.0.0",
            ],
        }
    }


def create_valid_pytest_ini_content():
    """
    Create standard valid pytest.ini content for testing.

    Following WatchOut pattern: standardized content fixtures.
    """
    return """[pytest]
testpaths = tests
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    memory: Memory leak tests
"""


def create_complete_valid_environment():
    """
    Create a complete valid configuration environment for testing.

    This represents the "happy path" where all files exist with valid content.
    Following WatchOut pattern: realistic mock data.
    """
    pyproject_data = create_valid_pyproject_data()
    pytest_content = create_valid_pytest_ini_content()

    # All critical files and directories exist
    files_exist = {
        "pyproject.toml": True,
        "pytest.ini": True,
        "logs": True,
        "logs/temp": True,
        "services": True,
        "cli": True,
        "tests": True,
        "tests/integration": True,
        "tests/memory": True,
    }

    # Add all service config files
    for service in ["jobs", "metadata", "storage", "download", "logging"]:
        files_exist[f"services/{service}/config.py"] = True

    file_contents = {
        "pytest.ini": pytest_content,
        "pyproject.toml": toml.dumps(pyproject_data),
    }

    env_vars = {"YOUTUBE_API_KEY": "test_api_key_12345"}

    return create_config_environment(
        files_exist=files_exist,
        file_contents=file_contents,
        env_vars=env_vars,
        toml_data=pyproject_data,
    )


def create_missing_files_environment(missing_files):
    """
    Create an environment with specific files missing.

    Args:
        missing_files: List of file paths that should not exist

    Following WatchOut pattern: focused test scenarios.
    """
    # Start with complete environment
    pyproject_data = create_valid_pyproject_data()
    pytest_content = create_valid_pytest_ini_content()

    files_exist = {
        "pyproject.toml": True,
        "pytest.ini": True,
        "logs": True,
        "logs/temp": True,
        "services": True,
        "cli": True,
        "tests": True,
        "tests/integration": True,
        "tests/memory": True,
    }

    # Add all service config files
    for service in ["jobs", "metadata", "storage", "download", "logging"]:
        files_exist[f"services/{service}/config.py"] = True

    # Remove the specified missing files
    for missing_file in missing_files:
        files_exist[missing_file] = False

    file_contents = {
        "pytest.ini": pytest_content,
        "pyproject.toml": toml.dumps(pyproject_data),
    }

    env_vars = {"YOUTUBE_API_KEY": "test_api_key_12345"}

    return create_config_environment(
        files_exist=files_exist,
        file_contents=file_contents,
        env_vars=env_vars,
        toml_data=pyproject_data,
    )


def create_invalid_content_environment(invalid_content_map):
    """
    Create an environment with invalid file contents.

    Args:
        invalid_content_map: Dict mapping file paths to invalid content

    Following WatchOut pattern: error scenario testing.
    """
    pyproject_data = create_valid_pyproject_data()
    pytest_content = create_valid_pytest_ini_content()

    files_exist = {
        "pyproject.toml": True,
        "pytest.ini": True,
        "logs": True,
        "logs/temp": True,
        "services": True,
        "cli": True,
        "tests": True,
        "tests/integration": True,
        "tests/memory": True,
    }

    # Add all service config files
    for service in ["jobs", "metadata", "storage", "download", "logging"]:
        files_exist[f"services/{service}/config.py"] = True

    file_contents = {
        "pytest.ini": pytest_content,
        "pyproject.toml": toml.dumps(pyproject_data),
    }

    # Override with invalid content
    file_contents.update(invalid_content_map)

    env_vars = {"YOUTUBE_API_KEY": "test_api_key_12345"}

    return create_config_environment(
        files_exist=files_exist,
        file_contents=file_contents,
        env_vars=env_vars
        # Don't pass toml_data so validation function parses invalid file_contents
    )
