"""Tests for the LoggingService."""

import json
from pathlib import Path

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
