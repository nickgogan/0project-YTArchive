# Configuration Refactor - Service Integration Checklist

**Date**: August 02, 2025
**Status**: ✅ **READY FOR IMPLEMENTATION**
**Purpose**: Service-specific integration steps and validation checklists
**Target**: Development team task breakdown

---

## 🎯 **Integration Overview**

This checklist provides step-by-step integration requirements for each of the 5 YTArchive services. Each service must complete all checklist items to ensure consistent configuration integration.

---

## 📋 **Jobs Service Integration Checklist**

### **🔧 Implementation Steps**

#### **Step 1: Configuration Class Creation**
- [ ] Create `services/jobs/config.py`
- [ ] Implement `JobsServiceConfig` class extending `ServiceSettings`
- [ ] Add service-specific configuration properties:
  - [ ] `jobs_dir: str = "logs/jobs"`
  - [ ] `registry_dir: str = "registry"`
  - [ ] `max_concurrent_jobs: int = 10`
  - [ ] `job_timeout_seconds: int = 3600`
- [ ] Implement `load_from_section()` class method
- [ ] Configure TOML section: `services.jobs`
- [ ] Configure environment prefix: `JOBS_`

#### **Step 2: Service Integration**
- [ ] Update `services/jobs/main.py` imports
- [ ] Replace hardcoded `ServiceSettings(port=8000)`
- [ ] Use `JobsServiceConfig.load_from_section()`
- [ ] Test service startup with configuration
- [ ] Verify service uses configuration values

#### **Step 3: Enhanced Health Checks**
- [ ] Verify `/health` endpoint returns configuration status
- [ ] Verify `/config/status` endpoint works
- [ ] Test health checks with and without config.toml

#### **Step 4: Testing**
- [ ] Create unit tests for `JobsServiceConfig`
- [ ] Test TOML section loading
- [ ] Test environment variable overrides
- [ ] Test fallback to defaults
- [ ] Add memory leak tests for configuration loading
- [ ] Test service startup integration

### **🧪 Validation Checklist**
- [ ] Service starts successfully with default configuration
- [ ] Service starts successfully with TOML configuration
- [ ] Environment variables override TOML values (e.g., `JOBS_PORT=8005`)
- [ ] Service gracefully handles missing config.toml
- [ ] Service gracefully handles invalid TOML syntax
- [ ] Health endpoints return correct configuration information
- [ ] Memory leak tests pass for configuration operations

### **📁 Files Modified**
- [ ] `services/jobs/config.py` (NEW)
- [ ] `services/jobs/main.py` (MODIFIED)
- [ ] `tests/unit/test_jobs_config.py` (NEW)
- [ ] `tests/memory/test_config_memory_leaks.py` (MODIFIED)

---

## 📋 **Metadata Service Integration Checklist**

### **🔧 Implementation Steps**

#### **Step 1: Configuration Class Creation**
- [ ] Create `services/metadata/config.py`
- [ ] Implement `MetadataServiceConfig` class extending `ServiceSettings`
- [ ] Add service-specific configuration properties:
  - [ ] `quota_limit: int = 10000`
  - [ ] `quota_reserve: int = 1000`
  - [ ] `cache_ttl: int = 3600`
  - [ ] `api_timeout_seconds: int = 30`
- [ ] Implement `load_from_section()` class method
- [ ] Configure TOML section: `services.metadata`
- [ ] Configure environment prefix: `METADATA_`

#### **Step 2: Service Integration**
- [ ] Update `services/metadata/main.py` imports
- [ ] Replace hardcoded `ServiceSettings(port=8001)`
- [ ] Use `MetadataServiceConfig.load_from_section()`
- [ ] Update service logic to use new configuration properties
- [ ] Test service startup with configuration

#### **Step 3: Enhanced Health Checks**
- [ ] Verify `/health` endpoint returns configuration status
- [ ] Verify `/config/status` endpoint works
- [ ] Test health checks with and without config.toml

#### **Step 4: Testing**
- [ ] Create unit tests for `MetadataServiceConfig`
- [ ] Test TOML section loading
- [ ] Test environment variable overrides
- [ ] Test fallback to defaults
- [ ] Add memory leak tests for configuration loading
- [ ] Test service startup integration

### **🧪 Validation Checklist**
- [ ] Service starts successfully with default configuration
- [ ] Service starts successfully with TOML configuration
- [ ] Environment variables override TOML values (e.g., `METADATA_QUOTA_LIMIT=15000`)
- [ ] Service gracefully handles missing config.toml
- [ ] Service gracefully handles invalid TOML syntax
- [ ] Quota and cache settings are applied correctly
- [ ] Health endpoints return correct configuration information
- [ ] Memory leak tests pass for configuration operations

### **📁 Files Modified**
- [ ] `services/metadata/config.py` (NEW)
- [ ] `services/metadata/main.py` (MODIFIED)
- [ ] `tests/unit/test_metadata_config.py` (NEW)
- [ ] `tests/memory/test_config_memory_leaks.py` (MODIFIED)

---

## 📋 **Download Service Integration Checklist**

### **🔧 Implementation Steps**

#### **Step 1: Configuration Class Creation**
- [ ] Create `services/download/config.py`
- [ ] Implement `DownloadServiceConfig` class extending `ServiceSettings`
- [ ] Add service-specific configuration properties:
  - [ ] `max_concurrent_downloads: int = 3`
  - [ ] `max_retries: int = 3`
  - [ ] `quality_preference: str = "1080p"`
  - [ ] `format_preference: str = "mp4"`
  - [ ] `download_timeout_seconds: int = 1800`
- [ ] Implement `load_from_section()` class method
- [ ] Configure TOML section: `services.download`
- [ ] Configure environment prefix: `DOWNLOAD_`

#### **Step 2: Service Integration**
- [ ] Update `services/download/main.py` imports
- [ ] Replace hardcoded `ServiceSettings(port=8002)`
- [ ] Use `DownloadServiceConfig.load_from_section()`
- [ ] Update download logic to use configuration properties
- [ ] Test service startup with configuration

#### **Step 3: Enhanced Health Checks**
- [ ] Verify `/health` endpoint returns configuration status
- [ ] Verify `/config/status` endpoint works
- [ ] Test health checks with and without config.toml

#### **Step 4: Testing**
- [ ] Create unit tests for `DownloadServiceConfig`
- [ ] Test TOML section loading
- [ ] Test environment variable overrides
- [ ] Test fallback to defaults
- [ ] Add memory leak tests for configuration loading
- [ ] Test service startup integration

### **🧪 Validation Checklist**
- [ ] Service starts successfully with default configuration
- [ ] Service starts successfully with TOML configuration
- [ ] Environment variables override TOML values (e.g., `DOWNLOAD_MAX_CONCURRENT=5`)
- [ ] Service gracefully handles missing config.toml
- [ ] Service gracefully handles invalid TOML syntax
- [ ] Download settings are applied correctly (quality, format, timeouts)
- [ ] Health endpoints return correct configuration information
- [ ] Memory leak tests pass for configuration operations

### **📁 Files Modified**
- [ ] `services/download/config.py` (NEW)
- [ ] `services/download/main.py` (MODIFIED)
- [ ] `tests/unit/test_download_config.py` (NEW)
- [ ] `tests/memory/test_config_memory_leaks.py` (MODIFIED)

---

## 📋 **Storage Service Integration Checklist**

### **🔧 Implementation Steps**

#### **Step 1: Configuration Class Creation**
- [ ] Create `services/storage/config.py`
- [ ] Implement `StorageServiceConfig` class extending `ServiceSettings`
- [ ] Add service-specific configuration properties:
  - [ ] `base_path: str = "~/YTArchive"`
  - [ ] `metadata_dir: str = "metadata"`
  - [ ] `videos_dir: str = "videos"`
  - [ ] `max_file_size_gb: int = 10`
- [ ] Implement `load_from_section()` class method
- [ ] Configure TOML section: `services.storage`
- [ ] Configure environment prefix: `STORAGE_`

#### **Step 2: Service Integration**
- [ ] Update `services/storage/main.py` imports
- [ ] Replace hardcoded `ServiceSettings(port=8003)`
- [ ] Use `StorageServiceConfig.load_from_section()`
- [ ] Update storage logic to use configuration properties
- [ ] Test service startup with configuration

#### **Step 3: Enhanced Health Checks**
- [ ] Verify `/health` endpoint returns configuration status
- [ ] Verify `/config/status` endpoint works
- [ ] Test health checks with and without config.toml

#### **Step 4: Testing**
- [ ] Create unit tests for `StorageServiceConfig`
- [ ] Test TOML section loading
- [ ] Test environment variable overrides
- [ ] Test fallback to defaults
- [ ] Add memory leak tests for configuration loading
- [ ] Test service startup integration

### **🧪 Validation Checklist**
- [ ] Service starts successfully with default configuration
- [ ] Service starts successfully with TOML configuration
- [ ] Environment variables override TOML values (e.g., `STORAGE_BASE_PATH=/custom/path`)
- [ ] Service gracefully handles missing config.toml
- [ ] Service gracefully handles invalid TOML syntax
- [ ] Storage paths are resolved and applied correctly
- [ ] Health endpoints return correct configuration information
- [ ] Memory leak tests pass for configuration operations

### **📁 Files Modified**
- [ ] `services/storage/config.py` (NEW)
- [ ] `services/storage/main.py` (MODIFIED)
- [ ] `tests/unit/test_storage_config.py` (NEW)
- [ ] `tests/memory/test_config_memory_leaks.py` (MODIFIED)

---

## 📋 **Logging Service Integration Checklist**

### **🔧 Implementation Steps**

#### **Step 1: Configuration Class Creation**
- [ ] Create `services/logging/config.py`
- [ ] Implement `LoggingServiceConfig` class extending `ServiceSettings`
- [ ] Add service-specific configuration properties:
  - [ ] `retention_days: int = 30`
  - [ ] `max_file_size_mb: int = 100`
  - [ ] `log_rotation: bool = True`
- [ ] Implement `load_from_section()` class method
- [ ] Configure TOML section: `services.logging`
- [ ] Configure environment prefix: `LOGGING_`

#### **Step 2: Service Integration**
- [ ] Update `services/logging/main.py` imports
- [ ] Replace hardcoded `ServiceSettings(port=8004)`
- [ ] Use `LoggingServiceConfig.load_from_section()`
- [ ] Update logging logic to use configuration properties
- [ ] Test service startup with configuration

#### **Step 3: Enhanced Health Checks**
- [ ] Verify `/health` endpoint returns configuration status
- [ ] Verify `/config/status` endpoint works
- [ ] Test health checks with and without config.toml

#### **Step 4: Testing**
- [ ] Create unit tests for `LoggingServiceConfig`
- [ ] Test TOML section loading
- [ ] Test environment variable overrides
- [ ] Test fallback to defaults
- [ ] Add memory leak tests for configuration loading
- [ ] Test service startup integration

### **🧪 Validation Checklist**
- [ ] Service starts successfully with default configuration
- [ ] Service starts successfully with TOML configuration
- [ ] Environment variables override TOML values (e.g., `LOGGING_RETENTION_DAYS=60`)
- [ ] Service gracefully handles missing config.toml
- [ ] Service gracefully handles invalid TOML syntax
- [ ] Logging settings are applied correctly (retention, rotation)
- [ ] Health endpoints return correct configuration information
- [ ] Memory leak tests pass for configuration operations

### **📁 Files Modified**
- [ ] `services/logging/config.py` (NEW)
- [ ] `services/logging/main.py` (MODIFIED)
- [ ] `tests/unit/test_logging_config.py` (NEW)
- [ ] `tests/memory/test_config_memory_leaks.py` (MODIFIED)

---

## 📋 **CLI Integration Checklist**

### **🔧 Implementation Steps**

#### **Step 1: Dynamic Service URL Loading**
- [ ] Implement `load_service_urls()` function in `cli/main.py`
- [ ] Replace hardcoded `SERVICES` dictionary
- [ ] Update `YTArchiveAPI` class constructor
- [ ] Test service URL loading from TOML
- [ ] Test fallback to default URLs

#### **Step 2: Configuration File Option**
- [ ] Add `--config-file` option to relevant CLI commands
- [ ] Update download command to accept config file
- [ ] Update metadata command to accept config file
- [ ] Update other commands as needed
- [ ] Test CLI commands with custom config files

#### **Step 3: Configuration Validation Enhancement**
- [ ] Extend `_validate_configuration()` function
- [ ] Add TOML file validation
- [ ] Add service section validation
- [ ] Add configuration parameter validation
- [ ] Update validation result structure
- [ ] Test configuration validation with various scenarios

### **🧪 Validation Checklist**
- [ ] CLI loads service URLs from config.toml correctly
- [ ] CLI falls back to default URLs when config.toml missing
- [ ] `--config-file` option works with custom configuration files
- [ ] Configuration validation detects missing config.toml
- [ ] Configuration validation detects invalid TOML syntax
- [ ] Configuration validation detects missing service sections
- [ ] Configuration validation provides helpful error messages
- [ ] All existing CLI functionality continues to work

### **📁 Files Modified**
- [ ] `cli/main.py` (MODIFIED)
- [ ] `tests/cli/test_config_commands.py` (NEW/MODIFIED)

---

## 📋 **Base Service Updates Checklist**

### **🔧 Implementation Steps**

#### **Step 1: Enhanced Health Endpoints**
- [ ] Update `BaseService._configure_routes()` method
- [ ] Enhance `/health` endpoint with configuration status
- [ ] Add `/config/status` endpoint
- [ ] Test health endpoints with various configuration states

#### **Step 2: ServiceSettings Base Class**
- [ ] Ensure `ServiceSettings` supports TOML configuration
- [ ] Verify inheritance works correctly for all service configs
- [ ] Test base configuration functionality

### **🧪 Validation Checklist**
- [ ] All service health endpoints return configuration information
- [ ] `/config/status` endpoint works for all services
- [ ] Base service configuration inheritance works correctly
- [ ] Health checks work with and without configuration files

### **📁 Files Modified**
- [ ] `services/common/base.py` (MODIFIED)

---

## 📊 **Cross-Service Integration Tests**

### **🧪 Integration Testing Checklist**
- [ ] All 5 services start successfully with default configuration
- [ ] All 5 services start successfully with TOML configuration
- [ ] CLI can communicate with all configured services
- [ ] Service discovery works with custom ports/hosts
- [ ] Configuration changes are reflected in service behavior
- [ ] Memory leak tests pass for all configuration operations
- [ ] End-to-end workflows work with configuration
- [ ] Service coordination is not disrupted by configuration changes

### **📈 Performance Testing**
- [ ] Configuration loading performance is acceptable
- [ ] Service startup time is not significantly impacted
- [ ] Memory usage remains within acceptable limits
- [ ] Configuration validation is fast enough for CLI use

---

## ✅ **Final Integration Validation**

### **System-Wide Validation**
- [ ] All services integrate successfully with configuration system
- [ ] CLI commands work with configuration-driven service discovery
- [ ] Configuration validation provides comprehensive feedback
- [ ] All existing tests continue to pass
- [ ] New configuration tests provide adequate coverage
- [ ] Documentation is updated to reflect configuration capabilities
- [ ] Memory leak detection covers configuration operations
- [ ] Error recovery patterns work with configuration loading

### **Quality Gates**
- [ ] Zero breaking changes to existing functionality
- [ ] 100% of existing tests pass
- [ ] New configuration tests achieve 80%+ coverage
- [ ] Memory leak tests pass for all configuration operations
- [ ] Performance regression is within acceptable limits (<10% startup time increase)

---

**Integration Status**: Ready for systematic implementation following these checklists
**Quality Assurance**: Each checklist item must be completed and validated before proceeding to next service
**Documentation**: All checklists completed constitutes full configuration integration
