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
8. [CLI Architecture](#cli-architecture)
9. [Testing Strategy](#testing-strategy)
10. [Memory Management](#memory-management)
11. [Logging & Monitoring](#logging--monitoring)
12. [Development Approach](#development-approach)
13. [Versioning Strategy](#versioning-strategy)
14. [Future Enhancements](#future-enhancements)

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

### Current Implementation Strategy (v0.1.0)
- **Decision**: Minimal configuration with Pydantic BaseSettings
- **Implementation**: Services use basic host/port configuration only
- **Format**: Environment variables via .env files
- **Rationale**: Simple for personal use, reduces initial complexity
- **Alternative Rejected**: Full TOML configuration system (deferred for simplicity)

### Service Configuration Pattern
- **Decision**: Hardcoded service-specific configurations
- **Implementation**: Retry configs, timeouts, and limits embedded in service code
- **Rationale**: Simplifies deployment and reduces configuration errors
- **Trade-off**: Less flexibility for advanced users, but maintains simplicity

### Environment Strategy
- **Decision**: Single environment configuration (development/personal use)
- **Rationale**: YTArchive is designed for personal use, eliminates multi-environment complexity
- **Alternative Rejected**: Multi-environment support (dev/staging/production - unnecessary complexity)

### Future Configuration Architecture
- **Planned**: TOML-based centralized configuration with service sections
- **Research**: Comprehensive configuration refactoring research completed
- **Timeline**: Configuration enhancement deferred to post-MVP phases

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
- **Decision**: Enterprise-grade error recovery framework for production reliability
- **Implementation**: Comprehensive `services/error_recovery/` package with pluggable components
- **Rationale**: Personal use project requires high reliability for long-running downloads
- **Alternative Rejected**: Simple retry logic (insufficient for complex failure scenarios)

### Core Components
- **ErrorRecoveryManager**: Central coordinator implementing execute_with_retry pattern
- **Strategy Pattern**: Pluggable retry strategies with different characteristics
- **Error Classification**: Automatic retry reason determination from exception types
- **Service Integration**: Dependency injection for service-specific error handlers
- **Context Tracking**: Comprehensive operation tracking with attempt history

### Retry Strategies
- **Decision**: Multiple specialized strategies for different failure patterns
- **ExponentialBackoffStrategy**: Standard backoff with jitter for general failures
- **CircuitBreakerStrategy**: Fail-fast pattern when error rates exceed thresholds
- **AdaptiveStrategy**: Dynamic adjustment based on historical success/failure patterns
- **FixedDelayStrategy**: Predictable intervals for rate-limited scenarios
- **Configuration**: Strategy selection per operation type with fallback chains

### Error Classification & Reporting
- **Decision**: Structured error categorization with automated retry decisions
- **Categories**: Network, API quota, rate limiting, download failures, service unavailable
- **Severity Levels**: Automatic escalation based on failure patterns and context
- **Reporting**: Structured error reports with recovery suggestions and context
- **Integration**: Seamless integration with logging service for error tracking

### Production Reliability Features
- **Operation Tracking**: Active recovery operations monitoring with UUIDs
- **Graceful Degradation**: Service-specific handlers with fallback to general retry
- **Resource Cleanup**: Automatic cleanup of failed operations and tracking state
- **Comprehensive Testing**: Full test coverage including edge cases and failure scenarios

## CLI Architecture

### Design Philosophy
- **Decision**: Rich terminal interface with async-first architecture
- **Implementation**: Click framework with async delegation pattern
- **Rationale**: Enhanced user experience for long-running operations
- **Alternative Rejected**: Simple synchronous CLI (insufficient for complex workflows)

### User Interface Pattern
- **Terminal UI**: Rich library for progress bars, tables, panels, and styled output
- **Progress Tracking**: Real-time progress updates for downloads and batch operations
- **Error Display**: Safe error message handling including coroutine cleanup
- **JSON Output**: Optional machine-readable output for all commands

### Service Integration
- **Decision**: Direct HTTP communication with hardcoded service URLs
- **Implementation**: AsyncHttpx client for all service communication
- **Rationale**: Simple service discovery appropriate for personal use
- **Alternative Rejected**: Dynamic service discovery (unnecessary complexity)

### Command Architecture
- **Pattern**: Click commands delegate to async implementation functions
- **Error Handling**: Comprehensive error boundary with safe message conversion
- **Configuration**: Custom parameter types for complex configurations (retry configs)
- **Extensibility**: Command groups for logical organization (playlist, recovery, diagnostics)

## Testing Strategy

### Multi-Tier Testing Architecture
- **Decision**: Comprehensive testing strategy with multiple validation layers
- **Implementation**: 451 tests across unit, service, and integration tiers
- **Quality Gate**: 100% test success rate required for all commits
- **Alternative Rejected**: Minimal testing (insufficient for production reliability)

### Test Organization
- **Unit Tests**: 210 tests covering business logic, models, and utilities
- **Service Tests**: 186 tests for service-specific functionality and API contracts
- **Integration Tests**: 55 tests for end-to-end workflows and service coordination
- **Memory Tests**: Comprehensive leak detection across all service operations

### Quality Assurance
- **Coverage Requirements**: 80% minimum code coverage with pytest-cov
- **Type Safety**: Full mypy --strict compliance for all code
- **Memory Safety**: Zero tolerance for memory leaks in long-running operations
- **Performance Testing**: Load testing and benchmark validation for critical paths

### Testing Infrastructure
- **Mocking Strategy**: Comprehensive mocking of external dependencies (YouTube API, filesystem)
- **Fixture Management**: Reusable test fixtures for consistent test environments
- **Async Testing**: Full async test support with pytest-asyncio
- **Continuous Validation**: Automated test execution in development workflow

## Memory Management

### Memory Safety Strategy
- **Decision**: Proactive memory leak detection and prevention
- **Implementation**: Automated memory leak testing for all services
- **Rationale**: Critical for long-running download operations and service reliability
- **Alternative Rejected**: Reactive memory monitoring (insufficient for prevention)

### Leak Detection Architecture
- **Automated Testing**: Memory leak tests integrated into test suite
- **Service Coverage**: Individual leak tests for all major services
- **Operation Tracking**: Memory usage monitoring during long-running operations
- **Reporting**: Detailed memory leak reports with trace information

### Resource Management
- **Lifecycle Management**: Explicit resource cleanup in service shutdown
- **Connection Pooling**: Proper HTTP client resource management
- **File Handling**: Safe file operations with context managers
- **Background Tasks**: Proper async task cleanup and cancellation

### Prevention Patterns
- **Context Managers**: Consistent use of async context managers for resources
- **Explicit Cleanup**: Manual resource cleanup in critical sections
- **Monitoring**: Runtime memory usage tracking for anomaly detection
- **Validation**: Memory leak tests as part of continuous integration

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
| 2025-01-31 | Minimal configuration implementation | Defer TOML complexity, hardcode service configs |
| 2025-01-31 | Enterprise error recovery framework | Production reliability for long-running downloads |
| 2025-01-31 | Rich CLI with async architecture | Enhanced UX for complex download workflows |
| 2025-01-31 | Hardcoded service URLs | Intentional simplicity for personal use |
| 2025-01-31 | Multi-tier testing strategy | 451 tests across unit/service/integration layers |
| 2025-01-31 | Proactive memory leak detection | Critical for long-running service reliability |
| 2025-01-31 | Click async delegation pattern | Safe coroutine handling in CLI commands |
