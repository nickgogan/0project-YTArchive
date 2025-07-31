#!/usr/bin/env python3
"""
Debug script to test our mock utilities in isolation.
This will help identify where the mocking breakdown is happening.
"""

import os
from pathlib import Path
from tests.common.config_test_utils import create_config_environment


def test_basic_path_mocking():
    """Test if our Path mocking works at all."""
    print("=== Testing Basic Path Mocking ===")

    files_exist = {"test_file.txt": True, "missing_file.txt": False}

    with create_config_environment(files_exist=files_exist):
        # Test that mocked paths work
        existing_path = Path("test_file.txt")
        missing_path = Path("missing_file.txt")

        print(f"Existing file exists: {existing_path.exists()}")  # Should be True
        print(f"Missing file exists: {missing_path.exists()}")  # Should be False

        # Test directory creation
        new_dir = Path("new_directory")
        print(f"New dir exists before mkdir: {new_dir.exists()}")  # Should be False
        new_dir.mkdir(parents=True, exist_ok=True)
        print(f"New dir exists after mkdir: {new_dir.exists()}")  # Should be True


def test_env_var_mocking():
    """Test if our environment variable mocking works."""
    print("\n=== Testing Environment Variable Mocking ===")

    env_vars = {"TEST_KEY": "test_value", "YOUTUBE_API_KEY": "mock_api_key"}

    with create_config_environment(env_vars=env_vars):
        print(f"TEST_KEY: {os.getenv('TEST_KEY')}")  # Should be test_value
        print(
            f"YOUTUBE_API_KEY: {os.getenv('YOUTUBE_API_KEY')}"
        )  # Should be mock_api_key
        print(f"MISSING_KEY: {os.getenv('MISSING_KEY')}")  # Should be None


def test_individual_validation_functions():
    """Test the individual validation functions with mocks."""
    print("\n=== Testing Individual Validation Functions ===")

    # Import the individual functions
    from cli.main import _validate_pyproject_file, _validate_critical_directories

    # Test pyproject validation with missing file
    print("Testing _validate_pyproject_file with missing file:")
    files_exist = {"pyproject.toml": False}
    with create_config_environment(files_exist=files_exist):
        result = _validate_pyproject_file()
        print(f"Result: {result}")
        print(f"Issues: {result['issues']}")
        print(f"File exists in result: {result['file_data']['exists']}")

    # Test directory validation
    print("\nTesting _validate_critical_directories:")
    files_exist = {"logs": False, "logs/temp": False}
    with create_config_environment(files_exist=files_exist):
        result = _validate_critical_directories(fix=False)
        print(f"Result issues: {result['issues']}")
        print(f"Directory data: {result['directory_data']}")


if __name__ == "__main__":
    test_basic_path_mocking()
    test_env_var_mocking()
    test_individual_validation_functions()
