# Service Configuration Integration Research
## Phase 1.2: Basic Configuration Integration - Research Analysis

**Date**: January 31, 2025
**Status**: 🔄 **IN PROGRESS**
**Priority**: 🔴 **Critical**

## Executive Summary

Research into integrating TOML configuration with existing service architecture reveals clean integration paths. Current `BaseService` + `ServiceSettings` pattern provides excellent foundation for configuration injection.

## Current Architecture Analysis

### ✅ Service Architecture Foundation
**Strong Foundation Identified:**

```python
# Current Pattern - services/common/base.py
class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    host: str = "127.0.0.1"  # Default value
    port: int                # Required, no default

class BaseService(ABC):
    def __init__(self, service_name: str, settings: ServiceSettings):
        self.service_name = service_name
        self.settings = settings
        self.app = FastAPI(...)
```

**Current Service Initialization (Hardcoded):**
```python
# All services follow this pattern:
if __name__ == "__main__":
    settings = ServiceSettings(port=8000)  # HARDCODED
    service = JobsService("JobsService", settings)
    service.run()
```

### 🔍 CLI Service Integration Analysis
**Current CLI Pattern:**
```python
# cli/main.py - HARDCODED service URLs
SERVICES = {
    "jobs": "http://localhost:8000",
    "metadata": "http://localhost:8001",
    "download": "http://localhost:8002",
    "storage": "http://localhost:8003",
    "logging": "http://localhost:8004",
}

class YTArchiveAPI:
    def __init__(self):
        self.client = httpx.AsyncClient()

    async def create_job(self, ...):
        response = await self.client.post(
            f"{SERVICES['jobs']}/api/v1/jobs", json=payload
        )
```

**CLI Configuration Commands:**
- ✅ `ytarchive config` command already exists
- ✅ `--check-config` flag for diagnostics
- ✅ Configuration validation framework in place

## Research Findings

### 1. Service Configuration Pattern

#### ✅ Recommended Integration Pattern
**Service-Specific Configuration Classes:**

```python
# services/jobs/config.py
class JobsServiceConfig(BaseSettings):
    # Service-specific settings
    host: str = "localhost"
    port: int = 8000
    log_level: str = "INFO"

    # Jobs-specific configuration
    jobs_dir: str = "logs/jobs"
    registry_dir: str = "registry"

    model_config = SettingsConfigDict(
        toml_file="config.toml",
        env_prefix="JOBS_",        # Allows JOBS_PORT override
        extra="ignore"
    )

    @classmethod
    def load_from_section(cls) -> "JobsServiceConfig":
        """Load configuration from [services.jobs] section."""
        import toml
        from pathlib import Path

        config_file = Path("config.toml")
        if not config_file.exists():
            return cls()  # Use defaults

        config_data = toml.load(config_file)
        service_config = config_data.get("services", {}).get("jobs", {})

        # Pydantic will handle validation and defaults
        return cls(**service_config)
```

**Updated Service Initialization:**
```python
# services/jobs/main.py
if __name__ == "__main__":
    config = JobsServiceConfig.load_from_section()
    service = JobsService("JobsService", config)
    service.run()
```

#### 🔍 FastAPI Integration Research
**Current Integration:** ✅ **Already Optimal**
- Services receive settings via constructor
- FastAPI app uses `self.settings.host` and `self.settings.port`
- No changes needed to FastAPI integration pattern

**Dependency Injection Pattern:**
```python
class JobsService(BaseService):
    def __init__(self, service_name: str, settings: JobsServiceConfig):
        super().__init__(service_name, settings)

        # Service-specific initialization using config
        self.jobs_dir = Path(settings.jobs_dir)
        self.registry_dir = Path(settings.registry_dir)
        # Configuration is available as self.settings
```

### 2. CLI Integration Research

#### ✅ CLI Configuration Override Pattern
**Dynamic Service URL Loading:**

```python
# cli/main.py - Replace hardcoded SERVICES dict
def load_service_urls() -> Dict[str, str]:
    """Load service URLs from configuration."""
    import toml
    from pathlib import Path

    config_file = Path("config.toml")
    if not config_file.exists():
        # Fallback to hardcoded defaults
        return {
            "jobs": "http://localhost:8000",
            "metadata": "http://localhost:8001",
            "download": "http://localhost:8002",
            "storage": "http://localhost:8003",
            "logging": "http://localhost:8004",
        }

    config_data = toml.load(config_file)
    services_config = config_data.get("services", {})

    service_urls = {}
    for service_name, service_config in services_config.items():
        host = service_config.get("host", "localhost")
        port = service_config.get("port", 8000)  # Default port
        service_urls[service_name] = f"http://{host}:{port}"

    return service_urls

# Updated YTArchiveAPI
class YTArchiveAPI:
    def __init__(self, config_file: Optional[str] = None):
        self.client = httpx.AsyncClient()
        self.services = load_service_urls()  # Dynamic loading
```

#### 🔍 CLI Option Override Research
**Configuration File Override:**
```python
@cli.command()
@click.option("--config-file", "-c", help="Path to configuration file")
@click.option("--api-key", help="Override YouTube API key")
def download(config_file: Optional[str], api_key: Optional[str], ...):
    """Download with configuration overrides."""
    # Load configuration with optional file override
    config = load_configuration(config_file)

    # Override specific values from CLI
    if api_key:
        config.youtube.api_key = api_key
```

### 3. Minimal Configuration Schema Design

#### ✅ Per-Service Configuration Schemas
**Jobs Service Schema:**
```python
class JobsServiceConfig(BaseSettings):
    host: str = "localhost"
    port: int = 8000
    log_level: str = "INFO"
    jobs_dir: str = "logs/jobs"
    registry_dir: str = "registry"
```

**Metadata Service Schema:**
```python
class MetadataServiceConfig(BaseSettings):
    host: str = "localhost"
    port: int = 8001
    log_level: str = "INFO"
    quota_limit: int = 10000
    quota_reserve: int = 1000
    cache_ttl: int = 3600
```

**Download Service Schema:**
```python
class DownloadServiceConfig(BaseSettings):
    host: str = "localhost"
    port: int = 8002
    log_level: str = "INFO"
    max_concurrent_downloads: int = 3
    max_attempts: int = 3
    base_delay: float = 2.0
    max_delay: float = 60.0
```

**Storage Service Schema:**
```python
class StorageServiceConfig(BaseSettings):
    host: str = "localhost"
    port: int = 8003
    log_level: str = "INFO"
    base_path: str = "~/YTArchive"
    metadata_dir: str = "metadata"
    videos_dir: str = "videos"
```

**Logging Service Schema:**
```python
class LoggingServiceConfig(BaseSettings):
    host: str = "localhost"
    port: int = 8004
    log_level: str = "INFO"
    retention_days: int = 30
    max_file_size_mb: int = 100
```

## Implementation Strategy

### ✅ Phase 1.2 Integration Approach

#### Step 1: Service Configuration Classes
1. Create service-specific config classes inheriting from ServiceSettings
2. Add service-specific configuration properties
3. Implement `load_from_section()` class method for TOML loading

#### Step 2: Update Service Initialization
1. Replace hardcoded `ServiceSettings(port=xxxx)` with config loading
2. Update each service's `if __name__ == "__main__"` block
3. Maintain backward compatibility with environment variables

#### Step 3: CLI Configuration Integration
1. Replace hardcoded `SERVICES` dict with dynamic loading
2. Add `--config-file` option to CLI commands
3. Add configuration file validation to existing `config` command

#### Step 4: Basic Configuration Overrides
1. Support `--config-file` for alternate configuration files
2. Support key CLI overrides (API key, output directory)
3. Maintain environment variable precedence

## Risk Analysis

### ✅ Low Risk Integration
**Advantages of Current Architecture:**
- Services already use dependency injection pattern
- Pydantic BaseSettings provides excellent TOML support
- CLI already has configuration validation framework
- Clear separation between service and CLI configuration needs

**Minimal Breaking Changes:**
- Only service startup scripts need modification
- CLI maintains all existing functionality
- Configuration remains optional (defaults provided)

## Next Steps - Phase 1.3

### 🔄 Ready for Configuration Validation Research
With service integration patterns established, Phase 1.3 can focus on:
1. Configuration file validation patterns
2. Startup validation integration
3. CLI config command enhancements
4. Basic health checks for configuration

---

**Research Quality**: ✅ **High Confidence**
**Implementation Readiness**: ✅ **Clear patterns identified**
**Blocking Issues**: None - existing architecture is config-integration ready
