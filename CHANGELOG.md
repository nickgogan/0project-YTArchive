# Changelog

All notable changes to the YTArchive project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project structure with five microservices architecture
- Comprehensive planning documentation:
  - Product Requirements Document (PRD.md)
  - Architecture Guide (ArchitectureGuide.md)
  - Implementation Guide (ImplementationGuide.md)
  - Individual service specifications in ServiceSpecifications/
  - Future Features roadmap (FutureFeatures.md)
- Service specifications for:
  - Jobs Service (port 8000) - Central coordinator
  - Metadata Service (port 8001) - YouTube API integration
  - Download Service (port 8002) - Video downloading with yt-dlp
  - Storage Service (port 8003) - File system management
  - Logging Service (port 8004) - Centralized logging
- Common data models in services/common/models.py
- Project configuration using pyproject.toml with uv package manager
- Basic project structure with service directories

### Changed
- Consolidated planning documentation to eliminate overlap
- Renamed and reorganized planning files for clarity:
  - ArchitectureDecisions.md → ArchitectureGuide.md (high-level only)
  - DesignDecisions.md → merged into ImplementationGuide.md
  - DeferredDesignDetails.md → FutureFeatures.md (future only)
  - ServicesSpecification.md → individual files in ServiceSpecifications/
- Updated service models to use proper typing and Pydantic BaseModel
- Clarified service responsibilities and API contracts

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
