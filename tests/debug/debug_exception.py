#!/usr/bin/env python3
"""
Debug script to understand the "Expecting something like a string" exception error.
"""

import json
from unittest.mock import patch
from cli.main import _validate_pyproject_file, _validate_critical_directories


def test_individual_functions_with_exception():
    """Test what happens when individual validation functions encounter exceptions."""
    print("=== Testing Individual Functions with Path Exception ===")

    try:
        # Test pyproject validation with Path exception
        print("Testing _validate_pyproject_file with Path exception:")
        with patch("pathlib.Path", side_effect=Exception("File system error")):
            result = _validate_pyproject_file()
            print(f"Result: {result}")
            print(f"JSON serializable: {json.dumps(result)}")
    except Exception as e:
        print(f"Exception in _validate_pyproject_file: {type(e).__name__}: {e}")

    try:
        # Test directory validation with Path exception
        print("\nTesting _validate_critical_directories with Path exception:")
        with patch("pathlib.Path", side_effect=Exception("File system error")):
            result = _validate_critical_directories(fix=False)
            print(f"Result: {result}")
            print(f"JSON serializable: {json.dumps(result)}")
    except Exception as e:
        print(f"Exception in _validate_critical_directories: {type(e).__name__}: {e}")


def test_full_validation_with_exception():
    """Test the full validation function with exception."""
    print("\n=== Testing Full Validation with Path Exception ===")

    from cli.main import _validate_configuration
    from unittest.mock import patch

    try:
        import asyncio

        async def run_test():
            with patch(
                "pathlib.Path", side_effect=Exception("File system error")
            ), patch("cli.main.console.print") as mock_print:
                await _validate_configuration(json_output=True, fix=False)

                if mock_print.called:
                    printed_data = mock_print.call_args[0][0]
                    print(f"Printed data type: {type(printed_data)}")
                    print(f"Printed data: {printed_data}")

                    try:
                        parsed = json.loads(printed_data)
                        print(
                            f"Successfully parsed JSON: {parsed.get('overall_status')}"
                        )
                        print(f"Error field: {parsed.get('error')}")
                    except json.JSONDecodeError as json_err:
                        print(f"JSON decode error: {json_err}")
                        print(f"Raw data: {repr(printed_data)}")

        asyncio.run(run_test())

    except Exception as e:
        print(f"Exception in full validation test: {type(e).__name__}: {e}")


if __name__ == "__main__":
    test_individual_functions_with_exception()
    test_full_validation_with_exception()
