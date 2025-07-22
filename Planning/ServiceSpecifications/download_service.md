# Download Service Specification

## Overview
The Download Service handles video downloads using yt-dlp, manages download progress, supports different quality options, and provides resume capability for interrupted downloads.

## Service Configuration
- **Port**: 8002
- **Host**: localhost (configurable)
- **Dependencies**: yt-dlp

## API Endpoints

### Download Operations

#### Start Video Download
```
POST /api/v1/download/video
```

**Request Body**:
```json
{
  "video_id": "dQw4w9WgXcQ",
  "quality": "1080p",
  "output_path": "~/YTArchive/videos",
  "include_captions": true,
  "caption_languages": ["en", "es"]
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "task_id": "uuid",
    "video_id": "dQw4w9WgXcQ",
    "status": "downloading",
    "created_at": "2024-01-01T00:00:00Z"
  },
  "trace_id": "uuid"
}
```

#### Get Download Progress
```
GET /api/v1/download/progress/{task_id}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "task_id": "uuid",
    "video_id": "dQw4w9WgXcQ",
    "status": "downloading",
    "progress_percent": 45.5,
    "downloaded_bytes": 45500000,
    "total_bytes": 100000000,
    "speed": 1048576,
    "eta": 52,
    "file_path": "~/YTArchive/videos/dQw4w9WgXcQ/dQw4w9WgXcQ.mp4"
  },
  "trace_id": "uuid"
}
```

#### Cancel Download
```
POST /api/v1/download/cancel/{task_id}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "task_id": "uuid",
    "status": "cancelled",
    "message": "Download cancelled successfully"
  },
  "trace_id": "uuid"
}
```

#### Get Available Formats
```
GET /api/v1/download/formats/{video_id}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "video_id": "dQw4w9WgXcQ",
    "formats": [
      {
        "format_id": "137",
        "ext": "mp4",
        "resolution": "1080p",
        "fps": 30,
        "vcodec": "avc1.640028",
        "acodec": "none",
        "filesize": 100000000,
        "format_note": "1080p"
      },
      {
        "format_id": "22",
        "ext": "mp4",
        "resolution": "720p",
        "fps": 30,
        "vcodec": "avc1.64001F",
        "acodec": "mp4a.40.2",
        "filesize": 50000000,
        "format_note": "720p"
      }
    ],
    "best_format": "137+140",
    "requested_quality": "1080p"
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

class DownloadStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

class DownloadRequest(BaseModel):
    video_id: str
    quality: str = "1080p"  # "best", "1080p", "720p", "480p", etc.
    output_path: str
    include_captions: bool = True
    caption_languages: List[str] = Field(default_factory=lambda: ["en"])
    resume: bool = True  # Resume partial downloads

class DownloadTask(BaseModel):
    task_id: str
    video_id: str
    status: DownloadStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output_path: str
    file_path: Optional[str] = None
    error: Optional[str] = None

class DownloadProgress(BaseModel):
    task_id: str
    video_id: str
    status: DownloadStatus
    progress_percent: float
    downloaded_bytes: int
    total_bytes: Optional[int] = None
    speed: Optional[float] = None  # bytes/sec
    eta: Optional[int] = None  # seconds
    file_path: Optional[str] = None
    error: Optional[str] = None

class VideoFormat(BaseModel):
    format_id: str
    ext: str
    resolution: Optional[str] = None
    fps: Optional[int] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    filesize: Optional[int] = None
    format_note: Optional[str] = None

class AvailableFormats(BaseModel):
    video_id: str
    formats: List[VideoFormat]
    best_format: str
    requested_quality: Optional[str] = None
```

## yt-dlp Integration

### Download Options
```python
ydl_opts = {
    'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
    'outtmpl': '%(id)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'writesubtitles': True,
    'subtitleslangs': ['en'],
    'subtitlesformat': 'vtt',
    'writethumbnail': True,
    'merge_output_format': 'mp4',
    'postprocessors': [{
        'key': 'FFmpegVideoConvertor',
        'preferedformat': 'mp4',
    }],
    'progress_hooks': [progress_callback],
}
```

### Quality Mapping
```python
QUALITY_MAP = {
    "best": "bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
    "audio": "bestaudio/best",
}
```

### Progress Tracking
```python
def progress_callback(d):
    if d['status'] == 'downloading':
        progress = {
            'downloaded_bytes': d.get('downloaded_bytes', 0),
            'total_bytes': d.get('total_bytes') or d.get('total_bytes_estimate'),
            'speed': d.get('speed'),
            'eta': d.get('eta'),
            'progress_percent': d.get('_percent_str', '0%').strip('%')
        }
        # Update task progress
```

## Download Management

### Task Lifecycle
1. Create download task (PENDING)
2. Start download (DOWNLOADING)
3. Track progress via callbacks
4. Handle completion/failure
5. Clean up temporary files

### Resume Support
- Check for `.part` files in output directory
- Use yt-dlp's built-in resume capability
- Track partial download state

### Concurrent Downloads
- Default: 3 concurrent downloads
- Configurable via settings
- Queue excess requests

### Temporary File Handling
- Location: `{output_path}/.tmp/`
- Pattern: `{video_id}.part`, `{video_id}.ytdl`
- Cleanup on completion or after timeout

## Configuration

### Environment Variables
None required (yt-dlp handles YouTube access)

### Config File Settings
```toml
[services.download]
host = "localhost"
port = 8002
max_concurrent_downloads = 3
download_timeout = 3600  # seconds
temp_dir = "~/.ytarchive/data/tmp"
default_quality = "1080p"
```

## Error Scenarios

### Common Errors
- `E002`: Video unavailable
- `E003`: Network timeout
- `E004`: Storage full
- `E007`: Invalid request (bad quality format)

### Error Handling
- Network errors: Automatic retry with resume
- Storage full: Check before download, fail fast
- Invalid format: Return available formats
- Timeout: Cancel download, clean up files

## Metrics

The Download service tracks:
- Active downloads count
- Completed downloads count
- Failed downloads by error type
- Average download speed
- Total bytes downloaded
- Queue size

## Example Usage

### Start a Download
```bash
curl -X POST http://localhost:8002/api/v1/download/video \
  -H "Content-Type: application/json" \
  -d '{
    "video_id": "dQw4w9WgXcQ",
    "quality": "720p",
    "output_path": "~/YTArchive/videos"
  }'
```

### Check Progress
```bash
curl http://localhost:8002/api/v1/download/progress/{task_id}
```

### Get Available Formats
```bash
curl http://localhost:8002/api/v1/download/formats/dQw4w9WgXcQ
```

### Cancel a Download
```bash
curl -X POST http://localhost:8002/api/v1/download/cancel/{task_id}
```
