"""Basic error reporting implementation."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .contracts import ErrorReporter
from .types import ErrorContext, ErrorReport, ErrorSeverity


class BasicErrorReporter(ErrorReporter):
    """Basic file-based error reporter."""

    def __init__(self, reports_dir: str = "logs/error_reports"):
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # In-memory error history for analysis
        self.error_history: List[ErrorReport] = []
        self.max_history_size = 100

    async def report_error(
        self, exception: Exception, severity: ErrorSeverity, context: ErrorContext
    ) -> ErrorReport:
        """Report an error with full context."""

        # Generate unique error ID
        error_id = f"ERR_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{hash(str(exception)) % 10000:04d}"

        # Extract exception information
        exception_type = type(exception).__name__

        # Create error report
        report = ErrorReport(
            id=error_id,
            timestamp=datetime.now(timezone.utc),
            severity=severity,
            title=f"{exception_type}: {str(exception)[:100]}",
            message=str(exception),
            exception_type=exception_type,
            context=context,
            suggested_actions=self._generate_suggestions(exception),
            recovery_possible=self._is_recovery_possible(exception),
            retry_recommended=self._should_retry(exception),
        )

        # Add to history
        self.error_history.append(report)
        if len(self.error_history) > self.max_history_size:
            self.error_history.pop(0)

        # Save to file
        await self._save_report(report)

        # Print to console based on severity
        self._log_error(report)

        return report

    async def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get error summary for the last N hours."""
        cutoff_time = datetime.now(timezone.utc).timestamp() - (hours * 3600)

        recent_errors = [
            error
            for error in self.error_history
            if error.timestamp.timestamp() > cutoff_time
        ]

        # Count by severity
        severity_counts = {}
        for severity in ErrorSeverity:
            severity_counts[severity.value] = sum(
                1 for error in recent_errors if error.severity == severity
            )

        return {
            "time_range_hours": hours,
            "total_errors": len(recent_errors),
            "severity_breakdown": severity_counts,
            "recent_errors": [
                {
                    "id": error.id,
                    "severity": error.severity.value,
                    "title": error.title,
                    "timestamp": error.timestamp.isoformat(),
                }
                for error in recent_errors[-10:]  # Last 10 errors
            ],
        }

    def _generate_suggestions(self, exception: Exception) -> List[str]:
        """Generate suggested actions based on error type."""
        suggestions = []
        exception_str = str(exception).lower()

        if "network" in exception_str or "connection" in exception_str:
            suggestions.extend(
                [
                    "Check internet connection",
                    "Verify proxy settings if using a proxy",
                    "Try again in a few minutes",
                ]
            )

        if "timeout" in exception_str:
            suggestions.extend(["Increase timeout settings", "Check network stability"])

        if "permission" in exception_str or "access" in exception_str:
            suggestions.extend(
                [
                    "Check file/directory permissions",
                    "Verify path exists and is accessible",
                ]
            )

        # Add general suggestions if no specific ones were found
        if not suggestions:
            exception_type = type(exception).__name__
            if exception_type == "ValueError":
                suggestions.extend(
                    [
                        "Check input parameters and data format",
                        "Verify configuration settings",
                        "Review error message for specific details",
                    ]
                )
            elif exception_type == "ConnectionError":
                suggestions.extend(
                    [
                        "Check network connectivity",
                        "Verify service endpoints are accessible",
                    ]
                )
            else:
                suggestions.extend(
                    [
                        "Review error details and logs",
                        "Try the operation again",
                        "Check system resources and configuration",
                    ]
                )

        return suggestions[:5]  # Limit to top 5 suggestions

    def _is_recovery_possible(self, exception: Exception) -> bool:
        """Determine if automatic recovery is possible."""
        exception_str = str(exception).lower()

        # Non-recoverable errors
        non_recoverable = [
            "video unavailable",
            "private video",
            "deleted",
            "copyright",
            "authentication failed",
        ]

        for pattern in non_recoverable:
            if pattern in exception_str:
                return False

        return True

    def _should_retry(self, exception: Exception) -> bool:
        """Determine if retry is recommended."""
        if not self._is_recovery_possible(exception):
            return False

        exception_str = str(exception).lower()

        # Retry recommended for temporary issues
        retry_patterns = [
            "timeout",
            "temporary",
            "rate limit",
            "connection",
            "server error",
        ]

        return any(pattern in exception_str for pattern in retry_patterns)

    async def _save_report(self, report: ErrorReport) -> None:
        """Save error report to file."""
        try:
            # Daily log file
            date_str = report.timestamp.strftime("%Y-%m-%d")
            log_file = self.reports_dir / f"{date_str}.log"

            # Append to daily log
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(report.model_dump(mode="json"), default=str) + "\n")

        except Exception as e:
            print(f"Failed to save error report: {e}")

    def _log_error(self, report: ErrorReport) -> None:
        """Log error to console based on severity."""
        severity_colors = {
            ErrorSeverity.CRITICAL: "\033[91m",  # Red
            ErrorSeverity.HIGH: "\033[93m",  # Yellow
            ErrorSeverity.MEDIUM: "\033[94m",  # Blue
            ErrorSeverity.LOW: "\033[92m",  # Green
            ErrorSeverity.INFO: "\033[95m",  # Magenta
        }

        color = severity_colors.get(report.severity, "")
        reset = "\033[0m"

        print(f"{color}[{report.severity.upper()}] {report.title}{reset}")
        print(f"Error ID: {report.id}")

        if report.suggested_actions:
            print("Suggested actions:")
            for action in report.suggested_actions[:3]:  # Show top 3
                print(f"  • {action}")
        print()  # Empty line
