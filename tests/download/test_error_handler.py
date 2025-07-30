"""Tests for DownloadErrorHandler implementation."""

import pytest
import yt_dlp
from unittest.mock import patch, MagicMock

from services.download.error_handler import DownloadErrorHandler
from services.error_recovery.types import ErrorContext, ErrorSeverity, RetryReason


class TestDownloadErrorHandler:
    """Test cases for DownloadErrorHandler."""

    @pytest.fixture
    def error_handler(self):
        """Create DownloadErrorHandler instance for testing."""
        return DownloadErrorHandler()

    @pytest.fixture
    def error_context(self):
        """Create sample ErrorContext for testing."""
        return ErrorContext(
            operation_name="download_video",
            operation_context={
                "video_id": "test123",
                "video_url": "https://www.youtube.com/watch?v=test123",
                "output_path": "/tmp/downloads",
                "quality": "720p",
                "task_id": "task-123",
            },
            attempt_count=1,
        )

    @pytest.mark.unit
    def test_should_retry_network_errors(self, error_handler, error_context):
        """Test that network errors are retried."""
        network_errors = [
            Exception("Connection timeout occurred"),
            Exception("Network unreachable"),
            Exception("DNS resolution failed"),
            Exception("Connection refused"),
            Exception("Connection reset by peer"),
            Exception("Broken pipe error"),
        ]

        for error in network_errors:
            assert error_handler.should_retry(error, error_context) is True

    @pytest.mark.unit
    def test_should_not_retry_youtube_permanent_errors(
        self, error_handler, error_context
    ):
        """Test that permanent YouTube errors are not retried."""
        youtube_errors = [
            Exception("Video unavailable: Private video"),
            Exception("Video has been removed by user"),
            Exception("This video is not available in your region"),
            Exception("Age restricted content"),
            Exception("Copyright claim - video removed"),
        ]

        for error in youtube_errors:
            assert error_handler.should_retry(error, error_context) is False

    @pytest.mark.unit
    def test_should_not_retry_filesystem_permission_errors(
        self, error_handler, error_context
    ):
        """Test that filesystem permission errors are not retried."""
        permission_errors = [
            Exception("Permission denied: Cannot write to directory"),
            Exception("Read-only file system"),
        ]

        for error in permission_errors:
            assert error_handler.should_retry(error, error_context) is False

    @pytest.mark.unit
    def test_should_retry_transient_ytdlp_errors(self, error_handler, error_context):
        """Test that transient yt-dlp errors are retried."""
        transient_errors = [
            yt_dlp.DownloadError("Temporary failure in name resolution"),
            yt_dlp.DownloadError("Server temporarily unavailable, try again later"),
        ]

        for error in transient_errors:
            assert error_handler.should_retry(error, error_context) is True

    @pytest.mark.unit
    def test_should_retry_disk_space_errors(self, error_handler, error_context):
        """Test that disk space errors are retried (for cleanup opportunity)."""
        disk_errors = [
            Exception("No space left on device"),
            Exception("Disk full error occurred"),
        ]

        for error in disk_errors:
            assert error_handler.should_retry(error, error_context) is True

    @pytest.mark.unit
    def test_should_retry_unknown_errors_once(self, error_handler, error_context):
        """Test that unknown errors are retried once."""
        unknown_error = Exception("Some unknown error occurred")

        # First attempt should retry
        error_context.attempt_count = 1
        assert error_handler.should_retry(unknown_error, error_context) is True

        # Third attempt should not retry
        error_context.attempt_count = 3
        assert error_handler.should_retry(unknown_error, error_context) is False

    @pytest.mark.unit
    def test_error_severity_classification(self, error_handler, error_context):
        """Test error severity classification."""
        # Critical errors
        critical_errors = [
            Exception("File corrupted during download"),
            Exception("Invalid format detected"),
        ]
        for error in critical_errors:
            assert (
                error_handler.get_error_severity(error, error_context)
                == ErrorSeverity.CRITICAL
            )

        # High severity errors
        high_errors = [
            Exception("Video unavailable: Private video"),
            Exception("Permission denied: Cannot write"),
        ]
        for error in high_errors:
            assert (
                error_handler.get_error_severity(error, error_context)
                == ErrorSeverity.HIGH
            )

        # Medium severity errors
        medium_errors = [
            Exception("Network connection timeout"),
            Exception("No space left on device"),
        ]
        for error in medium_errors:
            assert (
                error_handler.get_error_severity(error, error_context)
                == ErrorSeverity.MEDIUM
            )

        # Low severity errors
        low_error = yt_dlp.DownloadError("Temporary issue")
        assert (
            error_handler.get_error_severity(low_error, error_context)
            == ErrorSeverity.LOW
        )

    @pytest.mark.unit
    def test_retry_reason_classification(self, error_handler, error_context):
        """Test retry reason classification for strategy selection."""
        # Network errors
        network_error = Exception("Connection timeout occurred")
        assert (
            error_handler.get_retry_reason(network_error, error_context)
            == RetryReason.NETWORK_ERROR
        )

        # Server errors
        server_error = Exception("HTTP Error 503: Service Unavailable")
        assert (
            error_handler.get_retry_reason(server_error, error_context)
            == RetryReason.SERVER_ERROR
        )

        # Rate limiting
        rate_limit_error = Exception("Rate limit exceeded - too many requests")
        assert (
            error_handler.get_retry_reason(rate_limit_error, error_context)
            == RetryReason.RATE_LIMITED
        )

        # Resource exhaustion
        resource_error = Exception("No space left on device")
        assert (
            error_handler.get_retry_reason(resource_error, error_context)
            == RetryReason.RESOURCE_EXHAUSTED
        )

        # Timeout
        timeout_error = Exception("Request timeout after 30 seconds")
        assert (
            error_handler.get_retry_reason(timeout_error, error_context)
            == RetryReason.TIMEOUT
        )

        # Unknown
        unknown_error = Exception("Some other error")
        assert (
            error_handler.get_retry_reason(unknown_error, error_context)
            == RetryReason.UNKNOWN
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_disk_space_error(self, error_handler, error_context):
        """Test handling of disk space errors."""
        error = Exception("No space left on device")
        handled = await error_handler.handle_error(error, error_context)
        suggestions = error_handler.get_recovery_suggestions(error)

        assert handled is True
        assert len(suggestions) > 0
        assert "disk space" in suggestions[0].lower()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_network_error(self, error_handler, error_context):
        """Test handling of network errors."""
        error = Exception("Connection timeout occurred")
        handled = await error_handler.handle_error(error, error_context)
        suggestions = error_handler.get_recovery_suggestions(error)

        assert handled is True
        assert len(suggestions) > 0
        assert "connectivity" in suggestions[0].lower()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_youtube_error(self, error_handler, error_context):
        """Test handling of YouTube-specific errors."""
        error = Exception("Video unavailable: Private video")
        handled = await error_handler.handle_error(error, error_context)
        suggestions = error_handler.get_recovery_suggestions(error)

        assert handled is False  # YouTube errors should not be retried
        assert len(suggestions) > 0
        assert "video" in suggestions[0].lower()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_ytdlp_error(self, error_handler, error_context):
        """Test handling of yt-dlp specific errors."""
        error = yt_dlp.DownloadError("Extraction failed")
        handled = await error_handler.handle_error(error, error_context)
        suggestions = error_handler.get_recovery_suggestions(error)

        assert handled is True
        assert len(suggestions) > 0
        assert "yt-dlp" in suggestions[0].lower()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_unhandled_error(self, error_handler, error_context):
        """Test handling of unrecognized errors."""
        error = Exception("Some completely unknown error type")
        handled = await error_handler.handle_error(error, error_context)
        suggestions = error_handler.get_recovery_suggestions(error)

        assert handled is False
        assert len(suggestions) > 0  # Should return default suggestions

    @pytest.mark.unit
    @patch("pathlib.Path.glob")
    def test_cleanup_after_failure_success(
        self, mock_glob, error_handler, error_context
    ):
        """Test successful cleanup after download failure."""
        # Mock finding partial download files
        mock_part_file = MagicMock()
        mock_part_file.__str__ = lambda self: "/tmp/test.part"
        mock_tmp_file = MagicMock()
        mock_tmp_file.__str__ = lambda self: "/tmp/test.tmp"

        mock_glob.side_effect = lambda pattern: {
            "*.part": [mock_part_file],
            "*.tmp": [mock_tmp_file],
        }.get(pattern, [])

        # Test successful cleanup
        result = error_handler.cleanup_after_failure(error_context)

        assert result is True
        # Verify unlink was called on both file objects
        mock_part_file.unlink.assert_called_once()
        mock_tmp_file.unlink.assert_called_once()

    @pytest.mark.unit
    def test_cleanup_after_failure_no_output_path(self, error_handler):
        """Test cleanup when no output_path in context."""
        context = ErrorContext(
            operation_name="download_video",
            operation_context={"video_id": "test123"},  # No output_path
            attempt_count=1,
        )

        result = error_handler.cleanup_after_failure(context)
        assert result is False

    @pytest.mark.unit
    @patch("pathlib.Path.glob")
    def test_cleanup_after_failure_no_files(
        self, mock_glob, error_handler, error_context
    ):
        """Test cleanup when no partial files exist."""
        # Mock no files found
        mock_glob.return_value = []

        result = error_handler.cleanup_after_failure(error_context)
        assert result is False

    @pytest.mark.unit
    @patch("pathlib.Path.glob")
    def test_cleanup_after_failure_with_exception(
        self, mock_glob, error_handler, error_context
    ):
        """Test cleanup when file deletion fails."""
        # Mock finding files but deletion fails
        mock_file = MagicMock()
        mock_file.__str__ = lambda self: "/tmp/test.part"
        mock_file.unlink.side_effect = OSError("Permission denied")
        mock_glob.side_effect = (
            lambda pattern: [mock_file] if "*.part" in pattern else []
        )

        # Should still return False but not crash
        result = error_handler.cleanup_after_failure(error_context)
        assert result is False
