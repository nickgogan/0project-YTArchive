"""Logging Service for centralized log management."""

import json
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException, Query
from services.common.base import BaseService, ServiceSettings
from services.common.models import LogLevel, LogMessage, LogType


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

        @self.app.get("/logs", tags=["Logging"])
        async def get_logs(
            service: Optional[str] = Query(None, description="Filter by service name"),
            level: Optional[LogLevel] = Query(None, description="Filter by log level"),
            log_type: Optional[LogType] = Query(None, description="Filter by log type"),
            date: Optional[str] = Query(
                None, description="Filter by date (YYYY-MM-DD format)"
            ),
            limit: int = Query(100, description="Maximum number of logs to return"),
        ):
            """Retrieve logs with optional filtering."""
            try:
                logs = await self._get_filtered_logs(
                    service, level, log_type, date, limit
                )
                return {"logs": logs, "count": len(logs)}
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Failed to retrieve logs: {str(e)}"
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

    async def _get_filtered_logs(
        self,
        service: Optional[str],
        level: Optional[LogLevel],
        log_type: Optional[LogType],
        date: Optional[str],
        limit: int,
    ) -> List[dict]:
        """Get logs with filtering applied."""
        logs = []

        # Determine which directories and files to search
        if log_type:
            directories = [self.logs_dir / log_type.value]
        else:
            directories = [
                self.logs_dir / "runtime",
                self.logs_dir / "failed_downloads",
                self.logs_dir / "error_reports",
            ]

        # Determine which dates to search
        if date:
            target_files = [f"{date}.log"]
        else:
            # Get all .log files, sorted by date (newest first)
            target_files = []
            for directory in directories:
                if directory.exists():
                    log_files = sorted(directory.glob("*.log"), reverse=True)
                    target_files.extend([f.name for f in log_files])
            target_files = sorted(list(set(target_files)), reverse=True)

        # Read and filter logs
        for directory in directories:
            if not directory.exists():
                continue

            for filename in target_files:
                log_file = directory / filename
                if not log_file.exists():
                    continue

                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if not line.strip():
                                continue
                            try:
                                log_entry = json.loads(line.strip())

                                # Apply filters
                                if service and log_entry.get("service") != service:
                                    continue
                                if level and log_entry.get("level") != level.value:
                                    continue

                                logs.append(log_entry)

                                # Stop if we've reached the limit
                                if len(logs) >= limit:
                                    return logs
                            except json.JSONDecodeError:
                                # Skip malformed JSON lines
                                continue
                except IOError:
                    # Skip files we can't read
                    continue

        # Sort by timestamp (newest first) and return
        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return logs[:limit]


if __name__ == "__main__":
    settings = ServiceSettings(port=8001)  # Port for logging service
    service = LoggingService("LoggingService", settings)
    service.run()
