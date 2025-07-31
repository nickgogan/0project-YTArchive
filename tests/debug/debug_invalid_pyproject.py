#!/usr/bin/env python3
"""
Debug script to understand why the invalid pyproject test is failing.
"""

import json
import asyncio
import toml
from unittest.mock import patch
from tests.common.config_test_utils import (
    create_config_environment,
    create_invalid_content_environment,
)
from cli.main import _validate_configuration


async def debug_invalid_pyproject_test():
    """Debug the invalid pyproject test to see what's happening."""
    print("=== Debugging Invalid PyProject Test ===")

    # Replicate the exact test setup
    invalid_content = {"pyproject.toml": "invalid [toml content}"}

    # Mock toml.load to raise TomlDecodeError for invalid content
    def mock_toml_load_error(f):
        print(f"Mock toml.load called with file: {f}")
        raise toml.TomlDecodeError("Invalid TOML", "", 0)

    print("Setting up test environment...")

    mock_env = create_invalid_content_environment(invalid_content)
    with mock_env, patch(
        "cli.main.toml.load", side_effect=mock_toml_load_error
    ) as mock_toml, patch("cli.main.console.print") as mock_print:
        print("Running validation...")
        # Use create_config_environment() as in the test
        validation_data_env = create_config_environment()
        with validation_data_env:
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

                # Check specifically for the expected message
                has_invalid_toml = any(
                    "Invalid pyproject.toml" in issue
                    for issue in validation_data["issues"]
                )
                print(f"  Contains 'Invalid pyproject.toml': {has_invalid_toml}")
            else:
                print("  No issues found!")

            if validation_data["warnings"]:
                print("  Warnings:")
                for i, warning in enumerate(validation_data["warnings"]):
                    print(f"    {i+1}. {warning}")
        else:
            print("Mock print was not called!")

    print(f"Mock toml.load call count: {mock_toml.call_count}")


if __name__ == "__main__":
    asyncio.run(debug_invalid_pyproject_test())
