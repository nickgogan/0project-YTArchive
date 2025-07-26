# Logging Service Specification

## Overview
The Logging Service provides centralized log collection, storage, and retrieval for all YTArchive services. It handles log rotation, retention, and provides query capabilities for debugging and monitoring.

## Service Configuration
- **Port**: 8004
- **Host**: localhost (configurable)
- **Dependencies**: File system access

## API Endpoints

### Log Management

#### Submit Log Entry
```
POST /api/v1/logs
```

**Request Body**:
```json
{
  "service": "metadata",
  "level": "INFO",
  "message": "Video metadata fetched successfully",
  "timestamp": "2024-01-01T00:00:00Z",
  "context": {
    "video_id": "dQw4w9WgXcQ",
    "duration_ms": 245,
    "trace_id": "uuid"
  }
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "log_id": "uuid",
    "stored": true
  },
  "trace_id": "uuid"
}
```

#### Query Logs
```
GET /api/v1/logs?service=metadata&level=ERROR&from=2024-01-01T00:00:00Z&to=2024-01-02T00:00:00Z&limit=100
```

**Query Parameters**:
- `service`: Filter by service name
- `level`: Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `from`: Start timestamp (ISO 8601)
- `to`: End timestamp (ISO 8601)
- `trace_id`: Filter by trace ID
- `search`: Text search in message
- `limit`: Number of results (default: 100, max: 1000)
- `offset`: Pagination offset

**Response**:
```json
{
  "success": true,
  "data": {
    "logs": [
      {
        "log_id": "uuid",
        "timestamp": "2024-01-01T00:00:00Z",
        "service": "metadata",
        "level": "ERROR",
        "message": "API quota exceeded",
        "context": {
          "error_code": "E001",
          "quota_remaining": 0,
          "trace_id": "uuid"
        }
      }
    ],
    "total": 250,
    "limit": 100,
    "offset": 0
  },
  "trace_id": "uuid"
}
```

#### Get Service Logs
```
GET /api/v1/logs/services/{service_name}?hours=24
```

**Query Parameters**:
- `hours`: Hours of logs to retrieve (default: 24, max: 168)
- `level`: Filter by log level

**Response**:
```json
{
  "success": true,
  "data": {
    "service": "metadata",
    "logs": [...],
    "summary": {
      "total_logs": 1500,
      "by_level": {
        "DEBUG": 100,
        "INFO": 1200,
        "WARNING": 150,
        "ERROR": 45,
        "CRITICAL": 5
      },
      "time_range": {
        "from": "2024-01-01T00:00:00Z",
        "to": "2024-01-02T00:00:00Z"
      }
    }
  },
  "trace_id": "uuid"
}
```

### Metrics

#### Get Metrics
```
GET /api/v1/metrics?service=all&metric_type=system
```

**Query Parameters**:
- `service`: Service name or "all"
- `metric_type`: "system", "application", or "all"

**Response**:
```json
{
  "success": true,
  "data": {
    "metrics": [
      {
        "name": "api_requests_total",
        "value": 15000,
        "tags": {
          "service": "metadata",
          "endpoint": "/api/v1/metadata/video"
        },
        "timestamp": "2024-01-01T00:00:00Z"
      },
      {
        "name": "download_speed_mbps",
        "value": 8.5,
        "tags": {
          "service": "download",
          "video_id": "dQw4w9WgXcQ"
        },
        "timestamp": "2024-01-01T00:00:00Z"
      }
    ]
  },
  "trace_id": "uuid"
}
```

### Health Check
```
GET /api/v1/health
```

## Service-Specific Models

```python
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class LogEntry(BaseModel):
    service: str
    level: LogLevel
    message: str
    timestamp: datetime
    context: Dict[str, Any] = {}
    trace_id: Optional[str] = None

class StoredLogEntry(LogEntry):
    log_id: str
    stored_at: datetime

class LogQuery(BaseModel):
    service: Optional[str] = None
    level: Optional[LogLevel] = None
    from_timestamp: Optional[datetime] = None
    to_timestamp: Optional[datetime] = None
    trace_id: Optional[str] = None
    search: Optional[str] = None
    limit: int = Field(default=100, le=1000)
    offset: int = Field(default=0, ge=0)

class LogQueryResult(BaseModel):
    logs: List[StoredLogEntry]
    total: int
    limit: int
    offset: int

class LogSummary(BaseModel):
    total_logs: int
    by_level: Dict[LogLevel, int]
    time_range: Dict[str, datetime]
    error_rate: float
    warning_rate: float

class Metric(BaseModel):
    name: str
    value: float
    tags: Dict[str, str] = {}
    timestamp: datetime
    type: str = "gauge"  # "gauge", "counter", "histogram"

class MetricQuery(BaseModel):
    service: str = "all"
    metric_type: str = "all"  # "system", "application", "all"
    from_timestamp: Optional[datetime] = None
    to_timestamp: Optional[datetime] = None
```

## Log Storage

### File Organization
```
~/.ytarchive/data/logs/
├── raw/
│   ├── 2024/
│   │   ├── 01/
│   │   │   ├── 01/
│   │   │   │   ├── metadata_20240101.log
│   │   │   │   ├── download_20240101.log
│   │   │   │   └── jobs_20240101.log
│   │   │   └── 02/
│   │   │       └── ...
│   │   └── ...
│   └── ...
├── aggregated/
│   ├── daily/
│   │   └── 20240101_summary.json
│   └── weekly/
│       └── 2024_W01_summary.json
└── metrics/
    └── 2024/
        └── 01/
            └── metrics_20240101.json
```

### Log Format
```json
{
  "timestamp": "2024-01-01T00:00:00.123Z",
  "service": "metadata",
  "level": "INFO",
  "message": "Video metadata fetched",
  "context": {
    "video_id": "dQw4w9WgXcQ",
    "duration_ms": 245,
    "trace_id": "uuid"
  },
  "log_id": "uuid"
}
```

### Rotation Policy
- Daily rotation at midnight UTC
- Compress logs older than 7 days
- Archive logs older than 30 days
- Delete logs older than 90 days (configurable)

## Log Processing

### Real-time Processing
1. Receive log entry via API
2. Validate structure and fields
3. Enrich with metadata (log_id, stored_at)
4. Write to current log file
5. Update indexes for fast querying

### Batch Processing
1. Aggregate logs hourly
2. Generate daily summaries
3. Calculate metrics and statistics
4. Clean up old logs based on retention

### Indexing Strategy
- Index by service, level, timestamp
- Full-text index on message field
- Separate index for trace_id lookup
- Maintain recent logs in memory cache

## Query Optimization

### Query Patterns
1. **Time-based**: Use timestamp indexes
2. **Service-specific**: Pre-filtered log files
3. **Error tracking**: Level-based indexes
4. **Trace lookup**: Dedicated trace_id index

### Performance Considerations
- Cache recent queries (5-minute TTL)
- Limit query time range to 7 days
- Use pagination for large results
- Background indexing for new logs

## Configuration

### Environment Variables
None required

### Config File Settings
```toml
[services.logging]
host = "localhost"
port = 8004
max_log_size_mb = 100
rotation_interval = "daily"
compression_enabled = true
retention_days = 90

[logging]
base_dir = "~/.ytarchive/data/logs"
index_recent_hours = 24  # Keep in memory
cache_ttl_seconds = 300
max_query_days = 7
enable_metrics = true
```

## Error Scenarios

### Common Errors
- `E004`: Storage full
- `E007`: Invalid request (malformed log entry)
- `E999`: Internal error (file system issues)

### Error Handling
- Storage full: Rotate logs early
- Invalid logs: Reject with clear error
- Query timeout: Return partial results
- Corruption: Skip corrupted entries

## Metrics Collection

The Logging service collects:
- Log volume by service and level
- Error rates per service
- Average response times
- Storage usage
- Query performance
- Most common error types

## Integration Guidelines

### For Service Developers
```python
import httpx
import structlog

class LoggingClient:
    def __init__(self, service_name: str, logging_url: str):
        self.service_name = service_name
        self.logging_url = logging_url
        self.client = httpx.AsyncClient()

    async def log(self, level: str, message: str, **context):
        await self.client.post(
            f"{self.logging_url}/api/v1/logs",
            json={
                "service": self.service_name,
                "level": level,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "context": context
            }
        )
```

### Structured Logging Pattern
```python
logger = structlog.get_logger()
logger = logger.bind(service="my_service")

# Use structured logging
logger.info("operation_completed",
    duration_ms=150,
    items_processed=25,
    trace_id=trace_id
)
```

## Example Usage

### Submit a Log Entry
```bash
curl -X POST http://localhost:8004/api/v1/logs \
  -H "Content-Type: application/json" \
  -d '{
    "service": "metadata",
    "level": "ERROR",
    "message": "API quota exceeded",
    "context": {
      "error_code": "E001",
      "video_id": "dQw4w9WgXcQ"
    }
  }'
```

### Query Recent Errors
```bash
curl "http://localhost:8004/api/v1/logs?level=ERROR&hours=24"
```

### Get Service Summary
```bash
curl "http://localhost:8004/api/v1/logs/services/metadata?hours=24"
```

### Retrieve Metrics
```bash
curl "http://localhost:8004/api/v1/metrics?service=all"
```
