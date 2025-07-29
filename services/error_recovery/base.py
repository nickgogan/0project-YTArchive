"""Base classes and core error recovery management."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from .contracts import ErrorReporter, RetryStrategy, ServiceErrorHandler
from .types import ErrorContext, ErrorReport, ErrorSeverity, RetryConfig


class ErrorRecoveryManager:
    """Central manager for error recovery across services."""

    def __init__(
        self,
        retry_strategy: RetryStrategy,
        error_reporter: ErrorReporter,
        service_handler: Optional[ServiceErrorHandler] = None,
    ):
        self.retry_strategy = retry_strategy
        self.error_reporter = error_reporter
        self.service_handler = service_handler

        # Track active recovery operations
        self.active_recoveries: Dict[str, dict] = {}

    async def execute_with_retry(
        self,
        func,
        context: ErrorContext,
        retry_config: Optional[RetryConfig] = None,
        *args,
        **kwargs,
    ):
        """Execute a function with retry logic."""
        retry_config = retry_config or RetryConfig()
        operation_id = str(uuid.uuid4())

        self.active_recoveries[operation_id] = {
            "function": func.__name__,
            "context": context,
            "started_at": datetime.now(timezone.utc),
            "attempts": 0,
        }

        try:
            for attempt in range(retry_config.max_attempts):
                try:
                    self.active_recoveries[operation_id]["attempts"] = attempt + 1
                    result = await func(*args, **kwargs)

                    # Success - record and return
                    self.retry_strategy.record_attempt(True)
                    return result

                except Exception as e:
                    # Record failed attempt
                    self.retry_strategy.record_attempt(False)

                    # Check if we should retry
                    if not await self.retry_strategy.should_retry(attempt, e, context):
                        break

                    # Try service-specific recovery first
                    if self.service_handler:
                        handled = await self.service_handler.handle_error(e, context)
                        if handled:
                            continue

                    # If not the last attempt, wait and retry
                    if attempt < retry_config.max_attempts - 1:
                        delay = await self.retry_strategy.get_delay(attempt, context)
                        await asyncio.sleep(delay)
                    else:
                        # Last attempt failed - report error
                        await self.error_reporter.report_error(
                            e, ErrorSeverity.HIGH, context
                        )
                        raise

        finally:
            # Clean up tracking
            self.active_recoveries.pop(operation_id, None)

    async def report_error(
        self, exception: Exception, severity: ErrorSeverity, context: ErrorContext
    ) -> ErrorReport:
        """Report an error through the configured reporter."""
        return await self.error_reporter.report_error(exception, severity, context)

    def get_active_recoveries(self) -> Dict[str, dict]:
        """Get currently active recovery operations."""
        return self.active_recoveries.copy()
