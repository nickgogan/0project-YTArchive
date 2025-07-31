"""Tests for the LoggingService."""

import json
from pathlib import Path
import tempfile

import pytest
from httpx import AsyncClient

from services.common.base import ServiceSettings
from services.common.models import LogMessage, LogLevel, LogType
from services.logging.main import LoggingService


@pytest.fixture
def logging_service():
    """Create a LoggingService instance for testing."""
    settings = ServiceSettings(port=8001)
    return LoggingService("TestLoggingService", settings)


@pytest.fixture
async def logging_client(logging_service):
    """Create an HTTP client for the logging service."""
    async with AsyncClient(app=logging_service.app, base_url="http://test") as client:
        yield client


@pytest.mark.service
@pytest.mark.asyncio
async def test_log_endpoint(logging_service: LoggingService):
    """Test that the /log endpoint correctly stores log messages."""
    async with AsyncClient(app=logging_service.app, base_url="http://test") as client:
        # Create a test log message
        log_data = {
            "service": "TestService",
            "level": "INFO",
            "message": "Test log message",
            "log_type": "runtime",
        }

        response = await client.post("/log", json=log_data)

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "logged"
    assert "timestamp" in result


@pytest.mark.service
@pytest.mark.asyncio
async def test_log_file_creation(logging_service: LoggingService):
    """Test that log files are created in the correct directories."""
    # Create a test log message
    log_message = LogMessage(
        service="TestService",
        level=LogLevel.INFO,
        message="Test message",
        log_type=LogType.RUNTIME,
    )

    # Write the log
    await logging_service._write_log_to_file(log_message)

    # Check that the file was created
    date_str = log_message.timestamp.strftime("%Y-%m-%d")
    expected_file = Path("logs/runtime") / f"{date_str}.log"

    assert expected_file.exists()

    # Check the file content (read the last line since there might be multiple entries)
    with open(expected_file, "r") as f:
        lines = f.read().strip().split("\n")
        # Get the last line (our test log entry)
        last_line = lines[-1]
        log_entry = json.loads(last_line)

        assert log_entry["service"] == "TestService"
        assert log_entry["level"] == "INFO"
        assert log_entry["message"] == "Test message"


@pytest.mark.service
@pytest.mark.asyncio
async def test_get_logs_endpoint(logging_service: LoggingService):
    """Test that the GET /logs endpoint retrieves logs with filtering."""
    # First, create some test log messages
    log_messages = [
        LogMessage(
            service="ServiceA",
            level=LogLevel.INFO,
            message="Info message from ServiceA",
            log_type=LogType.RUNTIME,
        ),
        LogMessage(
            service="ServiceB",
            level=LogLevel.ERROR,
            message="Error message from ServiceB",
            log_type=LogType.ERROR_REPORTS,
        ),
    ]

    # Write the logs
    for log_msg in log_messages:
        await logging_service._write_log_to_file(log_msg)

    # Test the GET endpoint
    async with AsyncClient(app=logging_service.app, base_url="http://test") as client:
        # Test getting all logs
        response = await client.get("/logs")
        assert response.status_code == 200
        result = response.json()
        assert "logs" in result
        assert "count" in result
        assert result["count"] >= 2  # Should have at least our 2 test logs

        # Test filtering by service
        response = await client.get("/logs?service=ServiceA")
        assert response.status_code == 200
        result = response.json()
        assert result["count"] >= 1
        # All returned logs should be from ServiceA
        for log in result["logs"]:
            assert log["service"] == "ServiceA"

        # Test filtering by level
        response = await client.get("/logs?level=ERROR")
        assert response.status_code == 200
        result = response.json()
        assert result["count"] >= 1
        # All returned logs should be ERROR level
        for log in result["logs"]:
            assert log["level"] == "ERROR"


@pytest.mark.service
@pytest.mark.asyncio
async def test_clear_logs_requires_confirmation():
    """Test that clear-logs endpoint requires confirmation flag."""
    settings = ServiceSettings(port=8001)
    logging_service = LoggingService("TestLoggingService", settings)

    async with AsyncClient(app=logging_service.app, base_url="http://test") as client:
        # Test without confirmation - should fail
        response = await client.post("/clear-logs")
        assert response.status_code == 400
        result = response.json()
        assert "Must set confirm=true" in result["detail"]

        # Test with confirm=false - should fail
        response = await client.post("/clear-logs?confirm=false")
        assert response.status_code == 400
        result = response.json()
        assert "Must set confirm=true" in result["detail"]


@pytest.mark.service
@pytest.mark.asyncio
async def test_clear_logs_all_directories():
    """Test clearing all log directories."""
    # Create logging service with temporary directory
    settings = ServiceSettings(port=8001)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        logs_path = temp_path / "logs"

        logging_service = LoggingService("TestLoggingService", settings)
        logging_service.logs_dir = logs_path

        # Create test directory structure with files
        test_dirs = ["runtime", "jobs", "temp", "error_reports"]
        total_files_created = 0

        for dir_name in test_dirs:
            dir_path = logging_service.logs_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)

            # Create some test files
            for i in range(3):
                test_file = dir_path / f"test_file_{i}.log"
                test_file.write_text(f"Test content {i}")
                total_files_created += 1

        async with AsyncClient(
            app=logging_service.app, base_url="http://test"
        ) as client:
            # Clear all directories with confirmation
            response = await client.post("/clear-logs?confirm=true")
            assert response.status_code == 200

            result = response.json()
            assert result["status"] == "success"
            assert "details" in result

            details = result["details"]
            assert details["total_files_removed"] == total_files_created
            assert len(details["directories_processed"]) == len(test_dirs)
            assert len(details["errors"]) == 0

            # Verify directories still exist but are empty
            for dir_name in test_dirs:
                dir_path = logging_service.logs_dir / dir_name
                assert dir_path.exists()
                assert dir_path.is_dir()
                assert len(list(dir_path.iterdir())) == 0


@pytest.mark.service
@pytest.mark.asyncio
async def test_clear_logs_specific_directories():
    """Test clearing only specific directories."""
    settings = ServiceSettings(port=8001)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        logs_path = temp_path / "logs"

        logging_service = LoggingService("TestLoggingService", settings)
        logging_service.logs_dir = logs_path

        # Create test directory structure
        all_dirs = ["runtime", "jobs", "temp"]
        dirs_to_clear = ["jobs", "temp"]
        dirs_to_keep = ["runtime"]

        for dir_name in all_dirs:
            dir_path = logging_service.logs_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)

            # Create test files in each directory
            for i in range(2):
                test_file = dir_path / f"test_{i}.log"
                test_file.write_text(f"Content {i}")

        async with AsyncClient(
            app=logging_service.app, base_url="http://test"
        ) as client:
            # Clear only specific directories
            response = await client.post(
                "/clear-logs?directories=jobs&directories=temp&confirm=true"
            )
            assert response.status_code == 200

            result = response.json()
            assert result["status"] == "success"

            details = result["details"]
            assert (
                details["total_files_removed"] == 4
            )  # 2 files each from jobs and temp
            assert len(details["directories_processed"]) == 2

            # Verify only specified directories were cleared
            for dir_name in dirs_to_clear:
                dir_path = logging_service.logs_dir / dir_name
                assert dir_path.exists()
                assert len(list(dir_path.iterdir())) == 0

            # Verify other directories were not touched
            for dir_name in dirs_to_keep:
                dir_path = logging_service.logs_dir / dir_name
                assert dir_path.exists()
                assert len(list(dir_path.iterdir())) == 2  # Original files still there


@pytest.mark.service
@pytest.mark.asyncio
async def test_clear_logs_invalid_directories():
    """Test error handling for invalid directory names."""
    settings = ServiceSettings(port=8001)
    logging_service = LoggingService("TestLoggingService", settings)

    async with AsyncClient(app=logging_service.app, base_url="http://test") as client:
        # Try to clear invalid directory
        response = await client.post(
            "/clear-logs?directories=invalid_dir&directories=another_invalid&confirm=true"
        )
        assert response.status_code == 500

        result = response.json()
        assert "Invalid directories specified" in result["detail"]
        assert "invalid_dir" in result["detail"]
        assert "another_invalid" in result["detail"]


@pytest.mark.service
@pytest.mark.asyncio
async def test_clear_logs_nonexistent_directories():
    """Test handling of non-existent directories."""
    settings = ServiceSettings(port=8001)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        logs_path = temp_path / "logs"

        logging_service = LoggingService("TestLoggingService", settings)
        logging_service.logs_dir = logs_path

        # Don't create any directories - they won't exist

        async with AsyncClient(
            app=logging_service.app, base_url="http://test"
        ) as client:
            # Try to clear specific directories that don't exist
            response = await client.post(
                "/clear-logs?directories=runtime&directories=jobs&confirm=true"
            )
            assert response.status_code == 200

            result = response.json()
            assert result["status"] == "success"

            details = result["details"]
            assert details["total_files_removed"] == 0
            assert len(details["directories_processed"]) == 0
            assert len(details["directories_skipped"]) == 2

            # Verify skip reasons
            skipped_dirs = {
                item["directory"]: item["reason"]
                for item in details["directories_skipped"]
            }
            assert "runtime" in skipped_dirs
            assert "jobs" in skipped_dirs
            assert "Directory does not exist" in skipped_dirs["runtime"]
            assert "Directory does not exist" in skipped_dirs["jobs"]


@pytest.mark.service
@pytest.mark.asyncio
async def test_clear_logs_with_subdirectories():
    """Test clearing directories that contain subdirectories."""
    settings = ServiceSettings(port=8001)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        logs_path = temp_path / "logs"

        logging_service = LoggingService("TestLoggingService", settings)
        logging_service.logs_dir = logs_path

        # Create directory with nested structure
        jobs_dir = logging_service.logs_dir / "jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories and files
        subdir1 = jobs_dir / "subdir1"
        subdir2 = jobs_dir / "subdir2"
        subdir1.mkdir()
        subdir2.mkdir()

        # Add files in main directory and subdirectories
        (jobs_dir / "main_file.json").write_text('{"test": "data"}')
        (subdir1 / "sub_file1.json").write_text('{"sub": "data1"}')
        (subdir2 / "sub_file2.json").write_text('{"sub": "data2"}')
        (subdir2 / "sub_file3.log").write_text("log entry")

        async with AsyncClient(
            app=logging_service.app, base_url="http://test"
        ) as client:
            # Clear the jobs directory
            response = await client.post("/clear-logs?directories=jobs&confirm=true")
            assert response.status_code == 200

            result = response.json()
            assert result["status"] == "success"

            details = result["details"]
            assert (
                details["total_files_removed"] == 4
            )  # All files in directory and subdirectories
            assert len(details["directories_processed"]) == 1
            assert len(details["errors"]) == 0

            # Verify main directory exists but is empty
            assert jobs_dir.exists()
            assert jobs_dir.is_dir()
            assert len(list(jobs_dir.iterdir())) == 0


@pytest.mark.service
@pytest.mark.asyncio
async def test_clear_logs_file_count_accuracy():
    """Test that file count reporting is accurate."""
    settings = ServiceSettings(port=8001)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        logs_path = temp_path / "logs"

        logging_service = LoggingService("TestLoggingService", settings)
        logging_service.logs_dir = logs_path

        # Create multiple directories with varying file counts
        test_data = {
            "runtime": 5,
            "jobs": 10,
            "temp": 0,  # Empty directory
            "error_reports": 3,
        }

        total_expected_files = 0

        for dir_name, file_count in test_data.items():
            dir_path = logging_service.logs_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)

            for i in range(file_count):
                test_file = dir_path / f"file_{i}.log"
                test_file.write_text(f"File {i} content")
                total_expected_files += 1

        async with AsyncClient(
            app=logging_service.app, base_url="http://test"
        ) as client:
            # Clear all directories
            response = await client.post("/clear-logs?confirm=true")
            assert response.status_code == 200

            result = response.json()
            details = result["details"]

            # Verify total count is accurate
            assert details["total_files_removed"] == total_expected_files

            # Verify individual directory counts
            processed_dirs = {
                item["directory"]: item["files_removed"]
                for item in details["directories_processed"]
            }

            for dir_name, expected_count in test_data.items():
                if expected_count > 0:
                    assert dir_name in processed_dirs
                    assert processed_dirs[dir_name] == expected_count


@pytest.mark.service
@pytest.mark.asyncio
async def test_clear_logs_preserves_directory_structure():
    """Test that directory clearing preserves the overall structure."""
    settings = ServiceSettings(port=8001)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        logs_path = temp_path / "logs"

        logging_service = LoggingService("TestLoggingService", settings)
        logging_service.logs_dir = logs_path

        # Create all known directories
        all_directories = [
            "runtime",
            "failed_downloads",
            "error_reports",
            "download_service",
            "download_state",
            "jobs",
            "playlist_results",
            "recovery_plans",
            "temp",
        ]

        for dir_name in all_directories:
            dir_path = logging_service.logs_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)

            # Add a test file to each directory
            test_file = dir_path / "test.log"
            test_file.write_text("test content")

        async with AsyncClient(
            app=logging_service.app, base_url="http://test"
        ) as client:
            # Clear all directories
            response = await client.post("/clear-logs?confirm=true")
            assert response.status_code == 200

            # Verify all directories still exist and are directories
            for dir_name in all_directories:
                dir_path = logging_service.logs_dir / dir_name
                assert dir_path.exists(), f"Directory {dir_name} should still exist"
                assert dir_path.is_dir(), f"{dir_name} should still be a directory"
                assert (
                    len(list(dir_path.iterdir())) == 0
                ), f"Directory {dir_name} should be empty"
