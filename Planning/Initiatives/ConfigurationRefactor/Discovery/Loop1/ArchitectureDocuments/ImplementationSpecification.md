# Configuration Refactor - Implementation Specification

**Date**: August 02, 2025
**Status**: ✅ **READY FOR IMPLEMENTATION**
**Based On**: ArchitecturalDecision.md (Approved)
**Target**: Project Manager Task Breakdown

---

## 🎯 **Implementation Overview**

This document provides detailed technical specifications, code patterns, and implementation steps for the Configuration Refactor initiative, following the approved "Aligned Minimalism" architectural approach.

---

## 📋 **Phase 1: Service Configuration Classes (2-3 days)**

### **1.1 Create Service-Specific Configuration Classes**

#### **Jobs Service Configuration**
**File**: `services/jobs/config.py`

```python
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from services.common.base import ServiceSettings

class JobsServiceConfig(ServiceSettings):
    """Configuration for Jobs Service."""

    # Inherited from ServiceSettings: host, port
    host: str = "localhost"
    port: int = 8000
    log_level: str = "INFO"

    # Jobs-specific configuration
    jobs_dir: str = "logs/jobs"
    registry_dir: str = "registry"
    max_concurrent_jobs: int = 10
    job_timeout_seconds: int = 3600

    model_config = SettingsConfigDict(
        toml_file="config.toml",
        env_prefix="JOBS_",
        extra="ignore"
    )

    @classmethod
    def load_from_section(cls) -> "JobsServiceConfig":
        """Load configuration from [services.jobs] TOML section."""
        import toml
        from pathlib import Path

        config_file = Path("config.toml")
        if not config_file.exists():
            return cls()  # Use defaults

        try:
            config_data = toml.load(config_file)
            service_config = config_data.get("services", {}).get("jobs", {})
            return cls(**service_config)
        except Exception as e:
            # Fall back to defaults on any error
            print(f"Warning: Failed to load jobs config from TOML: {e}")
            return cls()
```

#### **Metadata Service Configuration**
**File**: `services/metadata/config.py`

```python
class MetadataServiceConfig(ServiceSettings):
    """Configuration for Metadata Service."""

    host: str = "localhost"
    port: int = 8001
    log_level: str = "INFO"

    # Metadata-specific configuration
    quota_limit: int = 10000
    quota_reserve: int = 1000
    cache_ttl: int = 3600  # 1 hour
    api_timeout_seconds: int = 30

    model_config = SettingsConfigDict(
        toml_file="config.toml",
        env_prefix="METADATA_",
        extra="ignore"
    )

    @classmethod
    def load_from_section(cls) -> "MetadataServiceConfig":
        """Load configuration from [services.metadata] TOML section."""
        import toml
        from pathlib import Path

        config_file = Path("config.toml")
        if not config_file.exists():
            return cls()

        try:
            config_data = toml.load(config_file)
            service_config = config_data.get("services", {}).get("metadata", {})
            return cls(**service_config)
        except Exception as e:
            print(f"Warning: Failed to load metadata config from TOML: {e}")
            return cls()
```

#### **Download Service Configuration**
**File**: `services/download/config.py`

```python
class DownloadServiceConfig(ServiceSettings):
    """Configuration for Download Service."""

    host: str = "localhost"
    port: int = 8002
    log_level: str = "INFO"

    # Download-specific configuration
    max_concurrent_downloads: int = 3
    max_retries: int = 3
    quality_preference: str = "1080p"
    format_preference: str = "mp4"
    download_timeout_seconds: int = 1800  # 30 minutes

    model_config = SettingsConfigDict(
        toml_file="config.toml",
        env_prefix="DOWNLOAD_",
        extra="ignore"
    )

    @classmethod
    def load_from_section(cls) -> "DownloadServiceConfig":
        """Load configuration from [services.download] TOML section."""
        import toml
        from pathlib import Path

        config_file = Path("config.toml")
        if not config_file.exists():
            return cls()

        try:
            config_data = toml.load(config_file)
            service_config = config_data.get("services", {}).get("download", {})
            return cls(**service_config)
        except Exception as e:
            print(f"Warning: Failed to load download config from TOML: {e}")
            return cls()
```

#### **Storage Service Configuration**
**File**: `services/storage/config.py`

```python
class StorageServiceConfig(ServiceSettings):
    """Configuration for Storage Service."""

    host: str = "localhost"
    port: int = 8003
    log_level: str = "INFO"

    # Storage-specific configuration
    base_path: str = "~/YTArchive"
    metadata_dir: str = "metadata"
    videos_dir: str = "videos"
    max_file_size_gb: int = 10

    model_config = SettingsConfigDict(
        toml_file="config.toml",
        env_prefix="STORAGE_",
        extra="ignore"
    )

    @classmethod
    def load_from_section(cls) -> "StorageServiceConfig":
        """Load configuration from [services.storage] TOML section."""
        import toml
        from pathlib import Path

        config_file = Path("config.toml")
        if not config_file.exists():
            return cls()

        try:
            config_data = toml.load(config_file)
            service_config = config_data.get("services", {}).get("storage", {})
            return cls(**service_config)
        except Exception as e:
            print(f"Warning: Failed to load storage config from TOML: {e}")
            return cls()
```

#### **Logging Service Configuration**
**File**: `services/logging/config.py`

```python
class LoggingServiceConfig(ServiceSettings):
    """Configuration for Logging Service."""

    host: str = "localhost"
    port: int = 8004
    log_level: str = "INFO"

    # Logging-specific configuration
    retention_days: int = 30
    max_file_size_mb: int = 100
    log_rotation: bool = True

    model_config = SettingsConfigDict(
        toml_file="config.toml",
        env_prefix="LOGGING_",
        extra="ignore"
    )

    @classmethod
    def load_from_section(cls) -> "LoggingServiceConfig":
        """Load configuration from [services.logging] TOML section."""
        import toml
        from pathlib import Path

        config_file = Path("config.toml")
        if not config_file.exists():
            return cls()

        try:
            config_data = toml.load(config_file)
            service_config = config_data.get("services", {}).get("logging", {})
            return cls(**service_config)
        except Exception as e:
            print(f"Warning: Failed to load logging config from TOML: {e}")
            return cls()
```

### **1.2 Update Service Initialization Scripts**

#### **Jobs Service Main Script Update**
**File**: `services/jobs/main.py`

```python
# BEFORE (Hardcoded)
if __name__ == "__main__":
    settings = ServiceSettings(port=8000)  # HARDCODED
    service = JobsService("JobsService", settings)
    service.run()

# AFTER (Configuration-Driven)
if __name__ == "__main__":
    from services.jobs.config import JobsServiceConfig

    config = JobsServiceConfig.load_from_section()
    service = JobsService("JobsService", config)
    service.run()
```

**Similar updates required for**:
- `services/metadata/main.py`
- `services/download/main.py`
- `services/storage/main.py`
- `services/logging/main.py`

---

## 📋 **Phase 2: CLI Configuration Integration (1-2 days)**

### **2.1 Dynamic Service URL Loading**

#### **Update CLI Service Discovery**
**File**: `cli/main.py`

```python
# BEFORE (Hardcoded)
SERVICES = {
    "jobs": "http://localhost:8000",
    "metadata": "http://localhost:8001",
    "download": "http://localhost:8002",
    "storage": "http://localhost:8003",
    "logging": "http://localhost:8004",
}

# AFTER (Configuration-Driven)
def load_service_urls(config_file: Optional[str] = None) -> Dict[str, str]:
    """Load service URLs from configuration with fallback to defaults."""
    import toml
    from pathlib import Path

    config_path = Path(config_file) if config_file else Path("config.toml")

    # Default service URLs (fallback)
    default_services = {
        "jobs": "http://localhost:8000",
        "metadata": "http://localhost:8001",
        "download": "http://localhost:8002",
        "storage": "http://localhost:8003",
        "logging": "http://localhost:8004",
    }

    if not config_path.exists():
        return default_services

    try:
        config_data = toml.load(config_path)
        services_config = config_data.get("services", {})

        service_urls = {}
        for service_name, default_url in default_services.items():
            service_config = services_config.get(service_name, {})
            host = service_config.get("host", "localhost")

            # Extract port from default URL if not in config
            default_port = int(default_url.split(":")[-1])
            port = service_config.get("port", default_port)

            service_urls[service_name] = f"http://{host}:{port}"

        return service_urls

    except Exception as e:
        print(f"Warning: Failed to load service URLs from config: {e}")
        return default_services

# Updated YTArchiveAPI class
class YTArchiveAPI:
    def __init__(self, config_file: Optional[str] = None):
        self.client = httpx.AsyncClient()
        self.services = load_service_urls(config_file)  # Dynamic loading
```

### **2.2 CLI Configuration File Option**

#### **Add --config-file Option to Commands**

```python
@cli.command()
@click.option("--config-file", "-c", help="Path to configuration file")
@click.option("--quality", "-q", default="best", help="Video quality")
def download(config_file: Optional[str], quality: str, ...):
    """Download video with configuration override."""

    async def _download():
        api = YTArchiveAPI(config_file=config_file)
        # ... rest of download logic

    asyncio.run(_download())
```

---

## 📋 **Phase 3: Configuration Validation Enhancement (1 day)**

### **3.1 Extend Existing Validation Framework**

#### **Update _validate_configuration() Function**
**File**: `cli/main.py`

```python
async def _validate_configuration(json_output: bool, fix: bool = False) -> dict:
    """Enhanced configuration validation with TOML support."""
    validation_result = {
        "overall_status": "valid",
        "issues": [],
        "warnings": [],
        "fixes_applied": [],
        "configuration_files": {},
        "environment_variables": {},
        "directory_structure": {},
        "services_config": {},
        "configuration_validation": {}  # NEW
    }

    # ... existing validation logic ...

    # NEW: TOML Configuration Validation
    config_toml_path = Path("config.toml")
    validation_result["configuration_files"]["config.toml"] = {
        "exists": config_toml_path.exists(),
        "valid_toml": False,
        "required_sections": {},
        "missing_required": [],
    }

    if config_toml_path.exists():
        try:
            import toml
            config_data = toml.load(config_toml_path)
            validation_result["configuration_files"]["config.toml"]["valid_toml"] = True

            # Validate required service sections
            required_sections = ["services.jobs", "services.metadata", "services.download", "services.storage", "services.logging"]
            for section in required_sections:
                section_exists = _check_nested_section(config_data, section)
                validation_result["configuration_files"]["config.toml"]["required_sections"][section] = section_exists

                if not section_exists:
                    validation_result["configuration_files"]["config.toml"]["missing_required"].append(section)

        except Exception as e:
            validation_result["issues"].append(f"Invalid TOML syntax in config.toml: {str(e)}")
            validation_result["overall_status"] = "issues_found"
    else:
        validation_result["warnings"].append("Configuration file config.toml not found (using defaults)")
        if validation_result["overall_status"] == "valid":
            validation_result["overall_status"] = "warnings_only"

    # NEW: Service Configuration Validation
    if config_toml_path.exists() and validation_result["configuration_files"]["config.toml"]["valid_toml"]:
        try:
            config_data = toml.load(config_toml_path)
            services = ["jobs", "metadata", "download", "storage", "logging"]

            for service_name in services:
                service_validation = _validate_service_configuration(config_data, service_name)
                validation_result["services_config"][service_name] = service_validation

        except Exception as e:
            validation_result["issues"].append(f"Service configuration validation failed: {str(e)}")
            validation_result["overall_status"] = "issues_found"

    return validation_result

def _check_nested_section(config_data: dict, section_path: str) -> bool:
    """Check if nested TOML section exists."""
    keys = section_path.split('.')
    current = config_data

    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return False
    return True

def _validate_service_configuration(config_data: dict, service_name: str) -> dict:
    """Validate service-specific configuration."""
    service_validation = {
        "host_configured": False,
        "port_configured": False,
        "missing_required": [],
        "invalid_values": []
    }

    service_config = config_data.get("services", {}).get(service_name, {})

    # Required parameters
    required_params = {
        "host": str,
        "port": int,
    }

    for param, expected_type in required_params.items():
        if param in service_config:
            value = service_config[param]
            if isinstance(value, expected_type):
                service_validation[f"{param}_configured"] = True
            else:
                service_validation["invalid_values"].append(
                    f"{param} must be {expected_type.__name__}, got {type(value).__name__}"
                )
        else:
            service_validation["missing_required"].append(param)

    return service_validation
```

### **3.2 Enhanced Health Checks**

#### **Update BaseService Health Endpoint**
**File**: `services/common/base.py`

```python
class BaseService(ABC):
    def _configure_routes(self) -> None:
        """Configure the API routes for the service."""

        @self.app.get("/health", tags=["Monitoring"])
        async def health_check() -> Dict[str, str]:
            """Enhanced health check with configuration status."""
            from pathlib import Path

            return {
                "status": "ok",
                "service": self.service_name,
                "config_loaded": "true",
                "config_source": "config.toml" if Path("config.toml").exists() else "defaults",
                "host": self.settings.host,
                "port": str(self.settings.port)
            }

        @self.app.get("/config/status", tags=["Configuration"])
        async def config_status() -> Dict[str, Any]:
            """Configuration validation endpoint."""
            from pathlib import Path

            return {
                "config_file_exists": Path("config.toml").exists(),
                "settings_valid": True,
                "host": self.settings.host,
                "port": self.settings.port,
                "config_class": type(self.settings).__name__
            }
```

---

## 🧪 **Testing Requirements**

### **Unit Tests Required**
1. **Configuration Class Tests** - Test each service config class loading
2. **TOML Parsing Tests** - Test TOML file parsing with various scenarios
3. **Validation Tests** - Test configuration validation functions
4. **CLI Integration Tests** - Test --config-file option functionality

### **Integration Tests Required**
1. **Service Startup Tests** - Test services start with configuration
2. **CLI Command Tests** - Test CLI commands with configuration files
3. **Health Check Tests** - Test enhanced health endpoints

### **Memory Leak Tests Required**
1. **Configuration Loading Memory Tests** - Test config loading operations
2. **TOML Parsing Memory Tests** - Test TOML file operations
3. **Service Initialization Memory Tests** - Test service startup with config

---

## 📁 **File Structure Changes**

### **New Files to Create**
```
services/jobs/config.py
services/metadata/config.py
services/download/config.py
services/storage/config.py
services/logging/config.py
```

### **Files to Update**
```
services/jobs/main.py
services/metadata/main.py
services/download/main.py
services/storage/main.py
services/logging/main.py
services/common/base.py
cli/main.py
```

### **Test Files to Create/Update**
```
tests/unit/test_service_configs.py
tests/integration/test_config_integration.py
tests/memory/test_config_memory_leaks.py
tests/cli/test_config_commands.py
```

---

## ⏱️ **Implementation Timeline**

### **Phase 1: Service Configuration Classes (2-3 days)**
- Day 1: Create configuration classes for all 5 services
- Day 2: Update service initialization scripts
- Day 3: Test service startup with configuration

### **Phase 2: CLI Integration (1-2 days)**
- Day 1: Implement dynamic service URL loading
- Day 2: Add --config-file option to CLI commands

### **Phase 3: Validation Enhancement (1 day)**
- Day 1: Extend validation framework and update health checks

### **Total Estimated Effort**: 4-6 days implementation + testing

---

## ✅ **Ready for Project Manager Task Breakdown**

This specification provides:
- ✅ Detailed code patterns for all components
- ✅ Specific file locations and changes required
- ✅ Testing requirements and scenarios
- ✅ Implementation timeline and phases
- ✅ Success criteria and quality gates

**The Project Manager can now create concrete implementation tasks based on this specification.**
