# YouTube Archive - Critical Design Decisions

This document addresses critical design decisions that must be made before implementation begins.

## 1. Data Persistence Strategy

### Storage Organization
- **Decision**: Centralized data directory with configurable paths
- **Base Directory**: `~/.ytarchive/data/` (configurable)
- **Rationale**: Simplifies backups, data management, and organization
- **Structure**:
  ```
  ~/.ytarchive/data/
  ├── jobs/           # Job definitions and state
  ├── registry/       # Service registry data
  ├── work_plans/     # Failed/unavailable video plans
  ├── tmp/            # Temporary files
  └── logs/           # Service logs
  ```

### Job Storage
- **Decision**: File-based JSON storage for jobs
- **Location**: `{base_data_dir}/jobs/` (configurable)
- **Format**: Individual JSON files per job: `{job_id}.json`
- **Rationale**: Simple, portable, no database dependencies
- **Retention**: Keep completed jobs for 30 days, failed jobs for 90 days

### Service Registry Storage
- **Decision**: In-memory storage with file backup
- **Location**: `{base_data_dir}/registry/registry.json` (configurable)
- **Update Frequency**: On each registration/health check
- **Rationale**: Fast access, survives restarts

### Work Plan Storage
- **Decision**: File-based storage in data directory
- **Location**: `{base_data_dir}/work_plans/` (configurable)
- **Format**: `{timestamp}_plan.json`
- **Retention**: Indefinite (manual cleanup)

### Temporary Files
- **Location**: `{base_data_dir}/tmp/` (configurable)
- **Purpose**: Partial downloads, processing intermediates
- **Cleanup**: On completion or service shutdown

### Log Storage
- **Location**: `{base_data_dir}/logs/` (configurable)
- **Organization**: By service and date
- **Format**: `{service_name}/{date}.log`
- **Rotation**: Daily rotation, 30-day retention

## 2. Missing Data Models

### JobOptions Model
```python
class JobOptions(BaseModel):
    """Options for job execution."""
    output_dir: str = "~/YTArchive"
    quality: str = "1080p"
    include_metadata: bool = True
    include_captions: bool = True
    caption_languages: List[str] = ["en"]
    skip_existing: bool = True
    api_key: Optional[str] = None  # Can override env var
```

### JobResult Model
```python
class JobResult(BaseModel):
    """Result of processing a single video/item."""
    video_id: str
    status: str  # "success", "failed", "skipped"
    message: Optional[str] = None
    metadata_saved: bool = False
    video_downloaded: bool = False
    file_size: Optional[int] = None
    duration_seconds: Optional[float] = None
    error_code: Optional[str] = None
```

### PlaylistVideo Model
```python
class PlaylistVideo(BaseModel):
    """Video entry in a playlist."""
    video_id: str
    position: int
    title: str
    duration: Optional[int] = None  # seconds
    is_available: bool = True
    added_at: Optional[datetime] = None
```

### UnavailableVideo Model
```python
class UnavailableVideo(BaseModel):
    """Track videos that cannot be downloaded."""
    video_id: str
    title: Optional[str] = None
    reason: str  # "private", "deleted", "region_blocked", "age_restricted"
    detected_at: datetime
    playlist_id: Optional[str] = None
    last_available: Optional[datetime] = None
```

### FailedDownload Model
```python
class FailedDownload(BaseModel):
    """Track failed download attempts."""
    video_id: str
    title: str
    attempts: int
    last_attempt: datetime
    errors: List[Dict[str, Any]]  # Error history
    file_size: Optional[int] = None
    retry_after: Optional[datetime] = None
```

## 3. CLI Service Discovery

### Configuration Strategy
- **Decision**: CLI reads from the same `config.toml` as services
- **Service Discovery**: Direct connection to Jobs service port from config
- **Fallback**: If Jobs service down, show error with service status
- **Implementation**:
  ```python
  # CLI connects only to Jobs service
  jobs_url = f"http://{config.services.jobs.host}:{config.services.jobs.port}"
  ```

## 4. YouTube API Integration

### Authentication Method
- **Decision**: API Key only (no OAuth)
- **Storage**: Environment variable `YOUTUBE_API_KEY`
- **Validation**: Check on service startup
- **Rotation**: Manual update + service restart

### API Endpoints to Use
```python
# Video metadata
youtube.videos().list(part="snippet,contentDetails,status", id=video_id)

# Playlist metadata
youtube.playlists().list(part="snippet,contentDetails", id=playlist_id)

# Playlist items
youtube.playlistItems().list(
    part="snippet,contentDetails",
    playlistId=playlist_id,
    maxResults=50
)

# Captions
youtube.captions().list(part="snippet", videoId=video_id)
```

### Quota Management
- **Costs**:
  - `videos.list`: 1 unit
  - `playlists.list`: 1 unit
  - `playlistItems.list`: 1 unit
  - `captions.list`: 50 units
- **Strategy**: Check quota before each API call
- **Reserve**: Keep 1000 units in reserve (configurable)

## 5. File Handling Conventions

### File Naming
```
videos/{video_id}/
  ├── {video_id}.mp4           # Video file
  ├── {video_id}_thumb.jpg     # Default thumbnail (maxres)
  ├── {video_id}_metadata.json # Video metadata
  └── captions/
      └── {video_id}_en.vtt    # Caption files

metadata/
  ├── videos/
  │   └── {video_id}.json      # Canonical metadata
  └── playlists/
      └── {playlist_id}.json   # Playlist metadata
```

### Thumbnail Selection
- **Priority**: maxresdefault > standard > high > medium > default
- **Format**: Always save as JPEG
- **Fallback**: Skip if no thumbnails available

### Temporary Files
- **Location**: `{output_dir}/.tmp/`
- **Naming**: `{video_id}.part` for partial downloads
- **Cleanup**: On successful completion or service shutdown

## 6. Service Communication Policies

### HTTP Timeouts
```python
TIMEOUTS = {
    "connect": 5.0,      # Connection timeout
    "read": 30.0,        # Read timeout
    "write": 30.0,       # Write timeout
    "pool": 30.0         # Pool timeout
}

# Long operations (downloads)
DOWNLOAD_TIMEOUT = 3600  # 1 hour
```

### Retry Policy Between Services
```python
RETRY_CONFIG = {
    "max_attempts": 3,
    "backoff_factor": 2,
    "max_backoff": 30,
    "retry_on": [502, 503, 504, 429]  # HTTP status codes
}
```

### Circuit Breaker
- **Threshold**: 5 consecutive failures
- **Timeout**: 60 seconds before retry
- **Half-Open**: Allow 1 request to test recovery

## 7. Progress Communication

### Progress Update Mechanism
- **Method**: Job status includes progress field
- **Update Frequency**: Every 5 seconds or 5% progress
- **Storage**: Update job file with progress
- **Format**:
  ```python
  class Progress(BaseModel):
      current: int
      total: int
      percentage: float
      message: str
      speed_bps: Optional[float] = None  # bytes per second
      eta_seconds: Optional[int] = None
  ```

### CLI Progress Display
- **Method**: Poll Jobs service every 2 seconds
- **Display**: Rich progress bar with speed/ETA
- **Interrupt**: Graceful cancellation on Ctrl+C

## 8. Data Validation Rules

### Video ID Validation
```python
VIDEO_ID_PATTERN = r"^[a-zA-Z0-9_-]{11}$"
```

### Playlist ID Validation
```python
PLAYLIST_ID_PATTERN = r"^(PL|UU|FL|RD|OL)[a-zA-Z0-9_-]{16,41}$"
```

### Storage Path Validation
- Must be absolute or start with `~/`
- Must have write permissions
- Must have sufficient space (check before download)

## 9. Health Check Criteria

### Service Health Definition
A service is considered healthy when:
1. HTTP endpoint responds with 200 status
2. Response time < 5 seconds
3. Required dependencies accessible
4. No critical errors in last 60 seconds

### Health Check Response
```python
class HealthStatus(BaseModel):
    healthy: bool
    checks: Dict[str, bool] = {
        "http_responsive": True,
        "dependencies_available": True,
        "no_critical_errors": True,
        "disk_space_available": True
    }
    message: Optional[str] = None
    last_error: Optional[str] = None
```

## 10. Job State Management

### Job Lifecycle States
```
CREATED -> QUEUED -> RUNNING -> [COMPLETED|FAILED|CANCELLED]
                         ↓
                    RETRYING -> RUNNING
```

### State Persistence
- Save state after each transition
- Include timestamp for each state change
- Keep state history for debugging

### Cleanup Policy
- Completed jobs: Delete after 30 days
- Failed jobs: Delete after 90 days
- Cancelled jobs: Delete after 7 days
- Work plans: Never auto-delete
