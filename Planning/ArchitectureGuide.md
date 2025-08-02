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
- **Rationale**: Predictable service locations, easy local development
- **Alternative Rejected**: Dynamic port assignment (adds complexity)

### Service Discovery
- **Decision**: Simple service registry in Jobs service
- **Rationale**: Centralized registry without external dependencies
- **Alternative Rejected**: External service discovery (Consul, etcd)

### Project Structure
- **Decision**: Service-focused monorepo structure
- **Rationale**: Clear service boundaries while maintaining shared code
- **Alternative Rejected**: Separate repositories per service

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

### Configuration Strategy
- **Decision**: Single TOML configuration file with environment variable overrides
- **Rationale**: TOML is Python-friendly, supports complex structures, simple for personal use
- **Alternative Rejected**: YAML (parsing complexity), JSON (no comments)

### Environment Strategy
- **Decision**: Single environment configuration (development/personal use)
- **Rationale**: YTArchive is designed for personal use, eliminates multi-environment complexity
- **Alternative Rejected**: Multi-environment support (dev/staging/production - unnecessary complexity)

## API Design

### API Pattern
- **Decision**: RESTful HTTP APIs with JSON payloads
- **Rationale**: Simple, well-understood, good tooling support
- **Alternative Rejected**: gRPC (complexity), GraphQL (overkill)

### Operation Model
- **Decision**: Job-based asynchronous operations
- **Rationale**: Long-running downloads need progress tracking
- **Alternative Rejected**: Synchronous blocking calls

## Data Flow

### Metadata Service Integration
- **Decision**: Metadata service must always be called before video download
- **Optimization**: Only persist metadata if it differs from the latest payload
- **Validation**: Each service validates its inputs

### Data Isolation
- **Decision**: Services are completely isolated (no shared data store)
- **Future**: Consider shared database in Phase 3

## Error Handling & Recovery

### Error Recovery Architecture
- **Decision**: Hybrid error recovery library with service-specific implementations
- **Implementation**: Central `services/error_recovery/` package providing shared components
- **Components**:
  - ErrorRecoveryManager: Central coordinator for retry logic
  - Retry Strategies: Exponential backoff, circuit breaker, adaptive, fixed delay
  - Error Reporting: Structured logging and diagnostics
  - Service Integration: Abstract interfaces for service-specific handlers

### Retry Strategy
- **Decision**: Multiple retry strategies with configurable selection
- **Available Strategies**:
  - ExponentialBackoffStrategy: Standard exponential backoff with jitter
  - CircuitBreakerStrategy: Fail-fast when error rates exceed thresholds
  - AdaptiveStrategy: Dynamic adjustment based on success/failure patterns
  - FixedDelayStrategy: Simple fixed-interval retries for predictable scenarios
- **Configuration**: Per-operation retry limits, delays, and strategy selection
- **Fallback**: Manual intervention after all automatic recovery attempts

### Error Classification
- **Decision**: Structured error severity and categorization
- **Severities**: LOW, MEDIUM, HIGH, CRITICAL with appropriate escalation
- **Error Context**: Capture operation details, timestamps, retry history
- **Recovery Guidance**: Automated suggestions for common error patterns

### Service Integration Pattern
- **Decision**: Abstract interfaces with dependency injection
- **Benefits**: Service-specific error handling while maintaining consistency
- **Implementation**: Services implement ServiceErrorHandler interface
- **Testing**: Comprehensive test coverage for all error recovery scenarios

## Logging & Monitoring

### Logging Architecture
- **Decision**: Centralized structured logging service
- **Rationale**: Single place to query all service logs
- **Alternative Rejected**: Per-service log files (hard to correlate)

### Monitoring Approach
- **Decision**: Service health checks and metrics collection
- **Rationale**: Essential for distributed system visibility
- **Alternative Rejected**: External monitoring stack (complexity)

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
| 2024-01-22 | HTTP/REST over gRPC | Simpler implementation, better debugging |
| 2024-01-22 | Jobs service orchestration | Central coordination simpler than choreography |
| 2024-01-22 | File-based job storage | Simple, portable, no database dependencies |
| 2024-01-22 | No caching in v1 | Reduce complexity for initial implementation |
| 2024-01-22 | Monorepo structure | Easier dependency management |
| 2024-01-22 | Centralized logging service | Single place to query all service logs |
| 2025-01-31 | Single environment configuration | Personal use project, eliminate multi-env complexity |
