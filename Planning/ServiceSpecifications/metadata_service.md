# Metadata Service Specification

## Overview
The Metadata Service interfaces with the YouTube Data API to fetch video and playlist metadata. It manages API quota usage and provides metadata to other services.

## Service Configuration
- **Port**: 8001
- **Host**: localhost (configurable)
- **Dependencies**: YouTube Data API

## API Endpoints

### Video Metadata

#### Get Video Metadata
```
GET /api/v1/metadata/video/{video_id}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "video_id": "dQw4w9WgXcQ",
    "title": "Video Title",
    "description": "Video description...",
    "duration": 212,
    "upload_date": "2009-10-25T06:57:33Z",
    "channel_id": "UCuAXFkgsw1L7xaCfnd5JJOw",
    "channel_title": "Channel Name",
    "thumbnail_urls": {
      "default": "https://i.ytimg.com/vi/dQw4w9WgXcQ/default.jpg",
      "medium": "https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg",
      "high": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
      "standard": "https://i.ytimg.com/vi/dQw4w9WgXcQ/sddefault.jpg",
      "maxres": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
    },
    "available_captions": ["en", "es", "fr"],
    "view_count": 1234567890,
    "like_count": 9876543,
    "fetched_at": "2024-01-01T00:00:00Z"
  },
  "trace_id": "uuid"
}
```

### Playlist Metadata

#### Get Playlist Metadata
```
GET /api/v1/metadata/playlist/{playlist_id}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "playlist_id": "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf",
    "title": "Playlist Title",
    "description": "Playlist description...",
    "channel_id": "UCuAXFkgsw1L7xaCfnd5JJOw",
    "channel_title": "Channel Name",
    "video_count": 25,
    "videos": [
      {
        "video_id": "dQw4w9WgXcQ",
        "position": 0,
        "title": "Video Title",
        "duration": 212,
        "is_available": true
      }
    ],
    "fetched_at": "2024-01-01T00:00:00Z"
  },
  "trace_id": "uuid"
}
```

### Batch Operations

#### Batch Fetch Metadata
```
POST /api/v1/metadata/batch
```

**Request Body**:
```json
{
  "video_ids": ["video_id1", "video_id2", "video_id3"]
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "metadata": [
      { /* video metadata */ },
      { /* video metadata */ }
    ],
    "failed": [
      {
        "video_id": "video_id3",
        "error": "Video unavailable"
      }
    ]
  },
  "trace_id": "uuid"
}
```

### Quota Management

#### Get Quota Status
```
GET /api/v1/metadata/quota
```

**Response**:
```json
{
  "success": true,
  "data": {
    "quota_limit": 10000,
    "quota_used": 2500,
    "quota_remaining": 7500,
    "reset_time": "2024-01-02T00:00:00Z",
    "operations_available": {
      "video_metadata": 7500,
      "playlist_metadata": 7500,
      "playlist_items": 7500,
      "captions": 150  // 50 units per request
    }
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
from typing import List, Optional, Dict
from datetime import datetime
from pydantic import BaseModel, Field

class VideoMetadata(BaseModel):
    video_id: str
    title: str
    description: str
    duration: int  # seconds
    upload_date: datetime
    channel_id: str
    channel_title: str
    thumbnail_urls: Dict[str, str]  # quality -> url
    available_captions: List[str] = []  # language codes
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    fetched_at: datetime

class PlaylistVideo(BaseModel):
    video_id: str
    position: int
    title: str
    duration: Optional[int] = None
    is_available: bool = True
    added_at: Optional[datetime] = None

class PlaylistMetadata(BaseModel):
    playlist_id: str
    title: str
    description: str
    channel_id: str
    channel_title: str
    video_count: int
    videos: List[PlaylistVideo]
    fetched_at: datetime

class BatchFetchRequest(BaseModel):
    video_ids: List[str] = Field(..., min_items=1, max_items=50)

class BatchFetchResponse(BaseModel):
    metadata: List[VideoMetadata]
    failed: List[Dict[str, str]]

class QuotaStatus(BaseModel):
    quota_limit: int
    quota_used: int
    quota_remaining: int
    reset_time: datetime
    operations_available: Dict[str, int]
```

## YouTube API Integration

### API Methods Used
```python
# Video metadata
youtube.videos().list(
    part="snippet,contentDetails,status,statistics",
    id=video_id
)

# Playlist metadata
youtube.playlists().list(
    part="snippet,contentDetails",
    id=playlist_id
)

# Playlist items
youtube.playlistItems().list(
    part="snippet,contentDetails",
    playlistId=playlist_id,
    maxResults=50
)

# Captions
youtube.captions().list(
    part="snippet",
    videoId=video_id
)
```

### Quota Costs
- `videos.list`: 1 unit per call
- `playlists.list`: 1 unit per call
- `playlistItems.list`: 1 unit per call
- `captions.list`: 50 units per call

### Quota Management Strategy
1. Check quota before each API call
2. Reserve 1000 units for emergencies
3. Batch requests when possible (up to 50 video IDs)
4. Cache responses to avoid duplicate calls
5. Track daily usage and reset time

## Configuration

### Environment Variables
- `YOUTUBE_API_KEY`: Required for YouTube Data API access

### Config File Settings
```toml
[services.metadata]
host = "localhost"
port = 8001
cache_ttl = 3600  # seconds
max_batch_size = 50

[youtube]
quota_limit = 10000
quota_reserve = 1000
```

## Error Scenarios

### Common Errors
- `E001`: API quota exceeded
- `E002`: Video unavailable (private, deleted, or region-blocked)
- `E005`: Invalid credentials (API key issues)
- `E007`: Invalid request (malformed video/playlist ID)

### Error Handling
- Quota exceeded: Return cached data if available
- Video unavailable: Mark as unavailable with reason
- Invalid credentials: Fail fast with clear error
- Network errors: Retry with exponential backoff

## Caching Strategy
- Cache all successful API responses
- TTL: 1 hour for video metadata, 30 minutes for playlists
- Cache key: `{type}:{id}:{timestamp}`
- Storage: In-memory (consider Redis for production)

## Metrics

The Metadata service tracks:
- Total API calls by type
- Quota usage and remaining
- Cache hit/miss ratio
- Average response time
- Failed requests by error type

## Example Usage

### Get Video Metadata
```bash
curl http://localhost:8001/api/v1/metadata/video/dQw4w9WgXcQ
```

### Get Playlist Information
```bash
curl http://localhost:8001/api/v1/metadata/playlist/PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf
```

### Batch Fetch Videos
```bash
curl -X POST http://localhost:8001/api/v1/metadata/batch \
  -H "Content-Type: application/json" \
  -d '{
    "video_ids": ["dQw4w9WgXcQ", "video_id2", "video_id3"]
  }'
```

### Check Quota Status
```bash
curl http://localhost:8001/api/v1/metadata/quota
```
