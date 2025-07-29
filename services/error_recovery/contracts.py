"""Contracts and interfaces for error recovery components."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .types import ErrorContext, ErrorReport, ErrorSeverity, RetryReason


class RetryStrategy(ABC):
    """Abstract base class for retry strategies."""

    @abstractmethod
    async def should_retry(
        self, attempt: int, exception: Exception, reason: RetryReason
    ) -> bool:
        """Determine if retry should be attempted."""
        pass

    @abstractmethod
    async def get_delay(self, attempt: int, reason: RetryReason) -> float:
        """Calculate delay for the given attempt."""
        pass

    @abstractmethod
    def record_attempt(self, success: bool, reason: Optional[RetryReason] = None):
        """Record metrics for an attempt."""
        pass


class ErrorReporter(ABC):
    """Abstract base class for error reporting."""

    @abstractmethod
    async def report_error(
        self, exception: Exception, severity: ErrorSeverity, context: ErrorContext
    ) -> ErrorReport:
        """Report an error with full context."""
        pass

    @abstractmethod
    async def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get error summary for the last N hours."""
        pass


class ServiceErrorHandler(ABC):
    """Interface for service-specific error handling."""

    @abstractmethod
    async def handle_error(self, exception: Exception, context: ErrorContext) -> bool:
        """
        Handle a service-specific error.

        Returns:
            bool: True if error was handled/recovered, False otherwise
        """
        pass

    @abstractmethod
    def get_recovery_suggestions(self, exception: Exception) -> List[str]:
        """Get service-specific recovery suggestions."""
        pass
