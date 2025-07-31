#!/usr/bin/env python3
"""
Line-by-line debug of _validate_pyproject_file to find exact transformation point.
"""

import sys
import toml
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "/Users/nick.gogan/Desktop/Projects/YTArchive")


def debug_step_by_step():
    """Debug each step of _validate_pyproject_file logic."""

    print("🔍 LINE-BY-LINE DEBUG OF _validate_pyproject_file")
    print("=" * 60)

    # Test each step that could cause the transformation

    print("\n📍 STEP 1: Path construction")
    try:
        with patch("pathlib.Path", side_effect=Exception("File system error")):
            pyproject_path = Path("pyproject.toml")
            print(f"✅ Path created: {pyproject_path}")
    except Exception as e:
        print(f"✅ Path construction exception: {type(e)} - '{e}'")

    print("\n📍 STEP 2: Path.exists() call")
    try:
        with patch("pathlib.Path") as mock_path_class:
            # Create a mock path instance that raises our exception on exists()
            mock_path_instance = mock_path_class.return_value
            mock_path_instance.exists.side_effect = Exception("File system error")

            path = Path("pyproject.toml")
            result = path.exists()
            print(f"✅ exists() returned: {result}")
    except Exception as e:
        print(f"✅ exists() exception: {type(e)} - '{e}'")

    print("\n📍 STEP 3: File open operation")
    try:
        with patch("pathlib.Path") as mock_path_class:
            mock_path_instance = mock_path_class.return_value
            mock_path_instance.exists.return_value = True
            mock_path_instance.open.side_effect = Exception("File system error")

            path = Path("pyproject.toml")
            if path.exists():
                with open(path, "rb") as f:
                    print(f"✅ File opened: {f}")
    except Exception as e:
        print(f"✅ File open exception: {type(e)} - '{e}'")

    print("\n📍 STEP 4: TOML load operation")
    try:
        # Create invalid file content that would cause TypeError
        invalid_content = b"invalid content"
        fake_file = BytesIO(invalid_content)

        result = toml.load(fake_file)
        print(f"✅ TOML loaded: {result}")
    except Exception as e:
        print(f"✅ TOML load exception: {type(e)} - '{e}'")

    print("\n📍 STEP 5: Test actual function with different patch points")
    try:
        from cli.main import _validate_pyproject_file

        # Patch different methods to see which causes the TypeError
        with patch("cli.main.Path") as mock_path_class:
            mock_path_instance = mock_path_class.return_value
            mock_path_instance.exists.return_value = True
            mock_path_instance.__enter__ = lambda self: mock_path_instance
            mock_path_instance.__exit__ = lambda self, *args: None
            mock_path_instance.read_bytes.side_effect = Exception("File system error")

            result = _validate_pyproject_file()
            print(f"✅ Function result: {result}")

    except Exception as e:
        print(f"✅ Function exception: {type(e)} - '{e}'")


if __name__ == "__main__":
    debug_step_by_step()
