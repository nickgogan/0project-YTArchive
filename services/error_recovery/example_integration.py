"""
Example integration with BaseService showing how to use the error recovery library.

This demonstrates the hybrid approach:
1. Shared error recovery library (retry strategies, error reporting)
2. Service-specific error handling (domain-specific recovery logic)
"""

import asyncio

from services.common.base import BaseService, ServiceSettings
from services.error_recovery import ErrorRecoveryManager
from services.error_recovery.contracts import ServiceErrorHandler
from services.error_recovery.retry.strategies import ExponentialBackoffStrategy
from services.error_recovery.reporting import BasicErrorReporter
from services.error_recovery.types import ErrorContext, ErrorSeverity, RetryConfig


class DownloadServiceErrorHandler(ServiceErrorHandler):
    """Download service specific error handler."""

    async def handle_error(self, exception: Exception, context: ErrorContext) -> bool:
        """Handle download-specific errors."""
        exception_str = str(exception).lower()

        # Handle quality-related errors
        if "quality" in exception_str or "format not available" in exception_str:
            print(
                f"Download service: Attempting quality fallback for {context.video_id}"
            )
            # In real implementation, this would trigger quality fallback
            return True  # Indicate we handled it

        # Handle partial download resume
        if "connection" in exception_str and context.video_id:
            print(
                f"Download service: Attempting partial download resume for {context.video_id}"
            )
            # In real implementation, this would resume partial download
            return True

        return False  # Let the retry strategy handle it

    def get_recovery_suggestions(self, exception: Exception) -> list[str]:
        """Get download-specific recovery suggestions."""
        suggestions = []
        exception_str = str(exception).lower()

        if "quality" in exception_str:
            suggestions.append("Try with lower quality setting")
            suggestions.append("Enable automatic quality fallback")

        if "network" in exception_str:
            suggestions.append("Check video availability")
            suggestions.append("Try resuming partial download")

        return suggestions


class EnhancedDownloadService(BaseService):
    """Example enhanced download service with error recovery."""

    def __init__(self, service_name: str, settings: ServiceSettings):
        super().__init__(service_name, settings)

        # Configure error recovery components
        retry_config = RetryConfig(
            max_attempts=3, base_delay=1.0, max_delay=60.0, jitter=True
        )

        retry_strategy = ExponentialBackoffStrategy(retry_config)
        error_reporter = BasicErrorReporter()
        service_handler = DownloadServiceErrorHandler()

        # Initialize error recovery manager
        self.error_recovery = ErrorRecoveryManager(
            retry_strategy=retry_strategy,
            error_reporter=error_reporter,
            service_handler=service_handler,
        )

    async def download_video_with_recovery(
        self, video_id: str, quality: str = "1080p"
    ) -> str:
        """Download video with advanced error recovery."""

        context = ErrorContext(
            video_id=video_id,
            service_name=self.service_name,
            operation="download_video",
            user_config={"quality": quality},
        )

        try:
            # Execute download with retry logic
            result = await self.error_recovery.execute_with_retry(
                func=self._download_video_internal,
                context=context,
                video_id=video_id,
                quality=quality,
            )
            return result

        except Exception as e:
            # Final error reporting if all retries failed
            await self.error_recovery.report_error(e, ErrorSeverity.HIGH, context)
            raise

    async def _download_video_internal(self, video_id: str, quality: str) -> str:
        """Internal download method that may fail."""
        print(f"Attempting to download {video_id} in {quality}")

        # Simulate various types of failures for demonstration
        import random

        failure_type = random.choice(["success", "network", "quality", "timeout"])

        if failure_type == "network":
            raise ConnectionError("Network connection failed")
        elif failure_type == "quality":
            raise ValueError("Requested quality not available")
        elif failure_type == "timeout":
            raise TimeoutError("Download timed out")

        # Success case
        return f"/downloads/{video_id}.mp4"

    async def get_error_dashboard(self) -> dict:
        """Get error recovery dashboard data."""
        retry_stats = {}
        if hasattr(self.error_recovery.retry_strategy, "total_attempts"):
            retry_stats = {
                "total_attempts": getattr(
                    self.error_recovery.retry_strategy, "total_attempts", 0
                ),
                "successful_attempts": getattr(
                    self.error_recovery.retry_strategy, "successful_attempts", 0
                ),
                "failed_attempts": getattr(
                    self.error_recovery.retry_strategy, "failed_attempts", 0
                ),
            }

        return {
            "error_summary": await self.error_recovery.error_reporter.get_error_summary(),
            "active_recoveries": self.error_recovery.get_active_recoveries(),
            "retry_stats": retry_stats,
        }


# Example usage
async def main():
    """Demonstrate the error recovery system."""
    settings = ServiceSettings(host="localhost", port=8001)
    service = EnhancedDownloadService("download", settings)

    print("Testing error recovery system...")

    try:
        result = await service.download_video_with_recovery("test_video_123", "1080p")
        print(f"Download successful: {result}")
    except Exception as e:
        print(f"Download failed after all retries: {e}")

    # Show dashboard
    dashboard = await service.get_error_dashboard()
    print("\nError Recovery Dashboard:")
    print(f"Total errors in last 24h: {dashboard['error_summary']['total_errors']}")
    print(f"Active recoveries: {len(dashboard['active_recoveries'])}")
    print(
        f"Retry success rate: {dashboard['retry_stats']['successful_attempts']} / {dashboard['retry_stats']['total_attempts']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
