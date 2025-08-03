# Storage Service Specification

## Overview
The Storage Service manages file system organization, stores metadata and video information, checks for existing files, and generates work plans for failed or unavailable content.

## Service Configuration
- **Port**: 8003
- **Host**: localhost (configurable)
- **Dependencies**: File system access

## API Endpoints

### Metadata Storage

#### Save Video Metadata
```
POST /api/v1/storage/save/metadata
```

**Request Body**:
```json
{
  "video_id": "dQw4w9WgXcQ",
  "metadata": {
    "title": "Video Title",
    "description": "Description...",
    "duration": 212,
    "upload_date": "2009-10-25T06:57:33Z",
    "channel_id": "UCuAXFkgsw1L7xaCfnd5JJOw",
    "channel_title": "Channel Name",
    "thumbnail_urls": {...},
    "available_captions": ["en"],
    "view_count": 1234567890,
    "like_count": 9876543,
    "fetched_at": "2024-01-01T00:00:00Z"
  }
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "path": "~/YTArchive/metadata/videos/dQw4w9WgXcQ.json",
    "size_bytes": 2048,
    "saved_at": "2024-01-01T00:00:00Z"
  },
  "trace_id": "uuid"
}
```

### Video Storage

#### Save Video Information
```
POST /api/v1/storage/save/video
```

**Request Body**:
```json
{
  "video_id": "dQw4w9WgXcQ",
  "video_path": "~/YTArchive/videos/dQw4w9WgXcQ/dQw4w9WgXcQ.mp4",
  "thumbnail_path": "~/YTArchive/videos/dQw4w9WgXcQ/dQw4w9WgXcQ_thumb.jpg",
  "captions": {
    "en": "~/YTArchive/videos/dQw4w9WgXcQ/captions/dQw4w9WgXcQ_en.vtt"
  },
  "file_size": 104857600,
  "download_completed_at": "2024-01-01T00:05:00Z"
}
```

### Existence Checks

#### Check if Video Exists
```
GET /api/v1/storage/exists/{video_id}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "exists": true,
    "has_video": true,
    "has_metadata": true,
    "has_thumbnail": true,
    "has_captions": ["en"],
    "paths": {
      "video": "~/YTArchive/videos/dQw4w9WgXcQ/dQw4w9WgXcQ.mp4",
      "metadata": "~/YTArchive/metadata/videos/dQw4w9WgXcQ.json",
      "thumbnail": "~/YTArchive/videos/dQw4w9WgXcQ/dQw4w9WgXcQ_thumb.jpg"
    },
    "last_modified": "2024-01-01T00:05:00Z"
  },
  "trace_id": "uuid"
}
```

### Metadata Retrieval

#### Get Stored Metadata
```
GET /api/v1/storage/metadata/{video_id}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "video_id": "dQw4w9WgXcQ",
    "metadata": {...},
    "storage_info": {
      "metadata_path": "~/YTArchive/metadata/videos/dQw4w9WgXcQ.json",
      "video_path": "~/YTArchive/videos/dQw4w9WgXcQ/dQw4w9WgXcQ.mp4",
      "file_size": 104857600,
      "stored_at": "2024-01-01T00:00:00Z"
    }
  },
  "trace_id": "uuid"
}
```

### Work Plan Management

#### Generate Work Plan
```
POST /api/v1/storage/work-plan
```

**Request Body**:
```json
{
  "unavailable_videos": [
    {
      "video_id": "abc123",
      "title": "Private Video",
      "reason": "private",
      "detected_at": "2024-01-01T00:00:00Z"
    }
  ],
  "failed_downloads": [
    {
      "video_id": "def456",
      "title": "Failed Video",
      "attempts": 3,
      "last_attempt": "2024-01-01T00:00:00Z",
      "errors": [...]
    }
  ]
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "plan_id": "20240101_120000",
    "path": "~/.ytarchive/data/work_plans/20240101_120000_plan.json",
    "total_videos": 2,
    "unavailable_count": 1,
    "failed_count": 1
  },
  "trace_id": "uuid"
}
```

### Storage Statistics

#### Get Storage Stats
```
GET /api/v1/storage/stats
```

**Response**:
```json
{
  "success": true,
  "data": {
    "total_videos": 150,
    "total_size_bytes": 32212254720,
    "total_size_human": "30 GB",
    "metadata_count": 150,
    "video_count": 145,
    "thumbnail_count": 148,
    "caption_count": 120,
    "disk_usage": {
      "used_bytes": 32212254720,
      "free_bytes": 107374182400,
      "total_bytes": 500107862016,
      "usage_percent": 6.4
    },
    "oldest_file": "2023-01-01T00:00:00Z",
    "newest_file": "2024-01-01T00:00:00Z"
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
from common.models import UnavailableVideo, FailedDownload

class StorageLocation(BaseModel):
    video_id: str
    video_path: Optional[str] = None
    metadata_path: str
    thumbnail_path: Optional[str] = None
    captions_paths: Dict[str, str] = {}  # language -> path
    size_bytes: int = 0
    stored_at: datetime
    last_modified: datetime

class VideoExistence(BaseModel):
    exists: bool
    has_video: bool = False
    has_metadata: bool = False
    has_thumbnail: bool = False
    has_captions: List[str] = []
    paths: Dict[str, Optional[str]] = {}
    last_modified: Optional[datetime] = None

class SaveMetadataRequest(BaseModel):
    video_id: str
    metadata: Dict[str, Any]

class SaveVideoRequest(BaseModel):
    video_id: str
    video_path: str
    thumbnail_path: Optional[str] = None
    captions: Dict[str, str] = {}  # language -> path
    file_size: int
    download_completed_at: datetime

class WorkPlan(BaseModel):
    plan_id: str
    created_at: datetime
    unavailable_videos: List[UnavailableVideo]
    failed_downloads: List[FailedDownload]
    total_videos: int
    unavailable_count: int
    failed_count: int
    notes: Optional[str] = None

class StorageStats(BaseModel):
    total_videos: int
    total_size_bytes: int
    total_size_human: str
    metadata_count: int
    video_count: int
    thumbnail_count: int
    caption_count: int
    disk_usage: Dict[str, Any]
    oldest_file: Optional[datetime] = None
    newest_file: Optional[datetime] = None
```

## File Organization

### Directory Structure
```
~/YTArchive/
├── metadata/
│   ├── videos/
│   │   └── {video_id}.json         # Canonical metadata
│   └── playlists/
│       └── {playlist_id}.json      # Playlist metadata
└── videos/
    └── {video_id}/
        ├── {video_id}.mp4          # Video file
        ├── {video_id}_thumb.jpg    # Thumbnail
        ├── {video_id}_metadata.json # Video-specific metadata
        └── captions/
            └── {video_id}_{lang}.vtt # Caption files

~/.ytarchive/data/
└── work_plans/
    └── {timestamp}_plan.json       # Work plans for failed items
```

### File Naming Conventions
- Video files: `{video_id}.mp4`
- Thumbnails: `{video_id}_thumb.jpg`
- Metadata: `{video_id}.json` or `{video_id}_metadata.json`
- Captions: `{video_id}_{language_code}.vtt`
- Work plans: `{YYYYMMDD_HHMMSS}_plan.json`

## Storage Operations

### Metadata Storage
1. Validate metadata structure
2. Create directory if needed
3. Write JSON with pretty formatting
4. Update storage index

### Video Storage
1. Verify file exists at source path
2. Create video directory structure
3. Move/copy files to destination
4. Update storage records
5. Clean up source if configured

### Existence Checking
1. Check metadata directory
2. Check video directory
3. Verify file integrity (optional)
4. Return detailed existence info

### Work Plan Generation
1. Collect failed/unavailable items
2. Generate timestamp-based ID
3. Create structured JSON report
4. Save to work plans directory

## Configuration

### Environment Variables
None required

### Config File Settings
```toml
[services.storage]
host = "localhost"
port = 8003
check_integrity = false  # Verify file hashes
move_files = false  # Move vs copy files
cleanup_source = false  # Delete source after storage

[storage]
base_path = "~/YTArchive"
metadata_dir = "{base_path}/metadata"
videos_dir = "{base_path}/videos"
work_plans_dir = "~/.ytarchive/data/work_plans"
min_free_space_gb = 10  # Minimum free space required
```

## Error Scenarios

### Common Errors
- `E004`: Storage full
- `E007`: Invalid request (missing required fields)
- `E999`: Internal error (file system issues)

### Error Handling
- Disk space: Check before operations
- File permissions: Verify write access
- Path validation: Ensure valid paths
- Atomicity: Use temp files + rename

## Metrics

The Storage service tracks:
- Total files stored
- Storage space used
- Files by type (video, metadata, etc.)
- Work plans generated
- Average file size
- Storage operations per minute

## Example Usage

### Save Video Metadata
```bash
curl -X POST http://localhost:8003/api/v1/storage/save/metadata \
  -H "Content-Type: application/json" \
  -d '{
    "video_id": "dQw4w9WgXcQ",
    "metadata": {...}
  }'
```

### Check if Video Exists
```bash
curl http://localhost:8003/api/v1/storage/exists/dQw4w9WgXcQ
```

### Get Storage Statistics
```bash
curl http://localhost:8003/api/v1/storage/stats
```

### Generate Work Plan
```bash
curl -X POST http://localhost:8003/api/v1/storage/work-plan \
  -H "Content-Type: application/json" \
  -d '{
    "unavailable_videos": [...],
    "failed_downloads": [...]
  }'
```
