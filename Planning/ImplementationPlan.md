# YTArchive Implementation Plan

This document outlines the prioritized implementation plan for the YTArchive project, organized in phases with clear deliverables and estimated timelines.

## Overview

### Implementation Philosophy
- Start with foundational services and build incrementally
- Each service should be independently testable
- Focus on MVP features first, defer advanced functionality
- Maintain clean service boundaries throughout

### Critical Path
Jobs Service → Logging Service → Storage Service → Metadata Service → Download Service → CLI

## Phase 1: Foundation (Week 1)

### 1.1 Project Setup (Day 1)
- [x] Initialize Git repository with proper `.gitignore`
- [x] Install dependencies using `uv sync`
- [x] Create initial test structure
- [x] Set up pre-commit hooks (black, ruff, mypy)
- [x] Configure VS Code settings for project

### 1.2 Common Infrastructure (Days 1-2)
- [x] Implement service base class (`services/common/base.py`)
  - Configuration loading with Pydantic Settings
  - Health check endpoint
  - Graceful shutdown handling (placeholder)
  - Basic HTTP server setup with uvicorn
- [x] Implement shared utilities (`services/common/utils.py`)
  - Path validation functions (placeholder)
  - Retry logic with exponential backoff
  - Circuit breaker implementation
- [x] Create test fixtures and mocks

### 1.3 Logging Service (Days 2-3)
- [x] Implement core logging service
  - [x] POST `/log` endpoint for receiving log messages
  - [x] GET `/logs` endpoint with filtering (by service, level, log_type, date, limit)
  - [x] Log rotation and retention (daily log files)
  - [x] Directory-based log organization (runtime, failed_downloads, error_reports)
- [x] Create structured logging models for other services (LogMessage, LogType, LogLevel)
- [x] Write unit tests

### 1.4 Jobs Service Core (Days 3-5)
- [x] Implement job creation and management
  - POST `/api/v1/jobs` endpoint
  - In-memory job storage (enhanced to file-based in Phase 2.1)
  - Job status tracking
- [x] Service registry functionality
  - POST `/api/v1/registry/register`
  - GET `/api/v1/registry/services`
  - DELETE `/api/v1/registry/services/{service_name}`
  - Health check monitoring
- [x] Basic job execution (synchronous)
  - PUT `/api/v1/jobs/{job_id}/execute`
  - Job status lifecycle (PENDING → RUNNING → COMPLETED/FAILED)
  - Basic processing for VIDEO_DOWNLOAD, PLAYLIST_DOWNLOAD, METADATA_ONLY
- [x] Write comprehensive tests

**Phase 1.4 Status: ✅ COMPLETED**

## Phase 2: Core Services (Week 2)

### 2.1 Storage Service (Days 6-7)
- [x] **Complete storage service implementation**
  - POST `/api/v1/storage/save/metadata` - Store video metadata with timestamps
  - POST `/api/v1/storage/save/video` - Track video file information
  - GET `/api/v1/storage/exists/{video_id}` - Comprehensive existence checking
  - GET `/api/v1/storage/metadata/{video_id}` - Retrieve stored metadata
  - POST `/api/v1/storage/work-plan` - Generate work plans for failed downloads
  - GET `/api/v1/storage/stats` - Storage statistics with disk usage metrics
- [x] **File system organization**
  - Proper directory structure creation (~/YTArchive/, metadata/, videos/, work_plans/)
  - Video file existence checking (video, metadata, thumbnails, captions)
  - JSON serialization with datetime handling
- [x] **Error handling and validation**
  - Comprehensive error handling (404 for missing files, 500 for server errors)
  - Type-safe implementation passing mypy validation
- [x] **Testing and quality**
  - Full test coverage with 14 tests including edge cases and error scenarios
  - All tests passing with no warnings
  - Code formatted and linted (Black, Ruff, mypy)

**Phase 2.1 Status: ✅ COMPLETED**

### 2.2 Metadata Service (Days 8-9)
- [x] **YouTube API integration**
  - Complete MetadataService implementation with google-api-python-client
  - Quota management (10,000 daily limit with 1,000 reserve)
  - Exponential backoff retry for network errors
  - Proper authentication with YOUTUBE_API_KEY environment variable
- [x] **API endpoints implementation**
  - GET `/api/v1/metadata/video/{video_id}` - Single video metadata with full details
  - GET `/api/v1/metadata/playlist/{playlist_id}` - Playlist metadata with video list
  - POST `/api/v1/metadata/batch` - Batch processing up to 50 video IDs
  - GET `/api/v1/metadata/quota` - Real-time quota status tracking
  - GET `/health` - Service health check endpoint
- [x] **Advanced features**
  - In-memory caching with TTL (1hr videos, 30min playlists)
  - Duration parsing from ISO 8601 format (PT3M33S → 213 seconds)
  - Thumbnail URL extraction from nested API response structure
  - Private video detection in playlists
  - Comprehensive error handling (quota exceeded, unavailable videos)
- [x] **Testing and quality**
  - Comprehensive test suite with 17 tests covering all endpoints
  - Mocked YouTube API responses for reliable testing
  - Edge cases including quota limits, caching, and error scenarios
  - Type-safe implementation with proper Pydantic models

**Phase 2.2 Status: ✅ COMPLETED**

### 2.3 Download Service Core (Days 10-12)
- [x] yt-dlp integration
  - POST `/api/v1/download/video`
  - GET `/api/v1/download/progress/{task_id}`
  - POST `/api/v1/download/cancel/{task_id}`
  - GET `/api/v1/download/formats/{video_id}`
  - Progress tracking implementation
  - Error handling for common failures
- [x] Thumbnail download support
- [x] Caption extraction (English only)
- [x] Quality selection (best, 1080p, 720p, 480p, 360p, audio)
- [x] Concurrent download management with semaphore
- [x] Background task lifecycle management
- [x] Comprehensive test suite with 21 tests
- [ ] Integration with Storage service for paths (Phase 3)
- [ ] Integration with Jobs service for status updates (Phase 3)

**Phase 2.3 Status: ✅ COMPLETED**

## Phase 3: CLI and Integration (Week 3)

### 3.1 CLI Implementation (Days 13-14)
- [x] Basic CLI structure with Click
- [x] Commands:
  - `ytarchive download <video_id>` (with quality selection, output path, metadata-only mode)
  - `ytarchive metadata <video_id>` (with formatted and JSON output)
  - `ytarchive status <job_id>` (with watch mode for continuous monitoring)
  - `ytarchive logs` (with service/level filtering and follow mode)
- [x] Add basic log viewer CLI command (from logging service)
- [x] Progress display for downloads (real-time progress bars with speed/ETA)
- [x] Rich terminal UI with colors, tables, and panels
- [x] Comprehensive error handling and input validation
- [x] Full async API integration with all services
- [x] Comprehensive test suite with 28 passing tests
- [ ] Configuration file support (deferred to future enhancement)

**Phase 3.1 Status: ✅ COMPLETED**

### 3.2 End-to-End Integration (Days 15-16)
- [ ] Full workflow testing:
  1. CLI creates job
  2. Jobs service coordinates
  3. Metadata fetched
  4. Storage prepared
  5. Video downloaded
  6. Progress reported
- [ ] Error scenario testing
- [ ] Performance profiling

### 3.3 Work Plan Service (Days 17-18)
- [ ] Implement work plan generation
  - Track unavailable videos
  - Document failed downloads
  - Generate retry recommendations
- [ ] Integration with Jobs service
- [ ] CLI command for work plan review

## Phase 4: Polish and MVP Release (Week 4)

### 4.1 Testing and Bug Fixes (Days 19-20)
- [ ] Comprehensive integration testing
- [ ] Fix identified bugs
- [ ] Performance optimization
- [ ] Memory leak detection

### 4.2 Documentation (Days 21-22)
- [ ] User guide with examples
- [ ] API documentation
- [ ] Service deployment guide
- [ ] Configuration reference

### 4.3 MVP Release Preparation (Days 23-24)
- [ ] Create release scripts
- [ ] Package for distribution
- [ ] Final testing on clean environment
- [ ] Tag v0.1.0 release

## Phase 5: Enhanced Features (Weeks 5-6)

### 5.1 Playlist Support (Days 25-27)
- [ ] Extend CLI for playlist downloads
- [ ] Batch job creation in Jobs service
- [ ] Playlist progress tracking
- [ ] Optimize for large playlists

### 5.2 Advanced Error Recovery (Days 28-30)
- [ ] Implement job retry with different strategies
- [ ] Partial download resume
- [ ] Automatic quality fallback
- [ ] Enhanced error reporting

### 5.3 Performance Enhancements (Days 31-33)
- [ ] Implement connection pooling
- [ ] Add caching layer for metadata
- [ ] Optimize file I/O operations
- [ ] Profile and optimize hot paths

### 5.4 Monitoring and Observability (Days 34-36)
- [ ] Add Prometheus metrics export
- [ ] Create service dashboards
- [ ] Implement distributed tracing
- [ ] Add performance benchmarks

## Implementation Guidelines

### Code Standards
1. All code must pass `mypy --strict`
2. Test coverage minimum: 80%
3. All public APIs must have docstrings
4. Use type hints throughout

### Testing Strategy
1. Unit tests for all business logic
2. Integration tests for service communication
3. End-to-end tests for critical paths
4. Mock external dependencies (YouTube API, file system)

### Daily Workflow
1. Review planned tasks
2. Write tests first (TDD)
3. Implement feature
4. Update documentation
5. Commit with descriptive message
6. Update CHANGELOG.md

### Definition of Done
- [ ] Feature is implemented and working
- [ ] Unit tests written and passing
- [ ] Integration tests updated
- [ ] Documentation updated
- [ ] Code reviewed (self-review for solo project)
- [ ] No linting errors
- [ ] Type checking passes

## Risk Mitigation

### Technical Risks
1. **YouTube API Changes**
   - Mitigation: Abstract API calls, version pin yt-dlp

2. **Service Communication Failures**
   - Mitigation: Implement circuit breakers, comprehensive retries

3. **Large File Handling**
   - Mitigation: Stream downloads, implement progress tracking

### Schedule Risks
1. **Underestimated Complexity**
   - Mitigation: MVP first, defer advanced features

2. **External Dependencies**
   - Mitigation: Mock everything, test offline

## Success Metrics

### MVP (v0.1.0)
- Successfully download single videos
- Handle common error cases gracefully
- All services communicate reliably
- Basic CLI is functional

### v0.2.0
- Playlist support working
- 95%+ download success rate
- Performance meets requirements (<1GB memory)
- Comprehensive test coverage

## Next Steps

1. Begin with Phase 1.1 - Project Setup
2. Set up development environment
3. Create initial commit with project structure
4. Start implementing common infrastructure

Remember: Focus on getting a working MVP first. Advanced features can always be added later.
