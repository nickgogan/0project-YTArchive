"""
Error Recovery Library for YTArchive Microservices

This library provides shared error recovery mechanisms including:
- Retry strategies (exponential backoff, circuit breaker, adaptive)
- Error reporting and diagnostics
- Contracts for service-specific error handling

Follows a hybrid approach: shared library + service-specific enhancements.
"""

from .base import ErrorRecoveryManager
from .contracts import RetryStrategy, ErrorReporter, ServiceErrorHandler
from .types import RetryConfig, ErrorSeverity, ErrorContext

__version__ = "1.0.0"
__all__ = [
    "ErrorRecoveryManager",
    "RetryStrategy",
    "ErrorReporter",
    "ServiceErrorHandler",
    "RetryConfig",
    "ErrorSeverity",
    "ErrorContext",
]
