"""Base classes and core error recovery management."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from .contracts import ErrorReporter, RetryStrategy, ServiceErrorHandler
from .types import ErrorContext, ErrorReport, ErrorSeverity, RetryConfig, RetryReason


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

    def _determine_retry_reason(
        self, exception: Exception, context: ErrorContext
    ) -> RetryReason:
        """Determine retry reason from exception type and context."""
        if isinstance(exception, (ConnectionError, TimeoutError)):
            return RetryReason.NETWORK_ERROR
        elif isinstance(exception, ValueError) and "quota" in str(exception).lower():
            return RetryReason.API_QUOTA_EXCEEDED
        elif isinstance(exception, ValueError) and "rate" in str(exception).lower():
            return RetryReason.RATE_LIMITED
        elif isinstance(exception, (IOError, OSError)):
            return RetryReason.DOWNLOAD_FAILED
        elif hasattr(exception, "response") and hasattr(
            exception.response, "status_code"
        ):
            if exception.response.status_code == 503:
                return RetryReason.SERVICE_UNAVAILABLE
            elif exception.response.status_code == 429:
                return RetryReason.RATE_LIMITED
            elif exception.response.status_code >= 500:
                return RetryReason.SERVER_ERROR
        return RetryReason.UNKNOWN

    async def execute_with_retry(
        self,
        func,
        context: ErrorContext,
        retry_config: Optional[RetryConfig] = None,
        *args,
        **kwargs,
    ):
        """Execute a function with retry logic."""
        # Use strategy's config if no override provided
        if retry_config is None:
            strategy_config = getattr(self.retry_strategy, "config", None)
            retry_config = (
                strategy_config
                if isinstance(strategy_config, RetryConfig)
                else RetryConfig()
            )
        operation_id = str(uuid.uuid4())

        self.active_recoveries[operation_id] = {
            "function": func.__name__,
            "context": context,
            "started_at": datetime.now(timezone.utc),
            "attempts": 0,
        }

        last_exception = None

        try:
            for attempt in range(retry_config.max_attempts):
                try:
                    self.active_recoveries[operation_id]["attempts"] = attempt + 1
                    result = await func(*args, **kwargs)

                    # Success - record and return
                    self.retry_strategy.record_attempt(True)
                    return result

                except Exception as e:
                    last_exception = e
                    # Determine retry reason
                    retry_reason = self._determine_retry_reason(e, context)

                    # Record failed attempt
                    self.retry_strategy.record_attempt(False, retry_reason)

                    # Check if we should retry
                    if not await self.retry_strategy.should_retry(
                        attempt, e, retry_reason
                    ):
                        break

                    # Try service-specific recovery first
                    if self.service_handler:
                        try:
                            handled = await self.service_handler.handle_error(
                                e, context
                            )
                            if handled:
                                continue
                        except Exception:
                            # If service handler fails, continue with normal retry logic
                            pass

                    # If not the last attempt, wait and retry
                    if attempt < retry_config.max_attempts - 1:
                        delay = await self.retry_strategy.get_delay(
                            attempt, retry_reason
                        )
                        await asyncio.sleep(delay)

            # If we get here, all attempts failed
            if last_exception:
                try:
                    await self.error_reporter.report_error(
                        last_exception, ErrorSeverity.HIGH, context
                    )
                except Exception:
                    # If error reporting fails, still propagate the original exception
                    pass
                raise last_exception

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
