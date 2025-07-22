# Architecture Decisions

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

## Service Architecture

### Communication Protocol
- **Decision**: HTTP/REST between services
- **Format**: JSON payloads
- **Authentication**: None initially (internal only)

### Service Coordination
- **Decision**: Jobs service as central coordinator
- **Pattern**: Orchestration (not choreography)
- **State**: Jobs service maintains all cross-service state

### Data Flow
- **Decision**: Metadata service always called before downloads
- **Persistence**: Only save if metadata differs from latest
- **Validation**: Each service validates its inputs

### Error Handling
- **Retry Logic**: 3 attempts with exponential backoff
- **Failed Jobs**: Queued in Jobs service for manual review
- **Partial Downloads**: Resume from failure point

### Configuration
- **Decision**: Single config file with service sections
- **Format**: YAML or TOML (TBD)
- **Secrets**: Environment variables only
- **Location**: `~/.ytarchive/config.yml` or project root

### Logging
- **Decision**: Centralized logging service
- **Level**: INFO by default
- **Format**: Structured JSON logs
- **Storage**: Local files with rotation

## Development Approach

### Initial Architecture
- **Decision**: Start with microservices architecture
- **Rationale**: Easier to maintain boundaries from start
- **Communication**: Direct HTTP calls initially

### Deployment
- **Decision**: Simple process-based deployment
- **No Docker**: Keep it simple for personal use
- **Process Manager**: Optional (systemd, supervisor)

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

### Configuration Format
- **Decision**: TOML format
- **Rationale**: Python native, cleaner for nested configs
- **File**: `config.toml` in project root
- **Structure**: Sections per service

### Service Startup
- **Decision**: Any order with health checks
- **Implementation**: Services retry connections until dependencies available
- **Health Endpoint**: Each service exposes `/health`
- **Timeout**: 30 seconds for all services to be healthy

## Future Considerations

### Phase 2 Enhancements
- Asynchronous operations
- Webhook support
- Shared database consideration

### Phase 3 Enhancements
- Duplicate detection
- Enhanced state management
- Performance optimizations
