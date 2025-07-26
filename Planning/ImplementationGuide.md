# YTArchive Implementation Guide

This document consolidates all technical implementation details for the YTArchive project.

## Table of Contents
1. [Data Persistence Strategy](#data-persistence-strategy)
2. [Common Data Models](#common-data-models)
3. [Service Communication](#service-communication)
4. [Configuration Management](#configuration-management)
5. [Error Handling](#error-handling)
6. [Logging & Monitoring](#logging--monitoring)
7. [Service Lifecycle](#service-lifecycle)
8. [API Standards](#api-standards)
9. [File Handling Conventions](#file-handling-conventions)
10. [Validation Rules](#validation-rules)
11. [Testing Strategy](#testing-strategy)

## Data Persistence Strategy

### Storage Organization
- **Base Directory**: `~/.ytarchive/data/` (configurable via config.toml)
- **Structure**:
  ```
  ~/.ytarchive/data/
  ├── jobs/           # Job definitions and state
  ├── registry/       # Service registry data
  ├── work_plans/     # Failed/unavailable video plans
  ├── tmp/            # Temporary files
  └── logs/           # Service logs
  ```

### Output Organization
- **Base Path**: `~/YTArchive` (configurable)
- **Structure**:
  ```
  ~/YTArchive/
  ├── metadata/
  │   ├── videos/
  │   │   └── {video_id}.json
  │   └── playlists/
  │       └── {playlist_id}.json
  └── videos/
      └── {video_id}/
          ├── {video_id}.mp4
          ├── {video_id}_thumb.jpg
          ├── {video_id}_metadata.json
          └── captions/
              └── {video_id}_en.vtt
  ```

### Data Retention
- Completed jobs: 30 days
- Failed jobs: 90 days
- Cancelled jobs: 7 days
- Work plans: Manual cleanup only
- Logs: 30 days with daily rotation

## Common Data Models

All services should import these from `services/common/models.py`:

### Base Models
```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class ErrorCode(str, Enum):
    API_QUOTA_EXCEEDED = "E001"
    VIDEO_UNAVAILABLE = "E002"
    NETWORK_TIMEOUT = "E003"
    STORAGE_FULL = "E004"
    INVALID_CREDENTIALS = "E005"
    SERVICE_UNAVAILABLE = "E006"
    INVALID_REQUEST = "E007"
    INTERNAL_ERROR = "E999"

class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    details: Optional[Dict[str, Any]] = None

class ServiceRequest(BaseModel):
    trace_id: str
    timestamp: datetime
    data: Dict[str, Any]

class ServiceResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[ErrorDetail] = None
    trace_id: str

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"

class HealthCheck(BaseModel):
    service: str
    status: HealthStatus
    version: str
    uptime_seconds: int
    checks: Dict[str, bool] = Field(default_factory=lambda: {
        "http_responsive": True,
        "dependencies_available": True,
        "no_critical_errors": True,
        "disk_space_available": True
    })
    metrics: Optional[Dict[str, Any]] = None
```

### Job Models
```python
class JobType(str, Enum):
    VIDEO_DOWNLOAD = "video_download"
    PLAYLIST_DOWNLOAD = "playlist_download"
    METADATA_ONLY = "metadata_only"

class JobStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

class JobOptions(BaseModel):
    output_dir: str = "~/YTArchive"
    quality: str = "1080p"
    include_metadata: bool = True
    include_captions: bool = True
    caption_languages: List[str] = Field(default_factory=lambda: ["en"])
    skip_existing: bool = True
    api_key: Optional[str] = None

class JobResult(BaseModel):
    video_id: str
    status: str  # "success", "failed", "skipped"
    message: Optional[str] = None
    metadata_saved: bool = False
    video_downloaded: bool = False
    file_size: Optional[int] = None
    duration_seconds: Optional[float] = None
    error_code: Optional[ErrorCode] = None

class Progress(BaseModel):
    current: int
    total: int
    percentage: float
    message: str
    speed_bps: Optional[float] = None  # bytes per second
    eta_seconds: Optional[int] = None
```

### Work Plan Models
```python
class UnavailableVideo(BaseModel):
    video_id: str
    title: Optional[str] = None
    reason: str  # "private", "deleted", "region_blocked", "age_restricted"
    detected_at: datetime
    playlist_id: Optional[str] = None
    last_available: Optional[datetime] = None

class FailedDownload(BaseModel):
    video_id: str
    title: str
    attempts: int
    last_attempt: datetime
    errors: List[Dict[str, Any]]
    file_size: Optional[int] = None
    retry_after: Optional[datetime] = None
```

## Service Communication

### HTTP Configuration
```python
TIMEOUTS = {
    "connect": 5.0,
    "read": 30.0,
    "write": 30.0,
    "pool": 30.0
}

DOWNLOAD_TIMEOUT = 3600  # 1 hour for downloads
```

### Retry Policy
```python
RETRY_CONFIG = {
    "max_attempts": 3,
    "backoff_factor": 2,
    "max_backoff": 30,
    "retry_on": [502, 503, 504, 429]
}
```

### Circuit Breaker
- Threshold: 5 consecutive failures
- Timeout: 60 seconds before retry
- Half-Open: Allow 1 request to test recovery

### Request/Response Format
All inter-service communication uses these formats:

**Request**:
```json
{
  "trace_id": "uuid",
  "timestamp": "2024-01-01T00:00:00Z",
  "data": { ... }
}
```

**Success Response**:
```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "trace_id": "uuid"
}
```

**Error Response**:
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "E001",
    "message": "Human readable error",
    "details": { ... }
  },
  "trace_id": "uuid"
}
```

## Configuration Management

### Configuration File Structure
Location: `config.toml` in project root

```toml
[general]
log_level = "INFO"
api_version = "v1"

[storage]
base_data_dir = "~/.ytarchive/data"
jobs_dir = "{base_data_dir}/jobs"
registry_dir = "{base_data_dir}/registry"
work_plans_dir = "{base_data_dir}/work_plans"
tmp_dir = "{base_data_dir}/tmp"
logs_dir = "{base_data_dir}/logs"

# Output paths
base_path = "~/YTArchive"
metadata_dir = "{base_path}/metadata"
videos_dir = "{base_path}/videos"

[youtube]
quota_limit = 10000
quota_reserve = 1000

[services.jobs]
host = "localhost"
port = 8000

[services.metadata]
host = "localhost"
port = 8001

[services.download]
host = "localhost"
port = 8002

[services.storage]
host = "localhost"
port = 8003

[services.logging]
host = "localhost"
port = 8004
```

### Environment Variables
- `YOUTUBE_API_KEY`: Required for YouTube API access

## Error Handling

### Standard Error Codes
Use the `ErrorCode` enum for consistent error reporting:
- E001: API_QUOTA_EXCEEDED
- E002: VIDEO_UNAVAILABLE
- E003: NETWORK_TIMEOUT
- E004: STORAGE_FULL
- E005: INVALID_CREDENTIALS
- E006: SERVICE_UNAVAILABLE
- E007: INVALID_REQUEST
- E999: INTERNAL_ERROR

### Error Response Pattern
```python
def handle_error(error: Exception, trace_id: str) -> ServiceResponse:
    logger.error("error_occurred",
        error_type=type(error).__name__,
        error_message=str(error),
        trace_id=trace_id
    )

    error_code = ErrorCode.INTERNAL_ERROR
    if isinstance(error, QuotaExceeded):
        error_code = ErrorCode.API_QUOTA_EXCEEDED
    # ... other error mappings

    return ServiceResponse(
        success=False,
        error=ErrorDetail(
            code=error_code,
            message=str(error),
            details={"trace_id": trace_id}
        ),
        trace_id=trace_id
    )
```

## Logging & Monitoring

### Structured Logging
```python
import structlog

# Service initialization
logger = structlog.get_logger()
logger = logger.bind(service="service_name", version="0.1.0")

# Standard log events
logger.info("request_received", endpoint=endpoint, method=method, trace_id=trace_id)
logger.info("request_completed", endpoint=endpoint, status_code=status, duration_ms=duration)
logger.error("error_name", error_code=code, error_message=str(error), **context)
```

### Progress Reporting
For long-running operations:
- Update every 5 seconds OR 5% progress (whichever comes first)
- Include speed and ETA when available
- Use the `Progress` model for consistency

### Health Check Implementation
```python
async def health_check() -> HealthCheck:
    uptime = time.time() - SERVICE_START_TIME

    checks = {
        "http_responsive": True,
        "dependencies_available": await check_dependencies(),
        "no_critical_errors": not has_critical_errors(),
        "disk_space_available": check_disk_space() > MIN_DISK_SPACE
    }

    return HealthCheck(
        service=SERVICE_NAME,
        status=HealthStatus.HEALTHY if all(checks.values()) else HealthStatus.UNHEALTHY,
        version=SERVICE_VERSION,
        uptime_seconds=int(uptime),
        checks=checks,
        metrics=get_service_metrics()
    )
```

## Service Lifecycle

### Startup Process
```python
class ServiceBase:
    async def startup(self):
        # 1. Load configuration
        self.config = load_config()

        # 2. Validate environment
        self.validate_environment()

        # 3. Initialize resources
        await self.initialize_resources()

        # 4. Register with Jobs service (except Jobs service itself)
        if self.service_name != "jobs":
            await self.register_with_jobs()

        # 5. Start health check endpoint
        self.start_health_endpoint()

        # 6. Log startup complete
        self.logger.info("service_started",
            service=self.service_name,
            port=self.config.port
        )
```

### Graceful Shutdown
```python
import signal
import asyncio

class ServiceBase:
    def __init__(self):
        self.shutdown_event = asyncio.Event()
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        self.logger.info("shutdown_signal_received", signal=signum)
        self.shutdown_event.set()

    async def shutdown(self):
        # 1. Stop accepting new requests
        self.accepting_requests = False

        # 2. Wait for current requests to complete (with timeout)
        await self.wait_for_requests(timeout=30)

        # 3. Clean up resources
        await self.cleanup_resources()

        # 4. Final log
        self.logger.info("service_stopped")
```

## API Standards

### URL Structure
- Base: `http://{host}:{port}/api/v1/`
- Resource naming: Use plural nouns (`/videos`, `/jobs`)
- Actions: Use verbs for non-CRUD operations (`/retry`, `/cancel`)

### Required Endpoints
Every service MUST implement:
```
GET /api/v1/health
```

### HTTP Status Codes
- 200: Success
- 201: Created
- 400: Bad Request
- 404: Not Found
- 429: Too Many Requests (quota exceeded)
- 500: Internal Server Error
- 503: Service Unavailable

## File Handling Conventions

### Video File Naming
```
{video_id}.mp4              # Video file
{video_id}_thumb.jpg        # Thumbnail (maxres priority)
{video_id}_metadata.json    # Video metadata
{video_id}_{lang}.vtt       # Caption files
```

### Thumbnail Priority
1. maxresdefault
2. standard
3. high
4. medium
5. default

### Path Validation
- Must be absolute or start with `~/`
- Must have write permissions
- Check disk space before operations

### Temporary Files
- Location: `{base_data_dir}/tmp/`
- Naming: `{video_id}.part` for partial downloads
- Cleanup: On completion or shutdown

## Validation Rules

### Video ID
```python
VIDEO_ID_PATTERN = r"^[a-zA-Z0-9_-]{11}$"

def validate_video_id(video_id: str) -> bool:
    return bool(re.match(VIDEO_ID_PATTERN, video_id))
```

### Playlist ID
```python
PLAYLIST_ID_PATTERN = r"^(PL|UU|FL|RD|OL)[a-zA-Z0-9_-]{16,41}$"

def validate_playlist_id(playlist_id: str) -> bool:
    return bool(re.match(PLAYLIST_ID_PATTERN, playlist_id))
```

### Storage Path
```python
def validate_storage_path(path: str) -> bool:
    # Expand user home
    expanded_path = os.path.expanduser(path)

    # Check if absolute or home-relative
    if not (os.path.isabs(expanded_path) or path.startswith("~/")):
        return False

    # Check write permissions
    return os.access(os.path.dirname(expanded_path), os.W_OK)
```

## Testing Strategy

### Test Structure
```
tests/
├── unit/
│   ├── test_models.py
│   ├── test_validators.py
│   └── services/
│       ├── test_jobs.py
│       └── test_metadata.py
├── integration/
│   ├── test_service_communication.py
│   └── test_end_to_end.py
└── fixtures/
    ├── sample_metadata.json
    └── mock_responses.py
```

### Testing Tools
- Framework: `pytest`
- Async support: `pytest-asyncio`
- HTTP mocking: `httpx` test client
- Coverage: `pytest-cov` (target: 80%)

### Test Patterns
```python
# Unit test example
async def test_video_id_validation():
    assert validate_video_id("dQw4w9WgXcQ")
    assert not validate_video_id("invalid")

# Integration test example
async def test_metadata_fetch(mock_youtube_api):
    mock_youtube_api.return_value = load_fixture("video_metadata.json")

    response = await client.get("/api/v1/metadata/video/dQw4w9WgXcQ")
    assert response.status_code == 200
    assert response.json()["data"]["video_id"] == "dQw4w9WgXcQ"
```

### Mock Service for Testing
```python
class MockService:
    def __init__(self, port: int):
        self.app = FastAPI()
        self.setup_routes()

    def setup_routes(self):
        @self.app.get("/api/v1/health")
        async def health():
            return {"status": "healthy"}
```

---

## Quick Reference

### Service Ports
- Jobs Service: 8000
- Metadata Service: 8001
- Download Service: 8002
- Storage Service: 8003
- Logging Service: 8004

### Key Patterns
1. All services implement `/api/v1/health`
2. Use structured logging with trace_id
3. Return `ServiceResponse` for all endpoints
4. Handle graceful shutdown
5. Validate all inputs
6. Report progress for long operations
7. Use exponential backoff for retries
