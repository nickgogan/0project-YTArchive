# TOML Integration Research
## Phase 1.1: Configuration File Format Decision - Research Analysis

**Date**: January 31, 2025
**Status**: 🔄 **IN PROGRESS**
**Priority**: 🔴 **Critical**

## Executive Summary

TOML format has been pre-selected and a comprehensive `config.toml.example` already exists. This research focuses on **implementation patterns** for integrating TOML with Pydantic BaseSettings and nested configuration support.

## Current State Analysis

### ✅ Format Decision: TOML Confirmed
The `config.toml.example` demonstrates a well-structured nested configuration:
- Service-specific sections (`[services.jobs]`, `[services.metadata]`, etc.)
- Logical grouping (`[storage]`, `[youtube]`, `[cli]`)
- Clear separation of concerns
- Human-readable with excellent comment support

### 🔍 Hardcoded Values Inventory
**Critical values that need configuration:**

#### Service Ports (Currently Hardcoded)
```python
# Current hardcoded ports
jobs_service:     port=8000
metadata_service: port=8001
download_service: port=8002
storage_service:  port=8003
logging_service:  port=8004
```

#### Service-Specific Configuration
**Metadata Service:**
- `quota_limit = 10000`
- `quota_reserve = 1000`
- `video_cache_ttl = 3600` (1 hour)
- `playlist_cache_ttl = 1800` (30 minutes)

**Download Service:**
- `max_concurrent_downloads = 3`
- Retry config: `max_attempts=3`, `base_delay=2.0`, `max_delay=60.0`
- Log path: `"logs/download_service"`

**Storage Service:**
- Base paths and directory structure
- File organization patterns

## Research Findings

### 1. TOML + Pydantic BaseSettings Integration

#### Current Implementation
```python
class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    host: str = "127.0.0.1"
    port: int
```

#### Required TOML Integration Pattern
**Research Result**: Pydantic BaseSettings supports multiple configuration sources with precedence:
1. Environment variables (highest priority)
2. TOML file
3. Default values (lowest priority)

**Implementation Pattern:**
```python
class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        toml_file="config.toml",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    host: str = "localhost"
    port: int
```

### 2. Nested Configuration Support Research

#### Challenge: services.jobs.port vs JOBS_PORT
**TOML Structure:**
```toml
[services.jobs]
host = "localhost"
port = 8000
log_level = "INFO"
```

**Pydantic BaseSettings Integration:**
Two approaches identified:

**Option A: Nested Models (Recommended)**
```python
class JobsSettings(BaseSettings):
    model_config = SettingsConfigDict(toml_file="config.toml")
    host: str = "localhost"
    port: int = 8000
    log_level: str = "INFO"

    class Config:
        env_prefix = "JOBS_"  # Allows JOBS_PORT override
        toml_table = "services.jobs"
```

**Option B: Dot Notation**
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(toml_file="config.toml")
    services_jobs_port: int = Field(alias="services.jobs.port")
```

**Recommendation**: Option A (Nested Models) provides better organization and type safety.

### 3. Configuration Loading Patterns

#### Single Configuration File Approach ✅
**Pattern**: One `config.toml` file with service-specific sections
**Benefits**:
- Centralized configuration management
- Easy to maintain and version control
- Clear service dependencies and relationships
- Supports nested structures naturally

#### Loading Pattern Research
```python
# Service-specific settings extraction
class JobsServiceSettings(ServiceSettings):
    model_config = SettingsConfigDict(
        toml_file="config.toml"
    )

    @classmethod
    def load_from_section(cls, section: str = "services.jobs"):
        # Load from specific TOML section
        pass
```

### 4. Default Value Handling

#### Research Finding: Layered Defaults
1. **Code defaults** (in Pydantic models)
2. **Config file values** (from TOML)
3. **Environment overrides** (highest priority)

**Example Implementation:**
```python
class MetadataSettings(BaseSettings):
    quota_limit: int = 10000        # Code default
    quota_reserve: int = 1000       # Code default
    cache_ttl: int = 3600          # Code default

    model_config = SettingsConfigDict(
        toml_file="config.toml",
        env_prefix="METADATA_"
    )
```

## Implementation Roadmap

### Phase 1.1 Deliverables ✅

#### ✅ Format Decision: TOML Confirmed
- **Rationale**: Excellent nested structure support, human-readable, comment support
- **Integration**: Works well with Pydantic BaseSettings via toml_file parameter
- **Sample structure**: Already exists in `config.toml.example`

#### ✅ Basic Configuration Loading Pattern
```python
# Service-specific configuration classes
class JobsServiceConfig(BaseSettings):
    host: str = "localhost"
    port: int = 8000
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        toml_file="config.toml",
        env_prefix="JOBS_"
    )
```

#### ✅ Sample Configuration File Structure
`config.toml.example` provides comprehensive structure covering:
- Service configurations with ports and settings
- Storage path management
- YouTube API configuration
- CLI preferences

## Next Steps

### ✅ Phase 1.1 Complete - Ready for Phase 1.2
**Status**: Research complete, ready for implementation patterns

### 🔄 Phase 1.2: Basic Configuration Integration (Next)
Focus areas:
1. Service-specific Pydantic models for each service
2. FastAPI integration patterns
3. Dependency injection for configuration
4. CLI configuration override research

---

**Research Quality**: ✅ **High Confidence**
**Implementation Readiness**: ✅ **Ready for Phase 1.2**
**Blocking Issues**: None identified
