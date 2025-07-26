# Service Specification Generation Guide

This document consolidates all necessary decisions and patterns for creating service specifications in the YTArchive project.

## 1. Service Foundation

### Base Configuration
- **Port Assignment**: See ArchitectureDecisions.md for assigned ports (8000-8004)
- **Host**: localhost (configurable via config.toml)
- **API Version**: `/api/v1/`
- **Communication**: HTTP/REST with JSON payloads

### Required Endpoints
Every service MUST implement:
```
GET /api/v1/health
```

### Standard Response Format
```json
{
  "success": true/false,
  "data": { ... },
  "error": {
    "code": "E001",
    "message": "Human readable error",
    "details": { ... }
  },
  "trace_id": "uuid"
}
```

### Standard Request Format (Inter-service)
```json
{
  "trace_id": "uuid",
  "timestamp": "2024-01-01T00:00:00Z",
  "data": { ... }
}
```

## 2. Data Models

### Import Common Models
From `services/common/models.py`:
- ErrorDetail, ServiceResponse, ServiceRequest
- HealthCheck, HealthStatus
- JobType, JobStatus, JobOptions, JobResult
- Progress
- Error codes (ErrorCode class)

### Service-Specific Models
Define using Pydantic BaseModel with:
- Type hints for all fields
- Optional fields marked with Optional[]
- Default values where appropriate
- Field validation using Field()
- Docstrings for complex models

## 3. Service Lifecycle

### Startup Process (Required)
1. Load configuration from `config.toml`
2. Validate environment variables/API keys
3. Initialize service-specific resources
4. Register with Jobs service (except Jobs service itself)
5. Start health check endpoint
6. Begin accepting requests

### Graceful Shutdown (Required)
```python
import signal
import asyncio

class ServiceName:
    def __init__(self):
        self.shutdown_event = asyncio.Event()
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        self.logger.info("Received shutdown signal", signal=signum)
        self.shutdown_event.set()
```

## 4. Monitoring & Observability

### Structured Logging (Required)
```python
import structlog

logger = structlog.get_logger()
logger = logger.bind(service="service_name", version="0.1.0")
```

### Standard Log Events
- Request received: `logger.info("request_received", endpoint=endpoint, method=method)`
- Request completed: `logger.info("request_completed", endpoint=endpoint, status_code=status, duration_ms=duration)`
- Errors: `logger.error("error_name", error_code=code, error_message=str(error), **context)`

### Health Check Response Format
```json
{
    "service": "service_name",
    "status": "healthy|unhealthy",
    "version": "0.1.0",
    "uptime_seconds": 3600,
    "checks": {
        "http_responsive": true,
        "dependencies_available": true,
        "no_critical_errors": true,
        "disk_space_available": true
    },
    "metrics": {
        // Service-specific metrics
    }
}
```

## 5. Error Handling

### HTTP Timeouts
```python
TIMEOUTS = {
    "connect": 5.0,
    "read": 30.0,
    "write": 30.0,
    "pool": 30.0
}
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

### Error Codes
Use standard codes from ErrorCode class:
- E001: API_QUOTA_EXCEEDED
- E002: VIDEO_UNAVAILABLE
- E003: NETWORK_TIMEOUT
- E004: STORAGE_FULL
- E005: INVALID_CREDENTIALS
- E006: SERVICE_UNAVAILABLE
- E007: INVALID_REQUEST
- E999: INTERNAL_ERROR

## 6. Storage & Configuration

### Configuration Access
```python
# Load from config.toml
config.services.{service_name}.{setting}
```

### File Storage Paths
```python
# From config.toml [storage] section
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
```

## 7. Inter-Service Communication

### Service Registry
- Register on startup: `POST /api/v1/registry/register`
- Discover services: `GET /api/v1/registry/services`

### Jobs Service Integration
All services (except Jobs) must:
1. Register with Jobs service on startup
2. Report progress for long-running operations
3. Update job status on completion/failure

### Logging Service Integration
Send structured logs to Logging service:
```
POST /api/v1/logs
```

## 8. Service-Specific Patterns

### For Services Handling YouTube API
- Check quota before API calls
- Track quota usage
- Implement exponential backoff
- Use API key from environment: `YOUTUBE_API_KEY`

### For Services Managing Files
- Validate paths (must be absolute or start with ~/)
- Check disk space before operations
- Clean up temporary files on completion/failure
- Use consistent naming patterns

### For Long-Running Operations
- Report progress every 5 seconds or 5% completion
- Support cancellation
- Implement resume capability where applicable

## 9. Validation Rules

### Video ID
```python
VIDEO_ID_PATTERN = r"^[a-zA-Z0-9_-]{11}$"
```

### Playlist ID
```python
PLAYLIST_ID_PATTERN = r"^(PL|UU|FL|RD|OL)[a-zA-Z0-9_-]{16,41}$"
```

## 10. Documentation Requirements

Each service specification MUST include:
1. **Overview**: Purpose and responsibilities
2. **API Endpoints**: Complete request/response documentation
3. **Data Models**: All models used by the service
4. **Dependencies**: Other services this service depends on
5. **Configuration**: Required settings and environment variables
6. **Error Scenarios**: Common errors and how they're handled
7. **Metrics**: What the service tracks and reports

## 11. Testing Considerations

Include in specification:
- Example requests/responses for each endpoint
- Error response examples
- Health check behavior under various conditions
- Performance expectations (response times, throughput)

---

## Quick Checklist for New Service Specification

- [ ] Overview and responsibilities defined
- [ ] All endpoints documented with request/response formats
- [ ] Data models defined (importing common + service-specific)
- [ ] Health check endpoint included
- [ ] Startup process documented
- [ ] Graceful shutdown handling described
- [ ] Structured logging patterns shown
- [ ] Error codes and handling specified
- [ ] Inter-service communication documented
- [ ] Configuration requirements listed
- [ ] File paths and storage patterns defined (if applicable)
- [ ] Validation rules included (if applicable)
- [ ] Metrics and monitoring approach described
