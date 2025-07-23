"""Logging Service for centralized log management."""

import json
from pathlib import Path

from fastapi import HTTPException
from services.common.base import BaseService, ServiceSettings
from services.common.models import LogMessage


class LoggingService(BaseService):
    """A service for centrally managing logs from all other services."""

    def __init__(self, service_name: str, settings: ServiceSettings):
        super().__init__(service_name, settings)
        self.logs_dir = Path("logs")
        self._ensure_log_directories()
        self._add_logging_routes()

    def _ensure_log_directories(self):
        """Create the log directory structure if it doesn't exist."""
        directories = [
            self.logs_dir / "runtime",
            self.logs_dir / "failed_downloads",
            self.logs_dir / "error_reports",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def _add_logging_routes(self):
        """Add logging-specific routes."""

        @self.app.post("/log", tags=["Logging"])
        async def receive_log(log_message: LogMessage):
            """Receive a log message from another service and store it."""
            try:
                await self._write_log_to_file(log_message)
                return {
                    "status": "logged",
                    "timestamp": log_message.timestamp.isoformat(),
                }
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Failed to write log: {str(e)}"
                )

    async def _write_log_to_file(self, log_message: LogMessage):
        """Write a log message to the appropriate file based on its type."""
        # Determine the subdirectory based on log type
        subdir = log_message.log_type.value
        log_dir = self.logs_dir / subdir

        # Create timestamped filename (one file per day)
        date_str = log_message.timestamp.strftime("%Y-%m-%d")
        log_file = log_dir / f"{date_str}.log"

        # Format the log entry
        log_entry = {
            "timestamp": log_message.timestamp.isoformat(),
            "service": log_message.service,
            "level": log_message.level.value,
            "message": log_message.message,
            "data": log_message.data,
        }

        # Write to file (append mode)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")


if __name__ == "__main__":
    settings = ServiceSettings(port=8001)  # Port for logging service
    service = LoggingService("LoggingService", settings)
    service.run()
