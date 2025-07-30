"""Type definitions and common models for error recovery."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ErrorSeverity(str, Enum):
    """Error severity levels."""

    CRITICAL = "critical"  # System failure, requires immediate attention
    HIGH = "high"  # Feature failure, significant impact
    MEDIUM = "medium"  # Degraded functionality
    LOW = "low"  # Minor issues, warnings
    INFO = "info"  # Informational messages


class RetryReason(str, Enum):
    """Categories of retry reasons."""

    NETWORK_ERROR = "network_error"
    API_QUOTA_EXCEEDED = "api_quota_exceeded"
    TEMPORARY_UNAVAILABLE = "temporary_unavailable"
    RATE_LIMITED = "rate_limited"
    DOWNLOAD_FAILED = "download_failed"
    SERVICE_UNAVAILABLE = "service_unavailable"
    QUALITY_NOT_AVAILABLE = "quality_not_available"
    SERVER_ERROR = "server_error"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class RetryConfig(BaseModel):
    """Configuration for retry strategies."""

    max_attempts: int = Field(
        default=3, gt=0, description="Maximum number of retry attempts"
    )
    base_delay: float = Field(default=1.0, ge=0.0, description="Base delay in seconds")
    max_delay: float = Field(
        default=300.0, gt=0.0, description="Maximum delay in seconds"
    )
    jitter: bool = True
    exponential_base: float = Field(
        default=2.0, gt=1.0, description="Exponential backoff base"
    )

    # Circuit breaker specific
    failure_threshold: int = Field(
        default=5, gt=0, description="Failure threshold for circuit breaker"
    )
    recovery_timeout: float = Field(
        default=60.0, gt=0.0, description="Recovery timeout in seconds"
    )

    @model_validator(mode="after")
    def validate_delay_relationship(self):
        """Validate that max_delay is greater than or equal to base_delay."""
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be greater than or equal to base_delay")
        return self


class ErrorContext(BaseModel):
    """Context information for error reporting."""

    operation_name: str
    attempt_count: int = 1
    operation_context: Dict[str, Any] = {}
    video_id: Optional[str] = None
    url: Optional[str] = None
    service_name: Optional[str] = None
    operation: Optional[str] = None
    job_id: Optional[str] = None
    retry_attempt: Optional[int] = None

    # Additional context
    user_config: Dict[str, Any] = {}
    environment: Dict[str, str] = {}


class ErrorReport(BaseModel):
    """Error report with context and recovery information."""

    id: str
    timestamp: datetime
    severity: ErrorSeverity
    title: str
    message: str
    exception_type: Optional[str] = None
    context: ErrorContext

    # Recovery information
    suggested_actions: List[str] = []
    recovery_possible: bool = True
    retry_recommended: bool = False
