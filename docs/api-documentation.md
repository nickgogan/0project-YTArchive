# YTArchive API Documentation

## Overview

YTArchive provides a comprehensive REST API through its microservices architecture. Each service exposes HTTP endpoints for programmatic access, allowing integration with external applications and automation workflows.

## Service Architecture

YTArchive consists of four main services:

- **Jobs Service** (Port 8001) - Job orchestration and coordination
- **Metadata Service** (Port 8002) - YouTube metadata extraction
- **Download Service** (Port 8003) - Video download management
- **Storage Service** (Port 8004) - File storage and organization

## Authentication

Currently, YTArchive services use API key authentication for YouTube API access. No authentication is required for local service-to-service communication.

**Required Environment Variables:**
- `YOUTUBE_API_KEY` - YouTube Data API v3 key

## Base URLs

Default service URLs (configurable):
```
Jobs Service:     http://localhost:8001
Metadata Service: http://localhost:8002
Download Service: http://localhost:8003
Storage Service:  http://localhost:8004
```

## Common Response Format

All services follow consistent response patterns:

### Success Response
```json
{
  "status": "success",
  "data": { ... },
  "timestamp": "2025-01-26T09:43:40Z"
}
```

### Error Response
```json
{
  "status": "error",
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": { ... }
  },
  "timestamp": "2025-01-26T09:43:40Z"
}
```

---

# Jobs Service API

**Base URL:** `http://localhost:8001`

The Jobs Service orchestrates download workflows and manages job lifecycle.

## Endpoints

### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "jobs",
  "timestamp": "2025-01-26T09:43:40Z"
}
```

### Create Download Job
```http
POST /jobs
```

**Request Body:**
```json
{
  "video_id": "dQw4w9WgXcQ",
  "quality": "720p",
  "output_path": "/downloads",
  "metadata_requested": true
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "job_id": "job_12345",
    "video_id": "dQw4w9WgXcQ",
    "status": "queued",
    "created_at": "2025-01-26T09:43:40Z",
    "estimated_completion": "2025-01-26T09:45:40Z"
  }
}
```

### Get Job Status
```http
GET /jobs/{job_id}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "job_id": "job_12345",
    "video_id": "dQw4w9WgXcQ",
    "status": "downloading",
    "progress": 45,
    "created_at": "2025-01-26T09:43:40Z",
    "updated_at": "2025-01-26T09:44:15Z",
    "metadata": { ... },
    "download_path": "/downloads/video.mp4"
  }
}
```

### List Jobs
```http
GET /jobs
```

**Query Parameters:**
- `status` - Filter by job status (`queued`, `downloading`, `completed`, `failed`)
- `limit` - Number of results to return (default: 50)
- `offset` - Pagination offset (default: 0)

**Response:**
```json
{
  "status": "success",
  "data": {
    "jobs": [
      {
        "job_id": "job_12345",
        "video_id": "dQw4w9WgXcQ",
        "status": "completed",
        "created_at": "2025-01-26T09:43:40Z"
      }
    ],
    "total": 1,
    "has_more": false
  }
}
```

### Cancel Job
```http
DELETE /jobs/{job_id}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "job_id": "job_12345",
    "status": "cancelled",
    "cancelled_at": "2025-01-26T09:44:00Z"
  }
}
```

---

# Metadata Service API

**Base URL:** `http://localhost:8002`

The Metadata Service handles YouTube metadata extraction and caching.

## Endpoints

### Health Check
```http
GET /health
```

### Get Video Metadata
```http
GET /metadata/{video_id}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "video_id": "dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up",
    "description": "The official video...",
    "duration": 212,
    "published_at": "2009-10-25T06:57:33Z",
    "channel": {
      "id": "UCuAXFkgsw1L7xaCfnd5JJOw",
      "title": "Rick Astley",
      "subscriber_count": 2890000
    },
    "statistics": {
      "view_count": 1380000000,
      "like_count": 14000000,
      "comment_count": 2100000
    },
    "thumbnails": {
      "default": "https://i.ytimg.com/vi/dQw4w9WgXcQ/default.jpg",
      "medium": "https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg",
      "high": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
    },
    "formats": [
      {
        "format_id": "18",
        "quality": "360p",
        "container": "mp4",
        "filesize": 15234567
      }
    ],
    "cached": true,
    "cache_expires_at": "2025-01-26T10:43:40Z"
  }
}
```

### Get Batch Metadata
```http
POST /metadata/batch
```

**Request Body:**
```json
{
  "video_ids": ["dQw4w9WgXcQ", "jNQXAC9IVRw"],
  "include_formats": false
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "metadata": {
      "dQw4w9WgXcQ": { ... },
      "jNQXAC9IVRw": { ... }
    },
    "failed": [],
    "cached_count": 1,
    "api_calls_used": 1
  }
}
```

### Get Playlist Metadata
```http
GET /metadata/playlist/{playlist_id}
```

**Query Parameters:**
- `include_videos` - Include individual video metadata (default: false)
- `limit` - Maximum videos to return (default: 50)

**Response:**
```json
{
  "status": "success",
  "data": {
    "playlist_id": "PLFgquLnL59alCl_2TQvOiD5Vgm1hCaGSI",
    "title": "My Playlist",
    "description": "Collection of videos",
    "channel": {
      "id": "UCuAXFkgsw1L7xaCfnd5JJOw",
      "title": "Channel Name"
    },
    "video_count": 25,
    "videos": [
      {
        "video_id": "dQw4w9WgXcQ",
        "title": "Video Title",
        "position": 1
      }
    ]
  }
}
```

### Clear Cache
```http
DELETE /metadata/cache
```

**Query Parameters:**
- `video_id` - Clear specific video cache
- `expired_only` - Clear only expired cache entries (default: false)

---

# Download Service API

**Base URL:** `http://localhost:8003`

The Download Service manages video download operations using yt-dlp.

## Endpoints

### Health Check
```http
GET /health
```

### Download Video
```http
POST /download
```

**Request Body:**
```json
{
  "video_id": "dQw4w9WgXcQ",
  "quality": "720p",
  "output_path": "/downloads",
  "job_id": "job_12345",
  "format_selection": "best[height<=720]",
  "extract_audio": false
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "download_id": "dl_67890",
    "video_id": "dQw4w9WgXcQ",
    "status": "downloading",
    "progress": 0,
    "estimated_size": 52428800,
    "output_path": "/downloads/Rick Astley - Never Gonna Give You Up [dQw4w9WgXcQ].mp4",
    "started_at": "2025-01-26T09:43:40Z"
  }
}
```

### Get Download Status
```http
GET /download/{download_id}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "download_id": "dl_67890",
    "video_id": "dQw4w9WgXcQ",
    "status": "completed",
    "progress": 100,
    "downloaded_bytes": 52428800,
    "total_bytes": 52428800,
    "speed": "1.2MB/s",
    "eta": "00:00",
    "output_path": "/downloads/video.mp4",
    "started_at": "2025-01-26T09:43:40Z",
    "completed_at": "2025-01-26T09:44:25Z"
  }
}
```

### List Active Downloads
```http
GET /download
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "downloads": [
      {
        "download_id": "dl_67890",
        "video_id": "dQw4w9WgXcQ",
        "status": "downloading",
        "progress": 45
      }
    ],
    "active_count": 1,
    "queue_count": 2
  }
}
```

### Cancel Download
```http
DELETE /download/{download_id}
```

---

# Storage Service API

**Base URL:** `http://localhost:8004`

The Storage Service manages file organization, metadata persistence, and search functionality.

## Endpoints

### Health Check
```http
GET /health
```

### Save Video Metadata
```http
POST /storage/metadata
```

**Request Body:**
```json
{
  "video_id": "dQw4w9WgXcQ",
  "metadata": {
    "title": "Rick Astley - Never Gonna Give You Up",
    "duration": 212,
    "published_at": "2009-10-25T06:57:33Z"
  },
  "file_path": "/downloads/video.mp4",
  "file_size": 52428800
}
```

### Save Video File
```http
POST /storage/video
```

**Request Body (multipart/form-data):**
- `video_id` - YouTube video ID
- `file` - Video file
- `metadata` - JSON metadata

### Get Video Information
```http
GET /storage/videos/{video_id}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "video_id": "dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up",
    "file_path": "/downloads/video.mp4",
    "file_size": 52428800,
    "stored_at": "2025-01-26T09:44:25Z",
    "metadata": { ... }
  }
}
```

### List Stored Videos
```http
GET /storage/videos
```

**Query Parameters:**
- `limit` - Number of results (default: 50)
- `offset` - Pagination offset (default: 0)
- `search` - Search query in title/description
- `sort` - Sort by (`stored_at`, `title`, `duration`)
- `order` - Sort order (`asc`, `desc`)

**Response:**
```json
{
  "status": "success",
  "data": {
    "videos": [
      {
        "video_id": "dQw4w9WgXcQ",
        "title": "Rick Astley - Never Gonna Give You Up",
        "duration": 212,
        "stored_at": "2025-01-26T09:44:25Z",
        "file_size": 52428800
      }
    ],
    "total": 1,
    "has_more": false
  }
}
```

### Search Videos
```http
GET /storage/search
```

**Query Parameters:**
- `q` - Search query
- `type` - Search type (`title`, `description`, `all`)
- `limit` - Results limit (default: 20)

### Get Storage Statistics
```http
GET /storage/stats
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "total_videos": 150,
    "total_size": 15728640000,
    "total_duration": 45000,
    "oldest_video": "2025-01-01T00:00:00Z",
    "newest_video": "2025-01-26T09:44:25Z",
    "storage_breakdown": {
      "videos": {
        "count": 150,
        "size": 14000000000
      },
      "metadata": {
        "count": 150,
        "size": 500000000
      },
      "thumbnails": {
        "count": 150,
        "size": 1228640000
      }
    }
  }
}
```

### Create Work Plan
```http
POST /storage/workplan
```

**Request Body:**
```json
{
  "video_ids": ["dQw4w9WgXcQ"],
  "reason": "download_failed",
  "metadata": {
    "error": "Network timeout",
    "retry_count": 1
  }
}
```

### List Work Plans
```http
GET /storage/workplan
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "work_plans": [
      {
        "id": "wp_123",
        "video_ids": ["dQw4w9WgXcQ"],
        "reason": "download_failed",
        "status": "pending",
        "created_at": "2025-01-26T09:45:00Z",
        "retry_count": 1
      }
    ],
    "total": 1
  }
}
```

---

# Error Codes

## Common Error Codes

| Code | Description | Service |
|------|-------------|---------|
| `INVALID_VIDEO_ID` | Video ID format invalid | All |
| `VIDEO_NOT_FOUND` | Video does not exist | Metadata, Download |
| `API_QUOTA_EXCEEDED` | YouTube API quota limit reached | Metadata |
| `DOWNLOAD_FAILED` | Video download failed | Download |
| `STORAGE_ERROR` | File storage operation failed | Storage |
| `JOB_NOT_FOUND` | Job ID does not exist | Jobs |

## Service-Specific Error Codes

### Metadata Service
- `YOUTUBE_API_ERROR` - YouTube API returned an error
- `CACHE_ERROR` - Cache operation failed
- `RATE_LIMIT_EXCEEDED` - API rate limit exceeded

### Download Service
- `YTDLP_ERROR` - yt-dlp extraction failed
- `DOWNLOAD_TIMEOUT` - Download operation timed out
- `QUALITY_NOT_AVAILABLE` - Requested quality not available
- `DISK_FULL` - Insufficient disk space

### Storage Service
- `FILE_NOT_FOUND` - Requested file does not exist
- `METADATA_INVALID` - Metadata format invalid
- `SEARCH_ERROR` - Search operation failed

### Jobs Service
- `JOB_CANCELLED` - Job was cancelled by user
- `COORDINATION_ERROR` - Service coordination failed

---

# Rate Limits

## YouTube API Limits
- **Quota**: 10,000 units per day (configurable)
- **Requests per second**: 100 (handled automatically)

## Service Limits
- **Concurrent downloads**: 3 (configurable)
- **API requests per minute**: 1000
- **Maximum file size**: 5GB per video

---

# WebSocket Events (Future)

For real-time updates, YTArchive will support WebSocket connections:

```javascript
const ws = new WebSocket('ws://localhost:8001/ws');

// Download progress updates
ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  if (data.event === 'download_progress') {
    console.log(`Progress: ${data.progress}%`);
  }
};
```

---

# SDK Examples

## Python SDK Usage

```python
import asyncio
from ytarchive_sdk import YTArchiveClient

async def main():
    client = YTArchiveClient(base_url="http://localhost:8001")

    # Create download job
    job = await client.jobs.create_download_job(
        video_id="dQw4w9WgXcQ",
        quality="720p"
    )

    # Monitor progress
    while job.status != "completed":
        job = await client.jobs.get_job(job.job_id)
        print(f"Progress: {job.progress}%")
        await asyncio.sleep(1)

    # Get video info
    video = await client.storage.get_video(job.video_id)
    print(f"Downloaded: {video.title}")

asyncio.run(main())
```

## JavaScript SDK Usage

```javascript
const YTArchive = require('ytarchive-js');

const client = new YTArchive.Client({
  baseURL: 'http://localhost:8001'
});

// Create and monitor download
async function downloadVideo(videoId) {
  const job = await client.jobs.createDownloadJob({
    videoId: videoId,
    quality: '720p'
  });

  // Monitor progress
  const progressInterval = setInterval(async () => {
    const status = await client.jobs.getJob(job.jobId);
    console.log(`Progress: ${status.progress}%`);

    if (status.status === 'completed') {
      clearInterval(progressInterval);
      console.log('Download completed!');
    }
  }, 1000);
}
```

---

# Testing API Endpoints

## Using curl

```bash
# Health check
curl http://localhost:8001/health

# Create download job
curl -X POST http://localhost:8001/jobs \
  -H "Content-Type: application/json" \
  -d '{"video_id": "dQw4w9WgXcQ", "quality": "720p"}'

# Get metadata
curl http://localhost:8002/metadata/dQw4w9WgXcQ

# Check storage stats
curl http://localhost:8004/stats
```

## Using Postman

Import the YTArchive Postman collection:
- Download: [ytarchive-api.postman_collection.json](./ytarchive-api.postman_collection.json)
- Set environment variable: `base_url` = `http://localhost`

---

*YTArchive API Documentation - Production Ready YouTube Archiving*
