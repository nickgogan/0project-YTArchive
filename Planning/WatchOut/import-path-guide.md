# Import Path Management Guide

This guide provides comprehensive guidelines for managing import paths in the YTArchive project, covering best practices, common pitfalls, and solutions for module reorganization.

## Repository Structure Overview

### Current Directory Structure
```
YTArchive/
├── cli/                      # Command-line interface
│   ├── __init__.py
│   └── main.py
├── services/                 # Core service implementations
│   ├── __init__.py
│   ├── common/              # Shared utilities and base classes
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── models.py
│   │   └── utils.py
│   ├── download/            # Download service
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── error_handler.py
│   │   └── resume.py
│   ├── error_recovery/      # Error recovery and retry system
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── contracts.py
│   │   ├── types.py
│   │   ├── reporting.py
│   │   ├── retry/
│   │   │   ├── __init__.py
│   │   │   └── strategies.py
│   │   └── example_integration.py
│   ├── jobs/                # Job orchestration service
│   │   ├── __init__.py
│   │   └── main.py
│   ├── logging/             # Centralized logging service
│   │   ├── __init__.py
│   │   └── main.py
│   ├── metadata/            # YouTube metadata service
│   │   ├── __init__.py
│   │   └── main.py
│   └── storage/             # File storage service
│       ├── __init__.py
│       └── main.py
├── tests/                   # Test suite
│   ├── __init__.py
│   ├── conftest.py         # Global test configuration
│   ├── common/             # Shared test utilities
│   │   ├── __init__.py
│   │   ├── temp_utils.py
│   │   └── memory_leak_detection.py
│   ├── cli/                # CLI tests
│   │   ├── __init__.py
│   │   └── test_*.py
│   ├── download/           # Download service tests
│   │   ├── __init__.py
│   │   └── test_*.py
│   ├── error_recovery/     # Error recovery tests
│   │   ├── __init__.py
│   │   └── test_*.py
│   ├── integration/        # Cross-service integration tests
│   │   ├── __init__.py
│   │   └── test_*.py
│   ├── jobs/               # Jobs service tests
│   │   ├── __init__.py
│   │   └── test_*.py
│   ├── logging/            # Logging service tests
│   │   ├── __init__.py
│   │   └── test_*.py
│   ├── memory/             # Memory leak detection tests
│   │   ├── __init__.py
│   │   └── test_*.py
│   ├── metadata/           # Metadata service tests
│   │   ├── __init__.py
│   │   └── test_*.py
│   └── storage/            # Storage service tests
│       ├── __init__.py
│       └── test_*.py
├── Planning/               # Project documentation
└── ytarchive.py           # Main entry point
```

### Package Structure
- **Top-level packages**: `cli`, `services`, `tests`
- **Service packages**: Each service has its own package under `services/`
- **Test packages**: Mirror the service structure under `tests/`
- **Common utilities**: Shared code in `services/common/` and `tests/common/`

## Import Path Best Practices

### 1. Use Absolute Imports for Cross-Package References

✅ **CORRECT - Cross-package imports:**
```python
# In services/download/main.py
from services.common.base import BaseService, ServiceSettings
from services.common.models import ServiceResponse
from services.error_recovery import ErrorRecoveryManager
from services.error_recovery.retry import ExponentialBackoffStrategy

# In tests/download/test_download_service.py
from services.download.main import DownloadService
from services.common.base import ServiceSettings
from tests.common.temp_utils import temp_dir
```

### 2. Use Relative Imports for Intra-Package References

✅ **CORRECT - Within same package:**
```python
# In services/error_recovery/base.py
from .contracts import ErrorReporter, RetryStrategy, ServiceErrorHandler
from .types import ErrorContext, ErrorReport, ErrorSeverity, RetryConfig

# In services/error_recovery/retry/strategies.py
from ..contracts import RetryStrategy
from ..types import RetryConfig, RetryReason
```

### 3. CLI Import Pattern

✅ **CORRECT - CLI imports:**
```python
# In cli/main.py (CLI should be self-contained)
import click
from rich.console import Console
# No direct service imports - use API calls

# In tests/cli/test_health_command.py
from cli.main import _check_system_health, _display_health_status
```

### 4. Test Import Pattern

✅ **CORRECT - Test imports:**
```python
# In tests/services/test_download_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.download.main import DownloadService
from services.common.base import ServiceSettings
from tests.common.temp_utils import temp_dir
```

## Common Import Issues and Solutions

### Issue 1: Module Reorganization Import Errors

**Problem**: After moving test files, imports break
```python
# ❌ WRONG - Old import path after moving files
from tests.memory_leak_detection import MemoryLeakDetector

# Error: ModuleNotFoundError: No module named 'tests.memory_leak_detection'
```

**Solution**: Update import paths to reflect new structure
```python
# ✅ CORRECT - Updated import path
from tests.memory.memory_leak_detection import MemoryLeakDetector
```

### Issue 2: Missing Common Utilities

**Problem**: Test fixture not found after centralization
```python
# ❌ WRONG - Missing fixture import
def test_something(temp_dir):  # fixture 'temp_dir' not found
    pass
```

**Solution**: Import centralized utilities
```python
# ✅ CORRECT - Import from centralized location
from tests.common.temp_utils import temp_dir

def test_something(temp_dir):
    pass
```

### Issue 3: Circular Imports

**Problem**: Two modules importing each other
```python
# services/download/main.py
from services.jobs.main import JobsService

# services/jobs/main.py
from services.download.main import DownloadService
```

**Solution**: Use dependency injection or common interface
```python
# ✅ CORRECT - Use common interface
from services.common.base import BaseService

class DownloadService(BaseService):
    def __init__(self, jobs_service: BaseService):
        self.jobs_service = jobs_service
```

### Issue 4: Deep Import Paths

**Problem**: Very long import paths
```python
# ❌ PROBLEMATIC - Too deep/specific
from services.error_recovery.retry.strategies import ExponentialBackoffStrategy
```

**Solution**: Use package `__init__.py` files for cleaner imports
```python
# In services/error_recovery/__init__.py
from .retry.strategies import ExponentialBackoffStrategy

# In your code
# ✅ CORRECT - Cleaner import
from services.error_recovery import ExponentialBackoffStrategy
```

## File Reorganization Guidelines

### When Moving Files

1. **Update All Import References**
   ```bash
   # Find all references to the old import
   grep -r "from tests.memory_leak_detection import" .

   # Update each reference
   sed -i 's/from tests\.memory_leak_detection import/from tests.memory.memory_leak_detection import/g' file.py
   ```

2. **Update `__init__.py` Files**
   ```python
   # In tests/memory/__init__.py
   from .memory_leak_detection import MemoryLeakDetector
   ```

3. **Test the Changes**
   ```bash
   # Run affected tests
   python -m pytest tests/memory/ -v

   # Check for import errors
   python -c "from tests.memory.memory_leak_detection import MemoryLeakDetector"
   ```

### Creating New Packages

1. **Create `__init__.py` Files**
   ```python
   # In new_package/__init__.py
   """Package documentation."""

   # Export main classes/functions
   from .main import MainClass
   from .utilities import helper_function

   __all__ = ['MainClass', 'helper_function']
   ```

2. **Follow Naming Conventions**
   - Package names: lowercase, underscores if needed (`error_recovery`)
   - Module names: lowercase, underscores if needed (`memory_leak_detection`)
   - Test files: `test_` prefix (`test_download_service.py`)

## Import Path Patterns by Category

### Service Imports
```python
# Service accessing common utilities
from services.common.base import BaseService
from services.common.models import ServiceResponse
from services.common.utils import retry_with_backoff

# Service accessing error recovery
from services.error_recovery import ErrorRecoveryManager
from services.error_recovery.retry import ExponentialBackoffStrategy
from services.error_recovery.types import ErrorContext, RetryConfig

# Service accessing other services (avoid direct imports)
# Use dependency injection instead
```

### Test Imports
```python
# Test accessing service under test
from services.download.main import DownloadService
from services.common.base import ServiceSettings

# Test accessing test utilities
from tests.common.temp_utils import temp_dir
from tests.memory.memory_leak_detection import MemoryLeakDetector

# Test accessing standard libraries
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
```

### CLI Imports
```python
# CLI should be self-contained
import click
from rich.console import Console
from rich.progress import Progress

# CLI accessing utilities (minimal)
from pathlib import Path
from typing import Optional, Dict, Any
```

## Testing Import Changes

### 1. Import Verification Script
```python
#!/usr/bin/env python3
"""Verify all imports work correctly."""

import sys
import importlib

def verify_imports():
    """Test critical imports."""
    imports_to_test = [
        'services.download.main',
        'services.common.base',
        'services.error_recovery',
        'tests.common.temp_utils',
        'tests.memory.memory_leak_detection',
        'cli.main',
    ]

    for module_name in imports_to_test:
        try:
            importlib.import_module(module_name)
            print(f"✅ {module_name}")
        except ImportError as e:
            print(f"❌ {module_name}: {e}")
            sys.exit(1)

    print("All imports verified successfully!")

if __name__ == "__main__":
    verify_imports()
```

### 2. pytest Import Testing
```bash
# Test imports without running tests
python -m pytest --collect-only tests/

# Run specific test categories
python -m pytest tests/memory/ -v
python -m pytest tests/integration/ -v
```

## IDE Configuration

### VS Code Settings
```json
{
    "python.analysis.extraPaths": [
        ".",
        "./services",
        "./tests"
    ],
    "python.analysis.autoSearchPaths": true,
    "python.defaultInterpreterPath": ".venv/bin/python"
}
```

### PyCharm Settings
1. Mark `services/` and `tests/` as source roots
2. Set project interpreter to virtual environment
3. Enable auto-import organization

## Troubleshooting Import Issues

### Common Error Messages and Solutions

#### 1. `ModuleNotFoundError: No module named 'X'`
```python
# Check if module exists
import os
print(os.path.exists('services/download/main.py'))

# Verify package structure
print(os.path.exists('services/__init__.py'))
print(os.path.exists('services/download/__init__.py'))
```

#### 2. `ImportError: cannot import name 'X' from 'Y'`
```python
# Check what's actually available
import services.download.main
print(dir(services.download.main))
```

#### 3. `ImportError: attempted relative import with no known parent package`
```python
# ❌ WRONG - Relative import in script
from .utilities import helper

# ✅ CORRECT - Use absolute import
from services.common.utilities import helper
```

## Migration Checklist

When reorganizing imports:

- [ ] Map old import paths to new paths
- [ ] Update all import statements
- [ ] Update `__init__.py` files
- [ ] Run import verification script
- [ ] Run full test suite
- [ ] Update documentation
- [ ] Update IDE configuration
- [ ] Commit changes with clear message

## Quick Reference

### Good Import Patterns
```python
# Absolute imports for cross-package
from services.common.base import BaseService
from tests.common.temp_utils import temp_dir

# Relative imports within package
from .contracts import RetryStrategy
from ..types import ErrorContext

# Standard library imports first
import asyncio
import json
from pathlib import Path

# Third-party imports second
import pytest
from unittest.mock import AsyncMock

# Local imports last
from services.download.main import DownloadService
```

### Bad Import Patterns
```python
# ❌ Mixed absolute/relative without clear pattern
from services.common.base import BaseService
from .utilities import helper

# ❌ Importing everything
from services.download.main import *

# ❌ Circular imports
from services.jobs.main import JobsService  # In download service
from services.download.main import DownloadService  # In jobs service
```

---

This guide should prevent most import path issues during development and reorganization. Always test imports after making changes and update documentation accordingly.
