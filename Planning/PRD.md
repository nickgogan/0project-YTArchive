# YouTube Archive - Product Requirements Document

## Executive Summary

YouTube Archive is a Python-based personal archiving tool designed to backup YouTube content and metadata. The tool provides a CLI interface for extracting video metadata, downloading videos, and organizing content in a structured local file system.

## Project Overview

### Vision
Create a reliable, efficient tool for personal YouTube content archiving that respects API rate limits while providing comprehensive backup capabilities.

### Goals
- Archive personal YouTube content with metadata preservation
- Provide flexible access via CLI
- Maintain organized local storage structure
- Handle errors gracefully with progress tracking

### Non-Goals
- Public distribution or multi-user support
- Real-time monitoring or scheduling
- Analytics or data analysis features
- Content migration capabilities

## User Personas

### Primary User
- **Role**: Content Owner/Individual User
- **Technical Level**: Developer/Technical
- **Use Case**: Personal backup of owned YouTube content
- **Access Method**: CLI

## Functional Requirements

### Core Features (MVP)

#### 1. Metadata Extraction Service
- **Video Metadata**
  - Title, description, duration, upload date
  - Video ID and URL
  - Available quality options
- **Playlist Information**
  - Playlist structure and organization
  - Video ordering within playlists
  - Playlist metadata (name, description)
- **Additional Assets**
  - Thumbnail images (all available resolutions)
  - Captions/subtitles (English only)

#### 2. Video Download Service
- **Download Capabilities**
  - Single video download (1080p quality)
  - Progress tracking with real-time updates
  - Error handling with automatic retry (3 attempts)
  - Support for interrupted download detection
- **Format Support**
  - Automatic format selection (prefer mp4)
  - Fallback to best available format

#### 3. Storage Management
- **File Organization**
  ```
  YTArchive/
  ├── metadata/
  │   ├── videos/
  │   │   └── {video_id}.json
  │   ├── playlists/
  │   │   └── {playlist_id}.json
  │   └── work_plans/
  │       └── {timestamp}_plan.json
  ├── videos/
  │   └── {video_id}/
  │       ├── video.mp4
  │       ├── thumbnail.jpg
  │       └── captions/
  │           └── en.vtt
  └── logs/
      ├── runtime/
      │   └── {timestamp}_runtime.log
      ├── failed_downloads/
      │   └── {timestamp}_failed.json
      └── error_reports/
          └── {timestamp}_errors.json
  ```

#### 4. Work Plan Service
- Document unavailable content (private/deleted videos)
- Track failed downloads with reasons
- Generate actionable reports for manual intervention

#### 5. API Rate Limit Management
- Implement exponential backoff
- Track quota usage
- Provide warnings when approaching limits

### Interface Specifications

#### CLI Interface
```bash
# Basic commands
ytarchive download <video_id>
ytarchive playlist <playlist_id>
ytarchive metadata <video_id|playlist_id>

# Options
--output-dir, -o: Specify output directory
--quality, -q: Video quality (default: 1080p)
--metadata-only: Skip video download
--api-key: YouTube API key
```

### Future Enhancements (Version 2+)

1. **Batch Operations**
   - Channel-wide archiving
   - Parallel downloads
   - Bulk metadata extraction

2. **Advanced Download Features**
   - Resume capability for interrupted downloads
   - Quality selection options
   - Audio extraction option

3. **Cloud Integration**
   - AWS S3 backup
   - Google Drive sync
   - Automated cloud upload

4. **Enhanced Management**
   - Duplicate detection
   - Storage optimization
   - Archive verification

## Technical Requirements

### Technology Stack
- **Language**: Python 3.11+
- **Package Manager**: uv
- **Key Libraries**:
  - `google-api-python-client` (YouTube Data API)
  - `yt-dlp` (video downloads)
  - `click` (CLI)
  - `pydantic` (data validation)
  - `httpx` (async HTTP)

### Performance Requirements
- Handle up to 500 videos
- Single-threaded operation (MVP)
- Memory usage < 1GB
- Graceful degradation under API limits

### Security & Compliance
- API keys stored in environment variables
- No credential storage in code
- Respect content ownership
- Honor video availability status

## Success Metrics

### Primary Metrics
- Successful download rate > 95%
- Zero data corruption
- API quota efficiency (< 80% usage)

### Secondary Metrics
- Average download time per video
- Storage efficiency
- Error recovery rate

## Project Phases

### Phase 1: MVP (Weeks 1-2)
- Basic CLI implementation
- Metadata extraction
- Single video download
- Error handling
- Progress tracking

### Phase 2: API & Enhanced Features (Weeks 3-4)
- Playlist support
- Work plan service

### Phase 3: Optimization (Week 5)
- Performance improvements
- Storage optimization
- Documentation
- Testing suite

## Risk Mitigation

### Technical Risks
- **API Rate Limits**: Implement robust backoff and quota tracking
- **Download Failures**: Retry mechanism with fallback options
- **Storage Space**: Clear space requirements documentation

### Operational Risks
- **API Changes**: Abstract API calls for easy updates
- **Format Changes**: Use yt-dlp for compatibility

## Dependencies

### External Dependencies
- YouTube Data API v3 access
- Stable internet connection
- Sufficient local storage

### Internal Dependencies
- Python 3.11+ environment
- uv package manager

## Appendix

### API Quota Calculations
- Metadata fetch: 1 unit per video
- Playlist fetch: 1 unit per 50 videos
- Daily quota: 10,000 units (default)
- Estimated capacity: ~9,000 videos/day (metadata only)

### Storage Estimates
- Average video (1080p): 200MB
- Metadata + thumbnails: 1MB
- 500 videos ≈ 100GB required

### Error Codes
- `E001`: API quota exceeded
- `E002`: Video unavailable
- `E003`: Network timeout
- `E004`: Storage full
- `E005`: Invalid credentials