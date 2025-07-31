#!/usr/bin/env python3
"""
Debug script to trace the exact error message transformation in exception handling test.

From terminal output:
- Expected: "File system error"
- Actual: "Expecting something like a string"

Need to find where the transformation happens.
"""

import sys
import asyncio
import json
from pathlib import Path
from unittest.mock import patch
from cli.main import _validate_configuration

sys.path.insert(0, "/Users/nick.gogan/Desktop/Projects/YTArchive")


async def debug_exception_handling():
    """Debug the exception handling path step by step."""

    print("🔍 DEBUGGING EXCEPTION HANDLING PATH")
    print("=" * 50)

    # Test 1: Direct Path construction with our exception
    print("\n📍 TEST 1: Direct Path construction")
    try:
        with patch("pathlib.Path", side_effect=Exception("File system error")):
            _ = Path("test")
    except Exception as e:
        print(f"✅ Exception type: {type(e)}")
        print(f"✅ Exception message: '{e}'")

    # Test 2: Full validation with Path exception
    print("\n📍 TEST 2: Full validation with Path exception")
    try:
        with patch("pathlib.Path", side_effect=Exception("File system error")), patch(
            "cli.main.console.print"
        ) as mock_print:
            await _validate_configuration(json_output=True, fix=False)

            if mock_print.called:
                output = mock_print.call_args[0][0]
                validation_data = json.loads(output)
                print(f"✅ Status: {validation_data['overall_status']}")
                print(
                    f"✅ Error message: '{validation_data.get('error', 'NO ERROR KEY')}'"
                )
                print(f"✅ Full output keys: {list(validation_data.keys())}")
            else:
                print("❌ Console.print was not called")

    except Exception as e:
        print(f"❌ Outer exception caught: {type(e)} - '{e}'")

    # Test 3: Check what happens in individual validation functions
    print("\n📍 TEST 3: Individual validation function behavior")
    try:
        # Import the individual validation function
        from cli.main import _validate_pyproject_file

        with patch("pathlib.Path", side_effect=Exception("File system error")):
            result = _validate_pyproject_file()
            print(f"✅ Validation result: {result}")

    except Exception as e:
        print(f"✅ Exception from _validate_pyproject_file: {type(e)} - '{e}'")


if __name__ == "__main__":
    asyncio.run(debug_exception_handling())
