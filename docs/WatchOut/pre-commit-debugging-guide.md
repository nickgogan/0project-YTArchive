# Pre-commit Hook Debugging Guide

**Status**: ✅ COMPLETE - Based on systematic debugging session (Jan 2025)
**Context**: Comprehensive pre-commit hook failure resolution

## Overview

This guide provides a systematic approach to debugging and resolving pre-commit hook failures, derived from actual debugging patterns that have proven effective in the YTArchive project.

## 🔍 Diagnostic Strategy

### 1. Initial Assessment
**Always start with a complete picture:**

```bash
# Get full scope of all failing hooks
uv run pre-commit run --all-files

# Then focus on specific hooks
uv run pre-commit run ruff --all-files
uv run pre-commit run mypy --all-files
```

**Key Pattern**: Don't fix errors one-by-one blindly. Understand the full scope first, as some errors may be related or have common root causes.

### 2. Error Categorization
Group errors by type for systematic resolution:

- **Syntax/Linting (Ruff)**: F811 redefinitions, F821 undefined names
- **Type Safety (MyPy)**: Type mismatches, missing imports, parameter issues
- **Formatting (Black)**: Usually auto-fixable
- **Import Issues**: Missing modules, wrong paths

## 🚨 Common Error Patterns & Solutions

### Pattern 1: Ruff F811 - Redefinition Errors

**Signature**: `F811 Redefinition of unused 'function_name' from line X`

**Root Cause**: Multiple functions/commands with identical names in same scope

**Solution Strategy**:
```python
# ❌ PROBLEM: Duplicate command names
@cli.command()
def status(job_id: str, watch: bool):
    """Check job status."""
    pass

@playlist.command()  # This creates another 'status' function!
def status(job_id: str, watch: bool):
    """Check playlist status."""
    pass

# ✅ SOLUTION: Use Click command name mapping
@cli.command()
def status(job_id: str, watch: bool):
    """Check job status."""
    pass

@playlist.command("status")  # CLI command name
def playlist_status(job_id: str, watch: bool):  # Python function name
    """Check playlist status."""
    pass
```

**Detection Pattern**: Look for functions with identical names in the same module, especially after refactoring or adding command groups.

### Pattern 2: MyPy Collection Type Issues

**Signature**: `Unsupported target for indexed assignment ("Collection[str]")` or `"Collection[str]" has no attribute "append"`

**Root Cause**: Using abstract `Collection[str]` type for mutable operations

**Solution Strategy**:
```python
# ❌ PROBLEM: Collection is immutable/abstract
from typing import Collection

def process_data():
    # MyPy infers this as Collection[str] - can't mutate
    results = {"issues": [], "warnings": []}
    results["issues"].append("error")  # ❌ MyPy error!

# ✅ SOLUTION: Explicit mutable types
from typing import Dict, List, Any

def process_data():
    # Explicitly type as mutable Dict
    results: Dict[str, Any] = {
        "issues": [],
        "warnings": [],
        "status": "valid"
    }
    results["issues"].append("error")  # ✅ Works!
```

**Key Imports to Add**:
```python
from typing import Dict, List, Any, Optional
```

### Pattern 3: Pydantic Constructor Type Mismatches

**Signature**: `Argument 1 to "ModelName" has incompatible type "**dict[str, ...]"; expected "str"`

**Root Cause**: Passing serialized string values instead of proper Python objects to Pydantic models

**Solution Strategy**:
```python
# ❌ PROBLEM: Passing string representations
job_data = {
    "job_id": "test-123",
    "job_type": "VIDEO_DOWNLOAD",  # String, not enum!
    "status": "PENDING",           # String, not enum!
    "created_at": "2025-01-31T12:00:00Z",  # String, not datetime!
}
return JobResponse(**job_data)  # ❌ MyPy error!

# ✅ SOLUTION: Pass proper Python objects
from services.common.models import JobType, JobStatus
from datetime import datetime

return JobResponse(
    job_id="test-123",
    job_type=JobType.VIDEO_DOWNLOAD,  # Enum object
    status=JobStatus.PENDING,         # Enum object
    created_at=datetime.now(),        # datetime object
    options=options,
)
```

### Pattern 4: Parameter Name Shadowing

**Signature**: `"bool" has no attribute "dumps"` or similar unexpected attribute errors

**Root Cause**: Parameter names shadowing imported modules

**Solution Strategy**:
```python
# ❌ PROBLEM: Parameter shadows json module
import json

@click.option("--json", is_flag=True)
def command(json: bool):  # Shadows json module!
    if json:
        print(json.dumps(data))  # ❌ bool.dumps() doesn't exist!

# ✅ SOLUTION: Rename parameter
import json

@click.option("--json", "json_output", is_flag=True)  # Map to different name
def command(json_output: bool):  # No shadowing
    if json_output:
        print(json.dumps(data))  # ✅ Uses json module correctly
```

**Common Shadowing Patterns**:
- `json` parameter → `json_output`
- `str` parameter → `string_value`
- `list` parameter → `items` or `values`
- `dict` parameter → `data` or `mapping`

### Pattern 5: Missing Function References

**Signature**: `F821 Undefined name 'function_name'`

**Root Cause**: References to functions that were moved/deleted during refactoring

**Solution Strategy**:
1. **Find the current location**:
   ```bash
   rg "function_name" --type py
   ```

2. **Update imports or references**:
   ```python
   # ❌ Old reference
   from cli.main import _validate_pyproject_file

   # ✅ New reference after refactoring
   from cli.main import _validate_configuration
   ```

3. **Update function calls**:
   ```python
   # ❌ Old call
   result = _validate_pyproject_file()

   # ✅ New call with updated signature
   import asyncio
   result = asyncio.run(_validate_configuration(json_output=False, fix=False))
   ```

## 🛠 Systematic Debugging Workflow

### Step 1: Full Scope Assessment
```bash
# Get complete error picture
uv run pre-commit run --all-files > pre_commit_errors.txt

# Analyze error patterns
grep -E "(error|Error)" pre_commit_errors.txt | sort | uniq -c
```

### Step 2: Prioritize by Impact
1. **Blocking errors first**: Ruff F811, F821 (prevent commits)
2. **Type safety errors**: MyPy constructor, import issues
3. **Enhancement errors**: External library stubs, annotation notes

### Step 3: Pattern-Based Resolution
Use this guide's patterns to resolve similar errors in batches rather than one-by-one.

### Step 4: Iterative Validation
```bash
# Test specific hook after changes
uv run pre-commit run ruff --all-files

# Full validation
uv run pre-commit run --all-files
```

## 🎯 Prevention Strategies

### 1. Development Practices
- **Run pre-commit frequently**: `uv run pre-commit run --all-files` before major commits
- **Use type hints consistently**: Always import `Dict`, `List`, `Any` when needed
- **Avoid parameter shadowing**: Never use built-in/module names as parameters
- **Clean up during refactoring**: Remove old function definitions explicitly

### 2. Code Review Checklist
- [ ] No duplicate function names in same scope
- [ ] All type annotations use proper mutable types (`List`, `Dict` vs `Collection`)
- [ ] Pydantic model constructors use Python objects, not strings
- [ ] No parameter names shadow imported modules
- [ ] All referenced functions exist and are properly imported

### 3. IDE Configuration
Configure your IDE to show MyPy errors in real-time to catch issues before pre-commit.

## 📋 Quick Reference

### Essential Type Imports
```python
from typing import Dict, List, Any, Optional, Union
```

### Safe Parameter Naming
```python
# Good parameter names that don't shadow
json_output, json_format, output_json    # Instead of 'json'
string_value, text_content              # Instead of 'str'
item_list, values, items                # Instead of 'list'
data_dict, mapping, config              # Instead of 'dict'
```

### Pydantic Constructor Pattern
```python
# Always pass Python objects, not serialized strings
return ModelClass(
    enum_field=EnumType.VALUE,        # Not "VALUE"
    datetime_field=datetime.now(),    # Not "2025-01-31T12:00:00Z"
    bool_field=True,                  # Not "true"
    dict_field={"key": "value"},      # Not '{"key": "value"}'
)
```

This guide should be your first reference when encountering pre-commit hook failures.
