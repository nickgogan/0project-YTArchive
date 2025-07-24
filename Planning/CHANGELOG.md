# Changelog

All notable changes to the YTArchive project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Set up foundational project infrastructure:
  - Established a stable Python 3.12 environment with `uv`.
  - Configured Git, `.gitignore`, and VS Code settings.
  - Implemented automated code quality checks with `pre-commit` (Black, Ruff, Mypy).
  - Created initial `pytest` structure for testing.
- Created comprehensive planning and design documentation:
  - Product Requirements Document (PRD.md)
  - Architecture and Implementation Guides
  - Detailed Service Specifications
  - Future Features roadmap (FutureFeatures.md)
- Service specifications for:
  - Jobs Service (port 8000) - Central coordinator
  - Metadata Service (port 8001) - YouTube API integration
  - Download Service (port 8002) - Video downloading with yt-dlp
  - Storage Service (port 8003) - File system management
  - Logging Service (port 8004) - Centralized logging
- **Common Infrastructure (Phase 1.2)**:
  - `BaseService` class for consistent service architecture with FastAPI integration
  - Pydantic-based configuration management with environment support
  - Retry logic with exponential backoff decorator for resilient operations
  - Circuit breaker implementation for fault tolerance
  - Comprehensive test fixtures and mocks for service testing
  - Health check endpoints for all services
- **Logging Service (Phase 1.3)**:
  - Centralized logging service with REST API (`/log` endpoint for writing, `/logs` endpoint for reading)
  - Log retrieval with advanced filtering capabilities (by service, level, log_type, date, and result limit)
  - Structured log storage with JSON format in daily files
  - Directory-based log organization (runtime, failed_downloads, error_reports)
  - `LogMessage`, `LogType`, and `LogLevel` models for inter-service logging
  - Comprehensive unit tests covering API endpoints and file operations
- **Jobs Service Core (Phase 1.4)**:
  - Complete jobs management and service registry
  - POST /api/v1/jobs endpoint for job creation with file-based persistence
  - GET /api/v1/jobs/{job_id} endpoint for job retrieval by ID
  - GET /api/v1/jobs endpoint for listing jobs with optional status filtering
  - PUT /api/v1/jobs/{job_id}/execute endpoint for job execution with status tracking
  - Basic synchronous job processing for VIDEO_DOWNLOAD, PLAYLIST_DOWNLOAD, and METADATA_ONLY
  - Job status lifecycle management (PENDING → RUNNING → COMPLETED/FAILED)
  - POST /api/v1/registry/register endpoint for service registration
  - GET /api/v1/registry/services endpoint for listing registered services
  - DELETE /api/v1/registry/services/{service_name} endpoint for service unregistration
  - Service health check infrastructure for monitoring registered services
  - JobResponse and ServiceRegistration models for structured data exchange
  - Comprehensive test coverage for job management, execution, and service registry
- **Storage Service (Phase 2.1)**:
  - Complete file system organization and metadata management service
  - POST /api/v1/storage/save/metadata endpoint for storing video metadata with timestamps
  - POST /api/v1/storage/save/video endpoint for tracking video file information
  - GET /api/v1/storage/exists/{video_id} endpoint for comprehensive existence checking
  - GET /api/v1/storage/metadata/{video_id} endpoint for retrieving stored metadata
  - POST /api/v1/storage/work-plan endpoint for generating work plans for failed downloads
  - GET /api/v1/storage/stats endpoint for storage statistics with disk usage metrics
  - Proper directory structure creation (~/YTArchive/, metadata/, videos/, work_plans/)
  - Video file existence checking (video, metadata, thumbnails, captions)
  - JSON serialization with proper datetime handling using Pydantic model_dump(mode='json')
  - Comprehensive error handling (404 for missing files, 500 for server errors)
  - Full test coverage with 14 tests including edge cases and error scenarios
  - Type-safe implementation passing mypy validation
- **Metadata Service** - Complete YouTube API integration implementation
  - API endpoints: video/{video_id}, playlist/{playlist_id}, batch, quota, health
  - YouTube Data API integration with proper authentication
  - Quota management (10,000 daily limit with 1,000 reserve)
  - In-memory caching with TTL (1hr videos, 30min playlists)
  - Batch processing up to 50 video IDs
  - Exponential backoff retry for network errors
  - Duration parsing from ISO 8601 format
  - Private video detection in playlists
  - Comprehensive error handling and type safety
  - Comprehensive testing (17 tests, all passing with no warnings)
  - Code quality validation (Black, Ruff, mypy)
- **Download Service** - Complete yt-dlp integration for video downloads
  - API endpoints: video download, progress tracking, cancellation, format querying
  - Full yt-dlp integration with async task-based downloads
  - Real-time progress tracking with callback hooks
  - Quality selection (best, 1080p, 720p, 480p, 360p, audio)
  - Thumbnail and caption extraction support
  - Concurrent download management (max 3 simultaneous with semaphore)
  - Background task lifecycle management to prevent async warnings
  - Task cancellation and cleanup mechanisms
  - Thread pool execution for blocking yt-dlp operations
  - Comprehensive testing (21 tests, 100% pass rate)
  - Type-safe implementation with proper async task management
- **CLI Implementation** - Complete command-line interface with Rich terminal UI
  - Core CLI commands: download, metadata, status, logs with full service integration
  - Rich terminal UI with colors, progress bars, tables, panels, and formatted output
  - Quality selection for downloads (best, 1080p, 720p, 480p, 360p, audio)
  - Real-time progress tracking with speed, ETA, and percentage display
  - Async API integration with all microservices (Jobs, Metadata, Download, Storage, Logging)
  - Advanced features: watch mode for status/logs, JSON output, service/level filtering
  - Comprehensive error handling with user-friendly messages
  - Input validation using Click framework decorators
  - Entry point script (ytarchive.py) for easy CLI execution
  - Comprehensive testing (28 tests, 100% pass rate)
  - Type-safe implementation with mypy compliance
- **Phase 3.2 End-to-End Integration Testing** - 2025-07-23

### Added
- **Integration Test Framework**: Comprehensive service coordination validation
  - `test_service_coordination.py` - 10 integration tests covering all service interactions
  - Jobs ↔ Storage service integration testing
  - Download service task management validation
  - Storage service batch operations and data integrity
  - Error handling across service boundaries
- **Performance Testing**: Response time validation and throughput benchmarking
- **Service Coordination**: Validated complete workflows from job creation to completion
- **Test Infrastructure**: Isolated test environments with proper fixture management

### Technical Details
- **Implementation**: Comprehensive integration tests without external dependencies
- **Testing**: 10/10 core integration tests passing + 113 total tests passing across all services
- **Coverage**: Job lifecycle, storage operations, download management, error scenarios
- **Performance**: Service response times <100ms for core operations
- **Service Coordination**: Jobs ↔ Storage ↔ Download service integration fully validated
- **Data Integrity**: Persistence and consistency verified across service boundaries

### Key Achievements
- **Robust Integration Framework**: Created scalable test infrastructure for service coordination
- **Performance Benchmarking**: Validated response times and throughput characteristics
- **Error Handling**: Comprehensive error scenario testing across all service boundaries
- **Service Lifecycle**: Complete job creation, processing, and completion workflows tested
- **Data Consistency**: Verified data persistence and integrity across all services

### Status
✅ **PHASE 3.2 COMPLETED (2025-07-23)** - All integration objectives achieved with 113/113 core tests passing

---

## [Phase 3.3] - Work Plan Service - 2025-07-24

### Added
- **Work Plan CLI Commands**: Complete work plan management interface
  - `ytarchive workplan list` - List all work plans with Rich table formatting
  - `ytarchive workplan show <plan_id>` - Display detailed work plan information
  - `ytarchive workplan create` - Create work plans from failed/unavailable videos
  - JSON output support for all commands
  - Rich terminal UI with colors, tables, and panels
- **Jobs Service Integration**: Automatic work plan generation for failed jobs
  - Enhanced `_update_job_status` method with error details tracking
  - `_add_to_work_plan` method for automatic work plan entries
  - Video ID extraction from YouTube URLs
  - Integration with Storage Service work plan API
- **Comprehensive Testing**: Full test coverage for work plan functionality
  - 12 CLI work plan command tests
  - Mock-based testing for reliable isolated testing
  - Error scenario and edge case coverage

### Technical Details
- **Implementation**: Work plan generation already existed in Storage Service, added CLI and Jobs integration
- **CLI Commands**: 3 new commands with full async implementation and Rich UI
- **Jobs Integration**: Failed jobs automatically create work plan entries with error details
- **Testing Coverage**: Comprehensive test suite covering all work plan CLI functionality
- **Error Handling**: Graceful failure handling with user-friendly error messages

### Key Achievements
- **Complete Work Plan Workflow**: From job failure to work plan creation to CLI review
- **Rich CLI Interface**: Beautiful terminal UI for work plan management
- **Automated Tracking**: Failed jobs automatically captured for review and retry
- **Service Integration**: Seamless integration between Jobs, Storage, and CLI layers
- **Comprehensive Testing**: Full test coverage ensuring reliability
- **Test Suite Cleanup and Optimization (Phase 3.4)**:
  - **67% reduction in runtime warnings** (from 3 warnings to 1)
  - **127 passing tests** with 99.2% clean execution
  - Fixed all AsyncMock warnings in jobs service tests using proper Mock/AsyncMock patterns
  - Enhanced CLI exception handling with robust `safe_error_message` utility
  - Fixed critical `test_health_check` failure using proper `pytest_asyncio.fixture`
  - Improved test mocking patterns for async HTTP clients and coroutine handling
  - Only 1 remaining warning (test execution artifact, no functional impact)
  - Achieved near-perfect test suite reliability and maintainability

### Status
✅ **PHASE 3.3 COMPLETED (2025-07-24)** - Work plan service fully integrated with jobs and CLI

### Changed
- Consolidated planning documentation to eliminate overlap
- Renamed and reorganized planning files for clarity:
  - ArchitectureDecisions.md → ArchitectureGuide.md (high-level only)
  - DesignDecisions.md → merged into ImplementationGuide.md
  - DeferredDesignDetails.md → FutureFeatures.md (future only)
  - ServicesSpecification.md → individual files in ServiceSpecifications/
- Updated service models to use proper typing and Pydantic BaseModel
- Clarified service responsibilities and API contracts

### Completed
- **Phase 1 Infrastructure Complete** - All foundation services implemented and tested
- Common infrastructure with BaseService, retry logic, and circuit breaker
- Centralized logging service with structured log management
- Jobs service with execution capability and service registry
- **Phase 2.1 Storage Service Complete** - File system organization and metadata management implemented and tested
- **Phase 2.2 Metadata Service Complete** - YouTube API integration implemented and tested

### Architecture Decisions
- Microservices architecture with HTTP/REST communication
- Jobs service as central coordinator (orchestration pattern)
- Fixed port assignments for service discovery
- TOML configuration with environment variable overrides
- File-based storage for jobs and metadata (no database in v1)
- Structured JSON logging with centralized collection
- Exponential backoff retry strategy with manual intervention fallback
- Service health checks and registry in Jobs service

### Technical Decisions
- Python 3.11+ with type hints throughout
- FastAPI for service APIs
- httpx for inter-service communication
- yt-dlp for video downloading
- Pydantic for data validation
- structlog for structured logging
- pytest for testing framework
- uv for package management
- Compatible version pinning (~=) for dependencies

## [0.1.0] - TBD

### Planned for Initial Release
- CLI implementation with basic commands
- Core service functionality:
  - Single video download
  - Playlist metadata extraction
  - Progress tracking
  - Error handling and retry logic
- Basic storage organization
- Service health monitoring
- Structured logging implementation

---

## Decision History

### 2024-01-22
- **Microservices architecture**: Clear boundaries, easier to maintain and scale
- **TOML for configuration**: Python-friendly, supports complex structures
- **Fixed ports with config override**: Simple discovery, predictable locations
- **Compatible version pinning (~=)**: Balance stability with security updates
- **No caching in v1**: Simplify initial implementation
- **File-based job storage**: Simple, portable, no database dependencies
- **Centralized logging service**: Single place to query all service logs
- **HTTP/REST over gRPC**: Simpler implementation, better debugging
- **Jobs service orchestration**: Central coordination vs choreography
- **Monorepo structure**: Easier dependency management, consistent versions

### Planning Consolidation (Current)
- **Separated concerns**: Architecture vs Implementation vs Service specs
- **Eliminated overlap**: Each document has distinct purpose
- **Created service specifications**: Individual docs for each service
- **Consolidated implementation details**: Single source of truth in ImplementationGuide.md
- **Archived redundant files**: Moved to Planning/Archive/
