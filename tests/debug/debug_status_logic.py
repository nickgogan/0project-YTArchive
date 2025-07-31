#!/usr/bin/env python3
"""
Debug script to understand why "warnings_only" tests are getting "issues_found" status.
"""

import sys
import asyncio
import json
import toml
from unittest.mock import patch

from cli.main import _validate_configuration
from tests.common.config_test_utils import (
    create_config_environment,
    create_valid_pyproject_data,
)

sys.path.insert(0, "/Users/nick.gogan/Desktop/Projects/YTArchive")


async def debug_service_configs_test():
    """Debug the service configs test to see what issues are being generated."""
    print("=== Debugging Service Configs Test ===")

    # Replicate the exact test setup from test_validate_configuration_service_configs
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

    print("Mock environment setup:")
    print(f"  Files exist: {files_exist}")
    print("  Environment vars: {'YOUTUBE_API_KEY': 'test_key'}")

    # Run validation with mocks
    with mock_env, patch("cli.main.console.print") as mock_print:
        await _validate_configuration(json_output=True, fix=False)

        if mock_print.called:
            printed_data = mock_print.call_args[0][0]
            validation_data = json.loads(printed_data)

            print("\nValidation Results:")
            print(f"  Overall status: {validation_data['overall_status']}")
            print(f"  Issues count: {len(validation_data['issues'])}")
            print(f"  Warnings count: {len(validation_data['warnings'])}")

            if validation_data["issues"]:
                print("  Issues:")
                for i, issue in enumerate(validation_data["issues"]):
                    print(f"    {i+1}. {issue}")

            if validation_data["warnings"]:
                print("  Warnings:")
                for i, warning in enumerate(validation_data["warnings"]):
                    print(f"    {i+1}. {warning}")

            # Check service configs specifically
            print("\nService Config Details:")
            for service, config in validation_data.get("services_config", {}).items():
                print(f"  {service}: config_exists={config.get('config_exists')}")


async def debug_env_var_test():
    """Debug the environment variable test."""
    print("\n=== Debugging Environment Variable Test ===")

    files_exist = {"pyproject.toml": True, "pytest.ini": True}
    # Add all service config files so they don't cause issues
    service_files = {
        f"services/{service}/config.py": True
        for service in ["jobs", "metadata", "storage", "download", "logging"]
    }
    files_exist.update(service_files)

    valid_pyproject = create_valid_pyproject_data()

    mock_env = create_config_environment(
        files_exist=files_exist,
        file_contents={"pyproject.toml": toml.dumps(valid_pyproject)},
        toml_data=valid_pyproject,
        env_vars={},  # No environment variables set
    )

    print("Mock environment setup:")
    print(f"  Files exist: {files_exist}")
    print("  Environment vars: (none)")

    # Run validation with mocks
    with mock_env, patch("cli.main.console.print") as mock_print:
        await _validate_configuration(json_output=True, fix=False)

        if mock_print.called:
            printed_data = mock_print.call_args[0][0]
            validation_data = json.loads(printed_data)

            print("\nValidation Results:")
            print(f"  Overall status: {validation_data['overall_status']}")
            print(f"  Issues count: {len(validation_data['issues'])}")
            print(f"  Warnings count: {len(validation_data['warnings'])}")

            if validation_data["issues"]:
                print("  Issues:")
                for i, issue in enumerate(validation_data["issues"]):
                    print(f"    {i+1}. {issue}")

            if validation_data["warnings"]:
                print("  Warnings:")
                for i, warning in enumerate(validation_data["warnings"]):
                    print(f"    {i+1}. {warning}")


async def main():
    await debug_service_configs_test()
    await debug_env_var_test()


if __name__ == "__main__":
    asyncio.run(main())
