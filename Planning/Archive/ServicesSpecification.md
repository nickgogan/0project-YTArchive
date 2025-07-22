# YTArchive Service Specification

## Service Overview

### 1. Jobs Service (Port: 8000)
**Primary Responsibilities:**
- Central coordination of all operations
- Job queue management
- Service registry and health monitoring
- Work plan generation

**API Endpoints:**
```
POST   /api/v1/jobs                    # Create a new job
GET    /api/v1/jobs/{job_id}          # Get job status
GET    /api/v1/jobs                    # List all jobs
PUT    /api/v1/jobs/{job_id}/retry    # Retry a failed job

POST   /api/v1/registry/register       # Register a service
GET    /api/v1/registry/services       # List all services
GET    /api/v1/health                  # Health check
```

**Data Models:**
```python
class Job:
    id: str
    type: JobType  # VIDEO_DOWNLOAD, PLAYLIST_DOWNLOAD, METADATA_ONLY
    status: JobStatus  # PENDING, RUNNING, COMPLETED, FAILED
    created_at: datetime
    updated_at: datetime
    video_ids: List[str]
    playlist_id: Optional[str]
    options: JobOptions
    results: List[JobResult]
    error: Optional[str]

class ServiceRegistry:
    service_name: str
    url: str
    port: int
    health_endpoint: str
    last_health_check: datetime
    is_healthy: bool
```

### 2. Metadata Service (Port: 8001)
**Primary Responsibilities:**
- Fetch video metadata from YouTube API
- Fetch playlist information
- Manage API quota usage
- Cache metadata to avoid duplicate API calls

**API Endpoints:**
```
GET    /api/v1/metadata/video/{video_id}       # Get video metadata
GET    /api/v1/metadata/playlist/{playlist_id} # Get playlist metadata
GET    /api/v1/metadata/quota                  # Get current quota usage
POST   /api/v1/metadata/batch                  # Batch fetch metadata
GET    /api/v1/health                          # Health check
```

**Data Models:**
```python
class VideoMetadata:
    video_id: str
    title: str
    description: str
    duration: int  # seconds
    upload_date: datetime
    channel_id: str
    channel_title: str
    thumbnail_urls: Dict[str, str]  # quality -> url
    available_captions: List[str]   # language codes
    view_count: Optional[int]
    like_count: Optional[int]
    fetched_at: datetime

class PlaylistMetadata:
    playlist_id: str
    title: str
    description: str
    channel_id: str
    channel_title: str
    video_count: int
    videos: List[PlaylistVideo]
    fetched_at: datetime
```

### 3. Download Service (Port: 8002)
**Primary Responsibilities:**
- Download videos using yt-dlp
- Handle different quality options
- Progress tracking
- Resume partial downloads

**API Endpoints:**
```
POST   /api/v1/download/video          # Start video download
GET    /api/v1/download/progress/{task_id}  # Get download progress
POST   /api/v1/download/cancel/{task_id}    # Cancel download
GET    /api/v1/download/formats/{video_id}  # Get available formats
GET    /api/v1/health                  # Health check
```

**Data Models:**
```python
class DownloadRequest:
    video_id: str
    quality: str  # "1080p", "720p", etc.
    output_path: str
    include_captions: bool
    caption_languages: List[str]

class DownloadProgress:
    task_id: str
    video_id: str
    status: DownloadStatus  # DOWNLOADING, COMPLETED, FAILED, CANCELLED
    progress_percent: float
    downloaded_bytes: int
    total_bytes: int
    speed: float  # bytes/sec
    eta: Optional[int]  # seconds
    error: Optional[str]
```

### 4. Storage Service (Port: 8003)
**Primary Responsibilities:**
- Manage file system organization
- Store metadata and videos
- Check for existing files
- Generate work plans

**API Endpoints:**
```
POST   /api/v1/storage/save/metadata   # Save metadata to disk
POST   /api/v1/storage/save/video      # Save video file info
GET    /api/v1/storage/exists/{video_id}  # Check if video exists
GET    /api/v1/storage/metadata/{video_id}  # Get stored metadata
POST   /api/v1/storage/work-plan       # Generate work plan
GET    /api/v1/storage/stats           # Get storage statistics
GET    /api/v1/health                  # Health check
```

**Data Models:**
```python
class StorageLocation:
    video_id: str
    video_path: Optional[str]
    metadata_path: str
    thumbnail_path: Optional[str]
    captions_dir: Optional[str]
    size_bytes: int
    stored_at: datetime

class WorkPlan:
    id: str
    created_at: datetime
    unavailable_videos: List[UnavailableVideo]
    failed_downloads: List[FailedDownload]
    total_videos: int
    successful_videos: int
```

### 5. Logging Service (Port: 8004)
**Primary Responsibilities:**
- Centralized log collection
- Log rotation and retention
- Query capabilities
- Metrics emission

**API Endpoints:**
```
POST   /api/v1/logs                    # Submit log entry
GET    /api/v1/logs                    # Query logs
GET    /api/v1/logs/services/{service} # Get logs for specific service
GET    /api/v1/metrics                 # Get metrics
GET    /api/v1/health                  # Health check
```

**Data Models:**
```python
class LogEntry:
    timestamp: datetime
    service: str
    level: LogLevel  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message: str
    context: Dict[str, Any]
    trace_id: Optional[str]

class Metric:
    name: str
    value: float
    tags: Dict[str, str]
    timestamp: datetime
```

## Common Models (services/common)

### Base Models
```python
class ServiceResponse:
    success: bool
    data: Optional[Any]
    error: Optional[ErrorDetail]

class ErrorDetail:
    code: str
    message: str
    details: Optional[Dict[str, Any]]

class HealthCheck:
    service: str
    status: str  # "healthy", "unhealthy"
    version: str
    uptime_seconds: int
    checks: Dict[str, bool]
```

### Configuration Models
```python
class ServiceConfig:
    host: str = "localhost"
    port: int
    log_level: str = "INFO"

class YouTubeConfig:
    api_key: str  # From environment variable
    quota_limit: int = 10000
    quota_reserve: int = 1000  # Keep this much quota in reserve

class StorageConfig:
    base_path: str = "~/YTArchive"
    metadata_dir: str = "metadata"
    videos_dir: str = "videos"
    logs_dir: str = "logs"
```

## Service Communication Flow

### Video Download Flow
1. CLI sends request to Jobs Service
2. Jobs Service creates job and calls Metadata Service
3. Metadata Service fetches from YouTube API and returns data
4. Jobs Service calls Storage Service to check if video exists
5. If not exists, Jobs Service calls Download Service
6. Download Service downloads video and reports progress
7. Upon completion, Download Service notifies Jobs Service
8. Jobs Service calls Storage Service to save file info
9. All services send logs to Logging Service

### Error Handling Flow
1. Service encounters error and logs to Logging Service
2. Service returns error response to caller
3. Jobs Service updates job status to FAILED
4. After 3 retries, Jobs Service calls Storage Service
5. Storage Service adds to work plan for manual review

## Inter-Service Communication

### Authentication
- No authentication in Phase 1 (internal use only)
- All services trust each other

### Request Format
```json
{
  "trace_id": "uuid",
  "timestamp": "2024-01-01T00:00:00Z",
  "data": { ... }
}
```

### Response Format
```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "trace_id": "uuid"
}
```

### Error Response Format
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "E001",
    "message": "API quota exceeded",
    "details": { ... }
  },
  "trace_id": "uuid"
}
```
