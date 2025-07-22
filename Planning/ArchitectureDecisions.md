# YouTube Archive - Architecture Decisions

This document captures all architectural decisions and design choices made for the YouTube Archive project.

## Table of Contents
1. [Service Architecture](#service-architecture)
2. [Service Infrastructure](#service-infrastructure)
3. [Dependency Management](#dependency-management)
4. [Configuration Management](#configuration-management)
5. [API Design](#api-design)
6. [Data Flow](#data-flow)
7. [Error Handling & Recovery](#error-handling--recovery)
8. [Logging & Monitoring](#logging--monitoring)
9. [Development Approach](#development-approach)
10. [Versioning Strategy](#versioning-strategy)
11. [Future Enhancements](#future-enhancements)

## Service Architecture

### Service Granularity
- **Decision**: Separate processes/microservices that communicate via HTTP
- **Rationale**: Clear service boundaries, easier to maintain and scale
- **Alternative Rejected**: Monolithic application with modules

### Communication Protocol
- **Decision**: HTTP/REST between services
- **Format**: JSON payloads
- **Authentication**: None initially (internal only)
- **Future**: Consider message queues in Phase 3

### Service Coordination
- **Decision**: Jobs service as central coordinator
- **Pattern**: Orchestration (not choreography)
- **State Management**: Jobs service maintains all cross-service state
- **Components**:
  - Jobs Service: Captures cross-service work
  - JobExecutor: Executes individual services

## Service Infrastructure

### Port Assignment
- **Decision**: Fixed ports in configuration
- **Default Ports**:
  - Jobs Service: 8000
  - Metadata Service: 8001
  - Download Service: 8002
  - Storage Service: 8003
  - Logging Service: 8004
- **Configuration**: Overridable in config file

### Service Discovery
- **Decision**: Simple service registry in Jobs service
- **Implementation**: Jobs service maintains service URLs
- **Registration**: Services register on startup
- **Health Checks**: Regular polling of service health

### Project Structure
- **Decision**: Service-focused structure
- **Layout**:
  ```
  ytarchive/
  ├── services/
  │   ├── jobs/
  │   ├── metadata/
  │   ├── download/
  │   ├── storage/
  │   ├── logging/
  │   └── common/
  ├── cli/
  └── tests/
  ```
- **Rationale**: Clear service boundaries, easier to understand

### Service Startup
- **Decision**: Any order with health checks
- **Implementation**: Services retry connections until dependencies available
- **Health Endpoint**: Each service exposes `/health`
- **Timeout**: 30 seconds for all services to be healthy

## Dependency Management

### Version Pinning Strategy
- **Decision**: Use compatible versions (e.g., `httpx~=0.25.0`)
- **Rationale**: Allows automatic patch updates while maintaining stability
- **Implementation**: All dependencies in `pyproject.toml` will use `~=` operator

### Lock File Management
- **Decision**: Commit `uv.lock` to version control
- **Rationale**: Ensures reproducible builds across all environments
- **Process**: Always commit `uv.lock` changes when updating dependencies

### Dependency Grouping
- **Decision**: Two groups - core and dev
- **Structure**:
  ```toml
  [project]
  dependencies = [...]  # Core runtime dependencies
  
  [project.optional-dependencies]
  dev = [...]  # Development, testing, and tooling dependencies
  ```

### Private Dependencies
- **Decision**: Start with public PyPI only
- **Future**: May add private dependencies if needed
- **Fallback**: Can configure private index if required later

### Update Strategy
- **Decision**: Update only when needed
- **Triggers**:
  - Security vulnerabilities
  - Bug fixes needed
  - New features required
  - Manual quarterly review

### Service Dependency Management
- **Decision**: Shared dependencies across all services (monorepo approach)
- **Structure**: Single `pyproject.toml` at project root
- **Benefits**: Consistent versions, easier management
- **Future**: Can split if services diverge significantly

## Configuration Management

### Configuration Storage
- **Decision**: Single config file with service sections
- **Format**: TOML (Python native, cleaner for nested configs)
- **Location**: `config.toml` in project root
- **Structure**: Sections per service

### Sensitive Data
- **Decision**: Environment variables for API keys and sensitive settings
- **Example**: `YOUTUBE_API_KEY` environment variable

## API Design

### Synchronous vs Asynchronous Operations
- **Current Decision**: Synchronous operations
- **Future Enhancement**: Make operations asynchronous in Phase 2 or 3
- **Implementation**: Return job IDs for long-running operations

### Long-running Operations
- **Solution**: Jobs service tracks all operations and their states
- **Progress Tracking**: Real-time updates via polling
- **Future**: Webhook support in Phase 3

### CLI/API Integration
- **Decision**: CLI commands directly call service code
- **Authentication**: No authentication between CLI and APIs
- **Rationale**: Simpler for personal use

## Data Flow

### Metadata Service Integration
- **Decision**: Metadata service must always be called before video download
- **Optimization**: Only persist metadata if it differs from the latest payload
- **Validation**: Each service validates its inputs

### Data Isolation
- **Decision**: Services are completely isolated (no shared data store)
- **Future**: Consider shared database in Phase 3

## Error Handling & Recovery

### Automatic Retries
- **Decision**: Up to 3 attempts with exponential backoff
- **Fallback**: Queue for manual retry via Jobs service after 3 failed attempts
- **Work Plans**: Failed downloads tracked for manual intervention

### Partial Downloads
- **Decision**: Resume from point of failure
- **Implementation**: Track download progress and resume capability

## Logging & Monitoring

### Logging Strategy
- **Decision**: Centralized logging via dedicated Logging service
- **Level**: INFO by default (configurable per service)
- **Format**: Structured JSON logs
- **Storage**: Local files with rotation
- **Retention**: 30 days default

### Monitoring
- **Progress Tracking**: INFO level detail
- **Metrics**: Services emit metrics/events
- **Health Checks**: Regular polling of service health

### State Management
- **Download Progress**: Persisted via Jobs service
- **Download History**: Tracked via Jobs service
- **Duplicate Detection**: Not implemented (Phase 3 enhancement)

## Development Approach

### Architecture Strategy
- **Decision**: Design for microservices from the start
- **Rationale**: Easier to maintain boundaries
- **Communication**: Direct HTTP calls initially

### Deployment
- **Decision**: Simple process-based deployment
- **No Docker**: Keep it simple for personal use
- **Process Manager**: Optional (systemd, supervisor)

## Versioning Strategy

### Version Format
- **Decision**: Semantic Versioning (SemVer)
- **Format**: `MAJOR.MINOR.PATCH`
- **Rules**:
  - MAJOR: Breaking API changes
  - MINOR: New features, backwards compatible
  - PATCH: Bug fixes only

### API Versioning
- **Decision**: Version in URL path
- **Format**: `/api/v1/...`
- **Migration**: Support previous version for 3 months minimum

### Service Versioning
- **Decision**: All services share project version initially
- **Future**: Independent versioning if services are decoupled

## Future Enhancements

### Phase 2 Enhancements
- Asynchronous operations
- Batch operations (channel-wide archiving, parallel downloads)
- Resume capability for interrupted downloads
- Quality selection options

### Phase 3 Enhancements
- Webhook support for notifications
- Shared database consideration
- Message queue integration (Redis/RabbitMQ)
- Duplicate request detection
- Enhanced state management
- Performance optimizations
- Cloud integration (AWS S3, Google Drive)
- Archive verification

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2024-01-22 | Microservices architecture | Clear boundaries, easier to maintain |
| 2024-01-22 | TOML for configuration | Python native, cleaner syntax |
| 2024-01-22 | Fixed ports with config override | Simple discovery, predictable |
| 2024-01-22 | Compatible version pinning (~=) | Balance stability with security updates |
