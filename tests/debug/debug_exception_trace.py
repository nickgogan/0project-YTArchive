#!/usr/bin/env python3
"""
Detailed exception flow tracing to understand error message transformation.
"""

import json
from unittest.mock import patch
from cli.main import _validate_configuration


def trace_pyproject_exception():
    """Trace exactly where the exception transformation happens in _validate_pyproject_file."""
    print("=== Tracing _validate_pyproject_file Exception Flow ===")

    # Test 1: Path construction only
    print("\n1. Testing Path construction:")
    try:
        with patch("pathlib.Path", side_effect=Exception("File system error")):
            from pathlib import Path

            path = Path("pyproject.toml")
            print(f"Path created: {path}")
    except Exception as e:
        print(f"Path construction failed: {type(e).__name__}: {e}")

    # Test 2: Path construction in validation context
    print("\n2. Testing Path construction in validation function:")
    try:
        with patch("pathlib.Path", side_effect=Exception("File system error")):
            # Note: _validate_pyproject_file was removed, using _validate_configuration instead
            import asyncio

            result = asyncio.run(_validate_configuration(json_output=False, fix=False))
            print(f"Validation result: {result}")
    except Exception as e:
        print(f"Validation function exception: {type(e).__name__}: {e}")

    # Test 3: Test if Path exists operation
    print("\n3. Testing Path.exists operation:")
    try:
        with patch("pathlib.Path") as mock_path:
            mock_path.side_effect = Exception("File system error")
            import asyncio

            result = asyncio.run(_validate_configuration(json_output=False, fix=False))
            print(f"Result with Path mock: {result}")
    except Exception as e:
        print(f"Path.exists exception: {type(e).__name__}: {e}")

    # Test 4: Test file opening operation
    print("\n4. Testing file opening with mocked Path:")
    try:
        with patch("pathlib.Path") as mock_path:
            # Mock Path to return a mock object that raises exception on exists()
            mock_path_instance = mock_path.return_value
            mock_path_instance.exists.return_value = True
            mock_path_instance.__str__ = lambda: "pyproject.toml"

            # Mock open to raise our original exception
            with patch("builtins.open", side_effect=Exception("File system error")):
                import asyncio

                result = asyncio.run(
                    _validate_configuration(json_output=False, fix=False)
                )
                print(f"Result with open mock: {result}")
    except Exception as e:
        print(f"File open exception: {type(e).__name__}: {e}")

    # Test 5: Test TOML loading operation
    print("\n5. Testing TOML loading with exception:")
    try:
        with patch("pathlib.Path") as mock_path:
            mock_path_instance = mock_path.return_value
            mock_path_instance.exists.return_value = True

            with patch("builtins.open") as mock_open:
                _ = mock_open.return_value.__enter__.return_value

                # Mock toml.load to raise the original exception
                with patch("toml.load", side_effect=Exception("File system error")):
                    import asyncio

                    result = asyncio.run(
                        _validate_configuration(json_output=False, fix=False)
                    )
                    print(f"Result with toml.load mock: {result}")
    except Exception as e:
        print(f"TOML load exception: {type(e).__name__}: {e}")


def trace_full_validation_exception():
    """Trace the full validation chain to see where message transformation occurs."""
    print("\n=== Tracing Full Validation Exception Chain ===")

    import asyncio

    async def run_trace():
        try:
            with patch(
                "pathlib.Path", side_effect=Exception("File system error")
            ), patch("cli.main.console.print") as mock_print:
                await _validate_configuration(json_output=True, fix=False)

                if mock_print.called:
                    printed_data = mock_print.call_args[0][0]
                    parsed = json.loads(printed_data)
                    print(f"Final error message: {parsed.get('error')}")
                    print(f"Full validation data: {json.dumps(parsed, indent=2)}")
        except Exception as e:
            print(f"Full validation chain exception: {type(e).__name__}: {e}")

    asyncio.run(run_trace())


if __name__ == "__main__":
    trace_pyproject_exception()
    trace_full_validation_exception()
