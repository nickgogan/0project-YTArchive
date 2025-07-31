"""Download service specific error handling implementation."""

import logging
from pathlib import Path
from typing import List, Optional

import yt_dlp  # type: ignore[import-untyped]
from services.error_recovery.types import ErrorContext, ErrorSeverity, RetryReason
from services.error_recovery.contracts import ServiceErrorHandler


logger = logging.getLogger(__name__)


class DownloadErrorHandler(ServiceErrorHandler):
    """Download service specific error handler for yt-dlp and download operations."""

    def __init__(self):
        self.network_error_keywords = [
            "timeout",
            "connection",
            "network",
            "dns",
            "resolve",
            "unreachable",
            "refused",
            "reset",
            "broken pipe",
            "http error",
            "server error",
        ]
        self.youtube_error_keywords = [
            "video unavailable",
            "private video",
            "deleted",
            "removed",
            "region",
            "age restricted",
            "copyright",
        ]
        self.filesystem_error_keywords = [
            "permission denied",
            "disk full",
            "no space",
            "read-only",
            "file exists",
            "directory not found",
        ]

    def should_retry(self, error: Exception, context: ErrorContext) -> bool:
        """Determine if an error should be retried."""
        error_str = str(error).lower()

        # Never retry certain permanent YouTube errors
        if any(keyword in error_str for keyword in self.youtube_error_keywords):
            logger.info(f"Permanent YouTube error detected, not retrying: {error}")
            return False

        # Never retry filesystem permission errors
        if "permission denied" in error_str or "read-only" in error_str:
            logger.info(f"Filesystem permission error, not retrying: {error}")
            return False

        # Retry network errors (most common retryable case)
        if any(keyword in error_str for keyword in self.network_error_keywords):
            logger.info(f"Network error detected, will retry: {error}")
            return True

        # Retry yt-dlp specific errors that are often transient
        if isinstance(error, yt_dlp.DownloadError):
            # Check if it's a transient yt-dlp error
            if "temporary failure" in error_str or "try again" in error_str:
                return True

        # Retry disk space errors after cleanup (if implemented)
        if "disk full" in error_str or "no space" in error_str:
            logger.warning(f"Disk space error, may retry after cleanup: {error}")
            return True

        # Default to retry for unknown errors, but limit attempts
        if context.attempt_count < 2:  # Only retry unknown errors once
            logger.info(f"Unknown error, will retry once: {error}")
            return True

        return False

    def get_error_severity(
        self, error: Exception, context: ErrorContext
    ) -> ErrorSeverity:
        """Classify error severity for prioritization."""
        error_str = str(error).lower()

        # Critical: Data loss or corruption risks
        if "corrupted" in error_str or "invalid format" in error_str:
            return ErrorSeverity.CRITICAL

        # High: Service unavailable or permanent failures
        if any(keyword in error_str for keyword in self.youtube_error_keywords):
            return ErrorSeverity.HIGH

        # High: Filesystem issues that prevent operation
        if "permission denied" in error_str or "readonly" in error_str:
            return ErrorSeverity.HIGH

        # Medium: Network issues (usually recoverable)
        if any(keyword in error_str for keyword in self.network_error_keywords):
            return ErrorSeverity.MEDIUM

        # Medium: Disk space (recoverable with cleanup)
        if "disk full" in error_str or "no space" in error_str:
            return ErrorSeverity.MEDIUM

        # Low: Temporary yt-dlp issues
        if isinstance(error, yt_dlp.DownloadError):
            return ErrorSeverity.LOW

        # Default to medium for unknown errors
        return ErrorSeverity.MEDIUM

    def get_retry_reason(
        self, error: Exception, context: ErrorContext
    ) -> Optional[RetryReason]:
        """Determine the reason for retry to select appropriate strategy."""
        error_str = str(error).lower()

        # Rate limiting errors
        if "rate limit" in error_str or "too many requests" in error_str:
            return RetryReason.RATE_LIMITED

        # Resource exhaustion errors
        if (
            "no space left" in error_str
            or "disk full" in error_str
            or "out of memory" in error_str
        ):
            return RetryReason.RESOURCE_EXHAUSTED

        # Timeout errors (specific timeout patterns)
        if "request timeout" in error_str or "timeout after" in error_str:
            return RetryReason.TIMEOUT

        # Server errors (HTTP 5xx errors)
        if (
            "http error 5" in error_str
            or "service unavailable" in error_str
            or "server error" in error_str
        ):
            return RetryReason.SERVER_ERROR

        # Network issues benefit from exponential backoff
        if any(keyword in error_str for keyword in self.network_error_keywords):
            return RetryReason.NETWORK_ERROR

        # Default for unknown retryable errors
        return RetryReason.UNKNOWN

    async def handle_error(self, error: Exception, context: ErrorContext) -> bool:
        """Perform service-specific error handling.

        Returns:
            bool: True if error was handled/recovered, False otherwise
        """
        error_str = str(error).lower()
        handled = False

        # Handle disk space issues (retryable)
        if "disk full" in error_str or "no space" in error_str:
            logger.info("Handled download error: disk_space_warning")
            handled = True

        # Handle network connectivity issues (retryable)
        elif any(keyword in error_str for keyword in self.network_error_keywords):
            logger.info("Handled download error: network_diagnostics")
            handled = True

        # Handle filesystem errors
        elif any(keyword in error_str for keyword in self.filesystem_error_keywords):
            logger.info("Handled download error: filesystem_issue")
            handled = (
                True  # Filesystem errors are handled (but some may not be retryable)
            )

        # Handle YouTube-specific errors (should not retry)
        elif any(keyword in error_str for keyword in self.youtube_error_keywords):
            logger.info(
                "Handled download error: youtube_error_classification (no retry)"
            )
            handled = False  # Don't retry YouTube-specific errors

        # Handle yt-dlp specific errors
        elif isinstance(error, yt_dlp.DownloadError):
            logger.info("Handled download error: ytdlp_error_analysis")
            handled = True

        # Log unhandled errors
        if not handled:
            logger.warning(f"Unhandled download error: {error}")

        return handled

    def get_recovery_suggestions(self, exception: Exception) -> List[str]:
        """Get service-specific recovery suggestions."""
        error_str = str(exception).lower()

        # Handle disk space issues
        if "disk full" in error_str or "no space" in error_str:
            return [
                "Check available disk space in output directory",
                "Consider cleaning up old downloads",
                "Move downloads to a different location with more space",
            ]

        # Handle network connectivity issues
        elif any(keyword in error_str for keyword in self.network_error_keywords):
            return [
                "Check internet connectivity",
                "Try a different network connection",
                "Verify YouTube is accessible from your location",
            ]

        # Handle YouTube-specific errors
        elif any(keyword in error_str for keyword in self.youtube_error_keywords):
            return [
                "Verify the video URL is correct and accessible",
                "Check if the video is available in your region",
                "Try accessing the video in a web browser",
            ]

        # Handle yt-dlp specific errors
        elif isinstance(exception, yt_dlp.DownloadError):
            return [
                "Update yt-dlp to the latest version",
                "Try a different video quality/format",
                "Check yt-dlp documentation for this error",
            ]

        return ["Check logs for more details", "Retry the operation"]

    def cleanup_after_failure(self, context: ErrorContext) -> bool:
        """Perform cleanup after download failure."""
        try:
            # Clean up partial download files if they exist
            if "output_path" in context.operation_context:
                output_path = Path(context.operation_context["output_path"])
                video_id = context.operation_context.get("video_id")

                if not video_id:
                    logger.warning("No video_id in context, cannot perform cleanup.")
                    return False

                # Look for partial download files
                partial_files = list(output_path.glob("*.part"))
                temp_files = list(output_path.glob("*.tmp"))

                cleaned_files = []
                for file_path in partial_files + temp_files:
                    try:
                        file_path.unlink()
                        cleaned_files.append(str(file_path))
                    except Exception as e:
                        logger.warning(f"Could not clean up file {file_path}: {e}")

                if cleaned_files:
                    logger.info(f"Cleaned up partial download files: {cleaned_files}")
                    return True
                elif partial_files or temp_files:
                    # Found files but couldn't clean any of them
                    return False

            return False

        except Exception as e:
            logger.error(f"Error during download cleanup: {e}")
            return False
