"""Common models shared across all services."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field


class LogLevel(str, Enum):
    """Log levels for the logging service."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class JobType(str, Enum):
    """Types of jobs that can be created."""

    VIDEO_DOWNLOAD = "VIDEO_DOWNLOAD"
    PLAYLIST_DOWNLOAD = "PLAYLIST_DOWNLOAD"
    METADATA_ONLY = "METADATA_ONLY"


class JobStatus(str, Enum):
    """Status of a job."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class DownloadStatus(str, Enum):
    """Status of a download task."""

    DOWNLOADING = "DOWNLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ErrorDetail(BaseModel):
    """Error details for API responses."""

    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ServiceResponse(BaseModel):
    """Standard response format for all services."""

    success: bool
    data: Optional[Any] = None
    error: Optional[ErrorDetail] = None
    trace_id: Optional[str] = None


class HealthCheck(BaseModel):
    """Health check response for services."""

    service: str
    status: str = Field(pattern="^(healthy|unhealthy)$")
    version: str
    uptime_seconds: int
    checks: Dict[str, bool] = Field(default_factory=dict)


class ServiceRequest(BaseModel):
    """Standard request format for inter-service communication."""

    trace_id: str
    timestamp: datetime
    data: Dict[str, Any]


# Error codes used across services
class ErrorCode:
    """Standard error codes."""

    API_QUOTA_EXCEEDED = "E001"
    VIDEO_UNAVAILABLE = "E002"
    NETWORK_TIMEOUT = "E003"
    STORAGE_FULL = "E004"
    INVALID_CREDENTIALS = "E005"
    SERVICE_UNAVAILABLE = "E006"
    INVALID_REQUEST = "E007"
    INTERNAL_ERROR = "E999"


# Job-related models
class JobOptions(BaseModel):
    """Options for job execution."""

    output_dir: str = "~/YTArchive"
    quality: str = "1080p"
    include_metadata: bool = True
    include_captions: bool = True
    caption_languages: List[str] = Field(default_factory=lambda: ["en"])
    skip_existing: bool = True
    api_key: Optional[str] = None  # Can override env var


class JobResult(BaseModel):
    """Result of processing a single video/item."""

    video_id: str
    status: str = Field(pattern="^(success|failed|skipped)$")
    message: Optional[str] = None
    metadata_saved: bool = False
    video_downloaded: bool = False
    file_size: Optional[int] = None
    duration_seconds: Optional[float] = None
    error_code: Optional[str] = None


# Playlist-related models
class PlaylistVideo(BaseModel):
    """Video entry in a playlist."""

    video_id: str
    position: int
    title: str
    duration: Optional[int] = None  # seconds
    is_available: bool = True
    added_at: Optional[datetime] = None


# Work plan models
class UnavailableVideo(BaseModel):
    """Track videos that cannot be downloaded."""

    video_id: str
    title: Optional[str] = None
    reason: str = Field(pattern="^(private|deleted|region_blocked|age_restricted)$")
    detected_at: datetime
    playlist_id: Optional[str] = None
    last_available: Optional[datetime] = None


class FailedDownload(BaseModel):
    """Track failed download attempts."""

    video_id: str
    title: str
    attempts: int
    last_attempt: datetime
    errors: List[Dict[str, Any]]  # Error history
    file_size: Optional[int] = None
    retry_after: Optional[datetime] = None


# Progress tracking
class Progress(BaseModel):
    """Progress information for long-running operations."""

    current: int
    total: int
    percentage: float
    message: str
    speed_bps: Optional[float] = None  # bytes per second
    eta_seconds: Optional[int] = None


# Health check extension
class HealthStatus(BaseModel):
    """Extended health status with detailed checks."""

    healthy: bool
    checks: Dict[str, bool] = Field(
        default_factory=lambda: {
            "http_responsive": True,
            "dependencies_available": True,
            "no_critical_errors": True,
            "disk_space_available": True,
        }
    )
    message: Optional[str] = None
    last_error: Optional[str] = None


class LogType(str, Enum):
    """Enum for log types, corresponding to subdirectories in the logs folder."""

    RUNTIME = "runtime"
    FAILED_DOWNLOADS = "failed_downloads"
    ERROR_REPORTS = "error_reports"


class LogMessage(BaseModel):
    """A structured log message that services can send to the LoggingService."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service: str
    level: LogLevel
    message: str
    log_type: LogType = LogType.RUNTIME
    data: Optional[Dict[str, Any]] = None


class ServiceRegistration(BaseModel):
    """Model for service registration in the registry."""

    service_name: str
    host: str
    port: int
    health_endpoint: str = "/health"
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class RegisteredService(BaseModel):
    """Model representing a registered service with its status."""

    service_name: str
    host: str
    port: int
    health_endpoint: str
    description: Optional[str] = None
    tags: List[str]
    registered_at: datetime
    last_health_check: Optional[datetime] = None
    is_healthy: bool = True
