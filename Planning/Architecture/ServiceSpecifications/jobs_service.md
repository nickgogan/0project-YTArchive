# Jobs Service Specification

## Overview
The Jobs Service is the central coordinator for all YTArchive operations. It manages job creation, execution, and tracking, maintains the service registry, and coordinates work between other services.

## Service Configuration
- **Port**: 8000
- **Host**: localhost (configurable)
- **Dependencies**: None (other services depend on Jobs)

## API Endpoints

### Job Management

#### Create Job
```
POST /api/v1/jobs
```

**Request Body**:
```json
{
  "type": "video_download|playlist_download|metadata_only",
  "video_ids": ["video_id1", "video_id2"],
  "playlist_id": "playlist_id",  // optional
  "options": {
    "output_dir": "~/YTArchive",
    "quality": "1080p",
    "include_metadata": true,
    "include_captions": true,
    "caption_languages": ["en"],
    "skip_existing": true
  }
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "job_id": "uuid",
    "status": "created",
    "created_at": "2024-01-01T00:00:00Z"
  },
  "trace_id": "uuid"
}
```

#### Get Job Status
```
GET /api/v1/jobs/{job_id}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "type": "video_download",
    "status": "running",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:05:00Z",
    "video_ids": ["video_id"],
    "options": {...},
    "progress": {
      "current": 50,
      "total": 100,
      "percentage": 50.0,
      "message": "Downloading video..."
    },
    "results": []
  },
  "trace_id": "uuid"
}
```

#### List Jobs
```
GET /api/v1/jobs?status=running&limit=10&offset=0
```

**Query Parameters**:
- `status`: Filter by job status
- `limit`: Number of results (default: 50)
- `offset`: Pagination offset

**Response**:
```json
{
  "success": true,
  "data": {
    "jobs": [...],
    "total": 100,
    "limit": 10,
    "offset": 0
  },
  "trace_id": "uuid"
}
```

#### Retry Failed Job
```
PUT /api/v1/jobs/{job_id}/retry
```

**Response**:
```json
{
  "success": true,
  "data": {
    "job_id": "uuid",
    "status": "retrying",
    "retry_count": 1
  },
  "trace_id": "uuid"
}
```

#### Cancel Job
```
PUT /api/v1/jobs/{job_id}/cancel
```

### Service Registry

#### Register Service
```
POST /api/v1/registry/register
```

**Request Body**:
```json
{
  "service_name": "metadata",
  "url": "http://localhost:8001",
  "health_endpoint": "/api/v1/health",
  "version": "0.1.0"
}
```

#### List Services
```
GET /api/v1/registry/services
```

**Response**:
```json
{
  "success": true,
  "data": {
    "services": [
      {
        "service_name": "metadata",
        "url": "http://localhost:8001",
        "health_endpoint": "/api/v1/health",
        "last_health_check": "2024-01-01T00:00:00Z",
        "is_healthy": true,
        "version": "0.1.0"
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
from pydantic import BaseModel
from common.models import JobType, JobStatus, JobOptions, JobResult, Progress

class Job(BaseModel):
    id: str
    type: JobType
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    video_ids: List[str]
    playlist_id: Optional[str] = None
    options: JobOptions
    results: List[JobResult] = []
    progress: Optional[Progress] = None
    error: Optional[str] = None
    retry_count: int = 0
    state_history: List[Dict[str, Any]] = []

class ServiceRegistration(BaseModel):
    service_name: str
    url: str
    port: int
    health_endpoint: str = "/api/v1/health"
    version: str
    registered_at: datetime
    last_health_check: Optional[datetime] = None
    is_healthy: bool = True
    consecutive_failures: int = 0

class CreateJobRequest(BaseModel):
    type: JobType
    video_ids: Optional[List[str]] = None
    playlist_id: Optional[str] = None
    options: Optional[JobOptions] = None

class JobListResponse(BaseModel):
    jobs: List[Job]
    total: int
    limit: int
    offset: int
```

## Internal Operations

### Job State Machine
```
CREATED -> QUEUED -> RUNNING -> [COMPLETED|FAILED]
                        |
                        v
                    RETRYING -> RUNNING
                        |
                        v
                    CANCELLED
```

### Service Health Monitoring
- Check interval: Every 30 seconds
- Failure threshold: 3 consecutive failures
- Recovery: Mark healthy after 1 successful check

### Job Execution Flow
1. Validate job request
2. Create job with CREATED status
3. Queue job (status: QUEUED)
4. Execute job steps:
   - For video downloads:
     a. Call Metadata Service
     b. Check Storage Service for existing files
     c. Call Download Service if needed
     d. Update Storage Service with results
5. Update job status and results
6. Handle failures with retry logic

## Configuration

### Environment Variables
None required (Jobs service is self-contained)

### Config File Settings
```toml
[services.jobs]
host = "localhost"
port = 8000
health_check_interval = 30  # seconds
max_retry_attempts = 3
job_retention_days = 30
failed_job_retention_days = 90
```

## Error Scenarios

### Common Errors
- `E006`: Service unavailable (dependency service down)
- `E007`: Invalid request (missing required fields)
- `E999`: Internal error

### Error Handling
- Automatic retries for transient failures
- Exponential backoff between retries
- Failed jobs tracked for manual intervention

## Metrics

The Jobs service tracks:
- Total jobs created
- Jobs by status
- Average job duration
- Service health status
- Registry size

## Example Usage

### Create a Video Download Job
```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "type": "video_download",
    "video_ids": ["dQw4w9WgXcQ"],
    "options": {
      "quality": "1080p",
      "include_captions": true
    }
  }'
```

### Check Job Progress
```bash
curl http://localhost:8000/api/v1/jobs/{job_id}
```

### Register a Service
```bash
curl -X POST http://localhost:8000/api/v1/registry/register \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "metadata",
    "url": "http://localhost:8001",
    "version": "0.1.0"
  }'
```
