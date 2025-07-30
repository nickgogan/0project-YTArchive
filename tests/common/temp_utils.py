"""
Centralized temporary directory utilities for tests.

This module provides utilities to ensure all test temporary directories
are created within the logs/ folder for better organization and cleanup.
"""

import shutil
import tempfile
from pathlib import Path
from typing import Generator
import pytest


class CentralizedTempDir:
    """Manages temporary directories within the logs/temp folder."""

    def __init__(self, base_dir: str = "logs/temp"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_temp_dir(self, prefix: str = "test_") -> Path:
        """Create a temporary directory within logs/temp."""
        return Path(tempfile.mkdtemp(prefix=prefix, dir=self.base_dir))

    def create_temp_file(self, suffix: str = ".tmp", prefix: str = "test_") -> Path:
        """Create a temporary file within logs/temp."""
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=self.base_dir)
        import os

        os.close(fd)  # Close the file descriptor
        return Path(path)

    def cleanup_all(self):
        """Clean up all temporary directories and files."""
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)


# Global instance for test usage
_temp_manager = CentralizedTempDir()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Pytest fixture for centralized temporary directory."""
    temp_path = _temp_manager.create_temp_dir()
    try:
        yield temp_path
    finally:
        if temp_path.exists():
            shutil.rmtree(temp_path)


@pytest.fixture
def temp_file() -> Generator[Path, None, None]:
    """Pytest fixture for centralized temporary file."""
    temp_path = _temp_manager.create_temp_file()
    try:
        yield temp_path
    finally:
        if temp_path.exists():
            temp_path.unlink()


def get_test_temp_dir(prefix: str = "test_") -> Path:
    """Get a temporary directory for manual cleanup."""
    return _temp_manager.create_temp_dir(prefix=prefix)


def cleanup_test_temps():
    """Clean up all test temporary directories."""
    _temp_manager.cleanup_all()


# Pytest session-level cleanup
@pytest.fixture(scope="session", autouse=True)
def cleanup_temps_on_exit():
    """Automatically clean up temporary directories at session end."""
    yield
    cleanup_test_temps()
