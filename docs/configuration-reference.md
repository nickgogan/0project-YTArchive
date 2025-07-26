# YTArchive Configuration Reference

## Overview

This document provides a complete reference for all configuration options, environment variables, and settings available in YTArchive. All services support multiple configuration methods with clear precedence rules.

## Configuration Hierarchy

Configuration is loaded in the following order (highest precedence first):

1. **Command-line arguments** - `--port 8001`
2. **Environment variables** - `YTARCHIVE_JOBS_PORT=8001`
3. **Configuration files** - `config/production.yaml`
4. **Default values** - Built-in defaults

## Global Environment Variables

### Core Settings

| Variable | Description | Type | Default | Required |
|----------|-------------|------|---------|----------|
| `YOUTUBE_API_KEY` | YouTube Data API v3 key | string | None | **Yes** |
| `YTARCHIVE_ENV` | Runtime environment | enum | `development` | No |
| `YTARCHIVE_LOG_LEVEL` | Logging verbosity | enum | `INFO` | No |
| `YTARCHIVE_CONFIG_FILE` | Path to configuration file | string | `config/default.yaml` | No |

**Valid values for `YTARCHIVE_ENV`:** `development`, `production`, `testing`
**Valid values for `YTARCHIVE_LOG_LEVEL`:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

### Storage Paths

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `YTARCHIVE_OUTPUT_DIR` | Base directory for downloads | path | `./downloads` |
| `YTARCHIVE_STORAGE_DIR` | Metadata storage directory | path | `./storage` |
| `YTARCHIVE_RECOVERY_PLANS_DIR` | Recovery plans directory | path | `./logs/recovery_plans` |
| `YTARCHIVE_LOGS_DIR` | Logs directory | path | `./logs` |
| `YTARCHIVE_TEMP_DIR` | Temporary files directory | path | `/tmp/ytarchive` |

### Performance Settings

| Variable | Description | Type | Default | Range |
|----------|-------------|------|---------|-------|
| `YTARCHIVE_MAX_CONCURRENT` | Max concurrent downloads | int | `3` | 1-20 |
| `YTARCHIVE_WORKER_THREADS` | Worker threads per service | int | `4` | 1-16 |
| `YTARCHIVE_DOWNLOAD_TIMEOUT` | Download timeout (seconds) | int | `3600` | 60-7200 |
| `YTARCHIVE_METADATA_CACHE_TTL` | Metadata cache TTL (seconds) | int | `3600` | 300-86400 |
| `YTARCHIVE_API_RATE_LIMIT` | API requests per minute | int | `100` | 10-1000 |

### Network Configuration

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `YTARCHIVE_BIND_HOST` | Host to bind services | string | `127.0.0.1` |
| `YTARCHIVE_JOBS_PORT` | Jobs service port | int | `8001` |
| `YTARCHIVE_METADATA_PORT` | Metadata service port | int | `8002` |
| `YTARCHIVE_DOWNLOAD_PORT` | Download service port | int | `8003` |
| `YTARCHIVE_STORAGE_PORT` | Storage service port | int | `8004` |

## Service-Specific Configuration

### Jobs Service Configuration

#### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `YTARCHIVE_JOBS_PORT` | Service port | `8001` |
| `YTARCHIVE_JOBS_WORKERS` | Number of workers | `4` |
| `YTARCHIVE_JOBS_MAX_QUEUE_SIZE` | Maximum job queue size | `1000` |
| `YTARCHIVE_JOBS_TIMEOUT` | Job execution timeout | `7200` |
| `YTARCHIVE_JOBS_RETRY_ATTEMPTS` | Failed job retry attempts | `3` |
| `YTARCHIVE_JOBS_RETRY_DELAY` | Delay between retries (seconds) | `300` |

#### YAML Configuration

```yaml
jobs:
  port: 8001
  workers: 4
  max_queue_size: 1000
  job_timeout: 7200
  retry:
    attempts: 3
    delay: 300
    exponential_backoff: true
  coordination:
    service_discovery: true
    health_check_interval: 30
  queue:
    persistence: true
    persistence_file: "storage/job_queue.json"
```

### Metadata Service Configuration

#### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `YTARCHIVE_METADATA_PORT` | Service port | `8002` |
| `YTARCHIVE_METADATA_API_KEY` | YouTube API key | None |
| `YTARCHIVE_METADATA_CACHE_TTL` | Cache TTL (seconds) | `3600` |
| `YTARCHIVE_METADATA_CACHE_SIZE` | Maximum cache entries | `10000` |
| `YTARCHIVE_METADATA_API_QUOTA` | Daily API quota limit | `10000` |
| `YTARCHIVE_METADATA_RATE_LIMIT` | Requests per minute | `100` |
| `YTARCHIVE_METADATA_BATCH_SIZE` | Batch request size | `50` |

#### YAML Configuration

```yaml
metadata:
  port: 8002
  youtube_api:
    key: "${YOUTUBE_API_KEY}"
    quota_limit: 10000
    rate_limit_per_minute: 100
    timeout: 30
    region: "US"
  cache:
    ttl: 3600
    max_entries: 10000
    cleanup_interval: 600
    persistent: true
    file: "storage/metadata_cache.json"
  batch:
    enabled: true
    size: 50
    timeout: 60
```

### Download Service Configuration

#### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `YTARCHIVE_DOWNLOAD_PORT` | Service port | `8003` |
| `YTARCHIVE_DOWNLOAD_MAX_CONCURRENT` | Max concurrent downloads | `3` |
| `YTARCHIVE_DOWNLOAD_TIMEOUT` | Download timeout | `3600` |
| `YTARCHIVE_DOWNLOAD_TEMP_DIR` | Temporary download directory | `/tmp/ytarchive` |
| `YTARCHIVE_DOWNLOAD_QUALITY` | Default quality | `best` |
| `YTARCHIVE_DOWNLOAD_FORMAT` | Default format | `mp4` |
| `YTARCHIVE_DOWNLOAD_MAX_SIZE` | Max file size (bytes) | `5368709120` |

#### YAML Configuration

```yaml
download:
  port: 8003
  concurrency:
    max_downloads: 3
    max_fragments: 4
    timeout: 3600
  paths:
    temp_dir: "/tmp/ytarchive"
    output_template: "%(title)s [%(id)s].%(ext)s"
  ytdlp:
    options:
      format: "best[height<=1080]"
      writesubtitles: true
      writeautomaticsub: false
      writethumbnail: true
      ignoreerrors: false
      no_warnings: false
      extractflat: false
    extractors:
      youtube:
        skip_dash_manifest: false
        player_skip_js: true
  quality:
    default: "best"
    fallback: "worst"
    preferences:
      - "1080p"
      - "720p"
      - "480p"
      - "360p"
  limits:
    max_file_size: 5368709120  # 5GB
    max_duration: 14400  # 4 hours
    min_duration: 1
```

### Storage Service Configuration

#### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `YTARCHIVE_STORAGE_PORT` | Service port | `8004` |
| `YTARCHIVE_STORAGE_BASE_PATH` | Base storage path | `./downloads` |
| `YTARCHIVE_STORAGE_METADATA_PATH` | Metadata storage path | `./storage` |
| `YTARCHIVE_STORAGE_MAX_FILE_SIZE` | Max file size | `5368709120` |
| `YTARCHIVE_STORAGE_ENABLE_SEARCH` | Enable search indexing | `true` |
| `YTARCHIVE_STORAGE_CLEANUP_INTERVAL` | Cleanup interval (seconds) | `86400` |

#### YAML Configuration

```yaml
storage:
  port: 8004
  paths:
    base: "./downloads"
    metadata: "./storage"
    recovery_plans: "./logs/recovery_plans"
    temp: "/tmp/ytarchive"
  organization:
    structure: "flat"  # flat, date, channel
    naming: "title_id"  # title_id, id_only, title_only
    max_filename_length: 255
  limits:
    max_file_size: 5368709120  # 5GB
    max_total_size: 1099511627776  # 1TB
    max_files: 100000
  search:
    enabled: true
    index_content: true
    index_path: "storage/search_index.json"
  cleanup:
    enabled: true
    interval: 86400  # 24 hours
    keep_failed_downloads: 604800  # 7 days
    temp_file_ttl: 3600  # 1 hour
```

## Advanced Configuration

### Logging Configuration

#### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `YTARCHIVE_LOG_LEVEL` | Global log level | `INFO` |
| `YTARCHIVE_LOG_FILE` | Log file path | `logs/ytarchive.log` |
| `YTARCHIVE_LOG_MAX_SIZE` | Max log file size | `100MB` |
| `YTARCHIVE_LOG_BACKUP_COUNT` | Number of backup files | `5` |
| `YTARCHIVE_LOG_FORMAT` | Log message format | See below |

#### YAML Configuration

```yaml
logging:
  level: INFO
  handlers:
    console:
      enabled: true
      level: INFO
      format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file:
      enabled: true
      level: DEBUG
      path: "logs/ytarchive.log"
      max_size: "100MB"
      backup_count: 5
      format: "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
  loggers:
    ytarchive.jobs:
      level: INFO
    ytarchive.metadata:
      level: INFO
    ytarchive.download:
      level: INFO
    ytarchive.storage:
      level: INFO
    yt_dlp:
      level: WARNING
```

**Default log format:**
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

### Security Configuration

#### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `YTARCHIVE_SECRET_KEY` | Application secret key | Auto-generated |
| `YTARCHIVE_API_KEY_HEADER` | API key header name | `X-API-Key` |
| `YTARCHIVE_CORS_ENABLED` | Enable CORS | `false` |
| `YTARCHIVE_CORS_ORIGINS` | Allowed CORS origins | `[]` |
| `YTARCHIVE_RATE_LIMIT_ENABLED` | Enable rate limiting | `true` |

#### YAML Configuration

```yaml
security:
  secret_key: "${YTARCHIVE_SECRET_KEY}"
  api_keys:
    header: "X-API-Key"
    required: false
    keys:
      - "your-api-key-here"
  cors:
    enabled: false
    origins:
      - "http://localhost:3000"
      - "https://yourdomain.com"
    methods:
      - "GET"
      - "POST"
      - "PUT"
      - "DELETE"
    headers:
      - "Content-Type"
      - "Authorization"
  rate_limiting:
    enabled: true
    requests_per_minute: 60
    burst_size: 10
    storage: "memory"  # memory, redis
```

### Monitoring Configuration

#### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `YTARCHIVE_METRICS_ENABLED` | Enable metrics collection | `true` |
| `YTARCHIVE_METRICS_PORT` | Metrics server port | `9090` |
| `YTARCHIVE_HEALTH_CHECK_INTERVAL` | Health check interval | `30` |
| `YTARCHIVE_MONITORING_ENABLED` | Enable monitoring | `true` |

#### YAML Configuration

```yaml
monitoring:
  enabled: true
  metrics:
    enabled: true
    port: 9090
    path: "/metrics"
    include_system: true
  health_checks:
    enabled: true
    interval: 30
    timeout: 10
    endpoints:
      - path: "/health"
        checks:
          - "service_status"
          - "database_connection"
          - "disk_space"
          - "memory_usage"
  alerts:
    enabled: false
    webhook_url: ""
    thresholds:
      error_rate: 0.05
      response_time: 5000
      memory_usage: 0.8
      disk_usage: 0.9
```

## Configuration Files

### Default Configuration File Structure

Create `config/default.yaml`:

```yaml
# YTArchive Default Configuration
version: "1.0"
environment: development

# Global settings
global:
  log_level: INFO
  max_concurrent: 3
  worker_threads: 4

# Service configurations
services:
  jobs:
    port: 8001
    workers: 4
    max_queue_size: 1000

  metadata:
    port: 8002
    youtube_api:
      key: "${YOUTUBE_API_KEY}"
      quota_limit: 10000

  download:
    port: 8003
    max_concurrent: 3
    timeout: 3600

  storage:
    port: 8004
    base_path: "./downloads"

# Paths
paths:
  output: "./downloads"
  storage: "./storage"
  work_plans: "./work_plans"
  logs: "./logs"
  temp: "/tmp/ytarchive"

# Logging
logging:
  level: INFO
  file: "logs/ytarchive.log"
  max_size: "100MB"
  backup_count: 5

# Performance
performance:
  max_concurrent_downloads: 3
  download_timeout: 3600
  metadata_cache_ttl: 3600
  api_rate_limit: 100
```

### Production Configuration File

Create `config/production.yaml`:

```yaml
# YTArchive Production Configuration
version: "1.0"
environment: production

# Global settings
global:
  log_level: WARNING
  max_concurrent: 10
  worker_threads: 8

# Service configurations
services:
  jobs:
    port: 8001
    workers: 8
    max_queue_size: 5000
    retry:
      attempts: 5
      delay: 600

  metadata:
    port: 8002
    youtube_api:
      key: "${YOUTUBE_API_KEY}"
      quota_limit: 50000
      rate_limit_per_minute: 200
    cache:
      ttl: 7200
      max_entries: 50000

  download:
    port: 8003
    max_concurrent: 10
    timeout: 7200
    ytdlp:
      options:
        format: "best[height<=1080]"
        writesubtitles: true

  storage:
    port: 8004
    base_path: "/opt/ytarchive/downloads"
    limits:
      max_file_size: 10737418240  # 10GB
      max_total_size: 10995116277760  # 10TB

# Production paths
paths:
  output: "/opt/ytarchive/downloads"
  storage: "/opt/ytarchive/storage"
  recovery_plans: "/opt/ytarchive/logs/recovery_plans"
  logs: "/opt/ytarchive/logs"
  temp: "/tmp/ytarchive"

# Logging
logging:
  level: WARNING
  handlers:
    console:
      enabled: false
    file:
      enabled: true
      level: INFO
      path: "/opt/ytarchive/logs/ytarchive.log"

# Security
security:
  api_keys:
    required: true
  rate_limiting:
    enabled: true
    requests_per_minute: 120

# Monitoring
monitoring:
  enabled: true
  metrics:
    enabled: true
    port: 9090
  health_checks:
    interval: 30
```

### Development Configuration File

Create `config/development.yaml`:

```yaml
# YTArchive Development Configuration
version: "1.0"
environment: development

# Global settings
global:
  log_level: DEBUG
  max_concurrent: 2
  worker_threads: 2

# Service configurations
services:
  jobs:
    port: 8001
    workers: 2

  metadata:
    port: 8002
    youtube_api:
      key: "${YOUTUBE_API_KEY}"
    cache:
      ttl: 1800

  download:
    port: 8003
    max_concurrent: 2

  storage:
    port: 8004
    base_path: "./dev_downloads"

# Development paths
paths:
  output: "./dev_downloads"
  storage: "./dev_storage"
  logs: "./dev_logs"

# Logging
logging:
  level: DEBUG
  handlers:
    console:
      enabled: true
      level: DEBUG
    file:
      enabled: true
      level: DEBUG

# Security (relaxed for development)
security:
  api_keys:
    required: false
  cors:
    enabled: true
    origins:
      - "http://localhost:3000"
      - "http://localhost:8080"
```

## Command-Line Arguments

### Global Arguments

All services support these common arguments:

```bash
python services/{service}/main.py [OPTIONS]

Options:
  --port INTEGER          Service port (overrides config)
  --host TEXT            Host to bind to (default: 127.0.0.1)
  --config-file PATH     Configuration file path
  --log-level TEXT       Log level (DEBUG|INFO|WARNING|ERROR|CRITICAL)
  --workers INTEGER      Number of worker threads
  --help                 Show help message
```

### Service-Specific Arguments

#### Jobs Service
```bash
python services/jobs/main.py [OPTIONS]

Additional Options:
  --max-queue-size INTEGER    Maximum job queue size
  --job-timeout INTEGER       Job execution timeout in seconds
  --retry-attempts INTEGER    Number of retry attempts for failed jobs
```

#### Metadata Service
```bash
python services/metadata/main.py [OPTIONS]

Additional Options:
  --api-key TEXT             YouTube API key
  --cache-ttl INTEGER        Cache TTL in seconds
  --rate-limit INTEGER       API rate limit per minute
  --batch-size INTEGER       Batch request size
```

#### Download Service
```bash
python services/download/main.py [OPTIONS]

Additional Options:
  --max-concurrent INTEGER   Maximum concurrent downloads
  --timeout INTEGER          Download timeout in seconds
  --temp-dir PATH           Temporary directory for downloads
  --quality TEXT            Default quality setting
```

#### Storage Service
```bash
python services/storage/main.py [OPTIONS]

Additional Options:
  --base-path PATH          Base storage directory
  --max-file-size INTEGER   Maximum file size in bytes
  --enable-search BOOLEAN   Enable search functionality
```

## Configuration Validation

### Environment Variable Validation

YTArchive validates all configuration values on startup:

```python
# Example validation rules
VALIDATION_RULES = {
    'YTARCHIVE_MAX_CONCURRENT': {'type': int, 'min': 1, 'max': 20},
    'YTARCHIVE_LOG_LEVEL': {'type': str, 'choices': ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']},
    'YTARCHIVE_DOWNLOAD_TIMEOUT': {'type': int, 'min': 60, 'max': 7200},
    'YOUTUBE_API_KEY': {'type': str, 'required': True, 'min_length': 30}
}
```

### Configuration Check Command

Validate your configuration:

```bash
# Check current configuration
python cli/main.py config check

# Check specific configuration file
python cli/main.py config check --config-file config/production.yaml

# Validate environment variables
python cli/main.py config validate-env
```

## Configuration Examples

### Docker Compose Configuration

```yaml
# docker-compose.yml
version: '3.8'

services:
  ytarchive-jobs:
    build: .
    command: python services/jobs/main.py
    environment:
      - YOUTUBE_API_KEY=${YOUTUBE_API_KEY}
      - YTARCHIVE_ENV=production
      - YTARCHIVE_LOG_LEVEL=INFO
      - YTARCHIVE_JOBS_PORT=8001
    ports:
      - "8001:8001"
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs

  ytarchive-metadata:
    build: .
    command: python services/metadata/main.py
    environment:
      - YOUTUBE_API_KEY=${YOUTUBE_API_KEY}
      - YTARCHIVE_METADATA_PORT=8002
    depends_on:
      - ytarchive-jobs
```

### Kubernetes ConfigMap

```yaml
# ytarchive-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ytarchive-config
data:
  YTARCHIVE_ENV: "production"
  YTARCHIVE_LOG_LEVEL: "INFO"
  YTARCHIVE_MAX_CONCURRENT: "10"
  YTARCHIVE_WORKER_THREADS: "8"
  YTARCHIVE_OUTPUT_DIR: "/data/downloads"
  YTARCHIVE_STORAGE_DIR: "/data/storage"
---
apiVersion: v1
kind: Secret
metadata:
  name: ytarchive-secrets
type: Opaque
stringData:
  YOUTUBE_API_KEY: "your-api-key-here"
```

## Troubleshooting Configuration

### Common Configuration Issues

1. **Missing YouTube API Key**
   ```
   Error: YOUTUBE_API_KEY environment variable is required
   Solution: Set the environment variable or add to config file
   ```

2. **Invalid Port Configuration**
   ```
   Error: Port 8001 is already in use
   Solution: Change port or stop conflicting service
   ```

3. **Permission Denied on Directories**
   ```
   Error: Permission denied: '/opt/ytarchive/downloads'
   Solution: Check directory permissions and ownership
   ```

4. **Configuration File Not Found**
   ```
   Error: Configuration file not found: config/production.yaml
   Solution: Create the file or specify correct path
   ```

### Configuration Debugging

Enable debug logging to troubleshoot configuration issues:

```bash
export YTARCHIVE_LOG_LEVEL=DEBUG
python services/jobs/main.py
```

View loaded configuration:
```bash
python cli/main.py config show
```

Test configuration:
```bash
python cli/main.py config test
```

## Migration Between Versions

### Configuration Migration

When upgrading YTArchive versions:

1. **Backup current configuration**:
   ```bash
   cp config/production.yaml config/production.yaml.backup
   ```

2. **Check for deprecated settings**:
   ```bash
   python cli/main.py config migrate --dry-run
   ```

3. **Apply migration**:
   ```bash
   python cli/main.py config migrate
   ```

### Environment Variable Changes

| Old Variable | New Variable | Version |
|-------------|--------------|---------|
| `YTDL_API_KEY` | `YOUTUBE_API_KEY` | v1.0 |
| `MAX_DOWNLOADS` | `YTARCHIVE_MAX_CONCURRENT` | v1.0 |

---

## Best Practices

### Configuration Management

1. **Use environment-specific config files**:
   - `config/development.yaml`
   - `config/staging.yaml`
   - `config/production.yaml`

2. **Keep secrets in environment variables**:
   ```bash
   export YOUTUBE_API_KEY="secret-key"
   ```

3. **Version control configuration templates**:
   ```bash
   config/
   ├── development.yaml
   ├── production.yaml.template
   └── staging.yaml
   ```

4. **Validate configuration in CI/CD**:
   ```bash
   python cli/main.py config validate
   ```

5. **Use configuration management tools**:
   - Ansible for deployment
   - Helm for Kubernetes
   - Terraform for infrastructure

### Security Best Practices

1. **Never commit secrets to version control**
2. **Use restricted API keys with minimum required permissions**
3. **Regularly rotate API keys**
4. **Set appropriate file permissions** (`600` for config files)
5. **Use environment variable injection** in containerized environments

---

*YTArchive Configuration Reference - Complete Settings Guide*
