"""Logging Service for centralized log management."""

import json
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any

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

    def _ensure_log_directories(self) -> None:
        """Create the log directory structure if it doesn't exist."""
        directories = [
            self.logs_dir / "runtime",
            self.logs_dir / "failed_downloads",
            self.logs_dir / "error_reports",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def _add_logging_routes(self) -> None:
        """Add logging-specific routes."""

        @self.app.post("/log", tags=["Logging"])
        async def receive_log(log_message: LogMessage) -> Dict[str, str]:
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
        ) -> Dict[str, Any]:
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

        @self.app.post("/clear-logs", tags=["Logging"])
        async def clear_logs(
            directories: Optional[List[str]] = Query(
                None,
                description="Specific directories to clear (if not provided, clears all)",
            ),
            confirm: bool = Query(
                False, description="Confirmation flag to prevent accidental clearing"
            ),
        ) -> Dict[str, Any]:
            """Clear log files from specified directories while preserving structure."""
            if not confirm:
                raise HTTPException(
                    status_code=400,
                    detail="Must set confirm=true to clear logs. This action cannot be undone.",
                )

            try:
                result = await self._clear_log_directories(directories)
                return {
                    "status": "success",
                    "message": "Log directories cleared successfully",
                    "details": result,
                }
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Failed to clear logs: {str(e)}"
                )

    async def _write_log_to_file(self, log_message: LogMessage) -> None:
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
    ) -> List[Dict[str, Any]]:
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

    async def _clear_log_directories(
        self, target_directories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Clear files from log directories while preserving directory structure.

        Args:
            target_directories: List of specific directory names to clear.
                               If None, clears all known log directories.

        Returns:
            Dict containing results of the clearing operation.
        """
        # Define all known log directories
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

        # Determine which directories to clear
        if target_directories:
            # Validate requested directories exist in our known list
            invalid_dirs = [d for d in target_directories if d not in all_directories]
            if invalid_dirs:
                raise ValueError(
                    f"Invalid directories specified: {invalid_dirs}. Valid options: {all_directories}"
                )
            directories_to_clear = target_directories
        else:
            directories_to_clear = all_directories

        clearing_results: Dict[str, Any] = {
            "directories_processed": [],
            "directories_skipped": [],
            "total_files_removed": 0,
            "errors": [],
        }

        for dir_name in directories_to_clear:
            dir_path = self.logs_dir / dir_name

            try:
                if not dir_path.exists():
                    clearing_results["directories_skipped"].append(
                        {"directory": dir_name, "reason": "Directory does not exist"}
                    )
                    continue

                if not dir_path.is_dir():
                    clearing_results["directories_skipped"].append(
                        {"directory": dir_name, "reason": "Path is not a directory"}
                    )
                    continue

                # Count files before clearing
                files_before = list(dir_path.rglob("*"))
                files_count = len([f for f in files_before if f.is_file()])

                # Clear all files and subdirectories, but preserve the main directory
                await self._safe_clear_directory_contents(dir_path)

                clearing_results["directories_processed"].append(
                    {
                        "directory": dir_name,
                        "files_removed": files_count,
                        "path": str(dir_path),
                    }
                )
                clearing_results["total_files_removed"] += files_count

            except Exception as e:
                clearing_results["errors"].append(
                    {"directory": dir_name, "error": str(e)}
                )

        return clearing_results

    async def _safe_clear_directory_contents(self, directory_path: Path) -> None:
        """Safely clear all contents of a directory while preserving the directory itself.

        Args:
            directory_path: Path to the directory to clear.
        """
        if not directory_path.exists() or not directory_path.is_dir():
            return

        # Remove all contents of the directory
        for item in directory_path.iterdir():
            try:
                if item.is_file():
                    item.unlink()  # Remove file
                elif item.is_dir():
                    shutil.rmtree(item)  # Remove directory and all its contents
            except Exception as e:
                # Log the error but continue with other items
                print(f"Warning: Could not remove {item}: {e}")
                raise e


if __name__ == "__main__":
    settings = ServiceSettings(port=8001)  # Port for logging service
    service = LoggingService("LoggingService", settings)
    service.run()
