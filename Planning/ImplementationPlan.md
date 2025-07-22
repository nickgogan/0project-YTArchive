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
- [ ] Initialize Git repository with proper `.gitignore`
- [ ] Install dependencies using `uv sync`
- [ ] Create initial test structure
- [ ] Set up pre-commit hooks (black, ruff, mypy)
- [ ] Configure VS Code settings for project

### 1.2 Common Infrastructure (Days 1-2)
- [ ] Implement service base class (`services/common/base.py`)
  - Configuration loading from TOML
  - Health check endpoint
  - Graceful shutdown handling
  - Basic HTTP server setup
- [ ] Implement shared utilities (`services/common/utils.py`)
  - Path validation functions
  - Retry logic with exponential backoff
  - Circuit breaker implementation
- [ ] Create test fixtures and mocks

### 1.3 Logging Service (Days 2-3)
- [ ] Implement core logging service
  - POST `/api/v1/logs` endpoint
  - GET `/api/v1/logs` with filtering
  - Log rotation and retention
- [ ] Create structured logging client for other services
- [ ] Add basic log viewer CLI command
- [ ] Write unit tests

### 1.4 Jobs Service Core (Days 3-5)
- [ ] Implement job creation and storage
  - POST `/api/v1/jobs` endpoint
  - File-based job persistence
  - Job status tracking
- [ ] Service registry functionality
  - POST `/api/v1/registry/register`
  - GET `/api/v1/registry/services`
  - Health check monitoring
- [ ] Basic job execution (synchronous)
- [ ] Write comprehensive tests

## Phase 2: Core Services (Week 2)

### 2.1 Storage Service (Days 6-7)
- [ ] Implement path management
  - GET `/api/v1/storage/check/{video_id}`
  - POST `/api/v1/storage/prepare/{video_id}`
  - GET `/api/v1/storage/path/{video_id}`
- [ ] Disk space validation
- [ ] File organization logic
- [ ] Integration with Jobs service

### 2.2 Metadata Service (Days 8-9)
- [ ] YouTube API client wrapper
  - Quota tracking
  - Automatic retry with backoff
- [ ] Video metadata endpoint
  - GET `/api/v1/metadata/video/{video_id}`
- [ ] Playlist metadata endpoint
  - GET `/api/v1/metadata/playlist/{playlist_id}`
- [ ] Metadata caching to reduce API calls
- [ ] Integration tests with mock YouTube API

### 2.3 Download Service Core (Days 10-12)
- [ ] yt-dlp integration
  - POST `/api/v1/download/video`
  - Progress tracking implementation
  - Error handling for common failures
- [ ] Thumbnail download support
- [ ] Caption extraction (English only)
- [ ] Integration with Storage service for paths
- [ ] Integration with Jobs service for status updates

## Phase 3: CLI and Integration (Week 3)

### 3.1 CLI Implementation (Days 13-14)
- [ ] Basic CLI structure with Click
- [ ] Commands:
  - `ytarchive download <video_id>`
  - `ytarchive metadata <video_id>`
  - `ytarchive status <job_id>`
  - `ytarchive logs`
- [ ] Configuration file support
- [ ] Progress display for downloads

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


