# Type Safety and MyPy Compliance Guide

This guide outlines best practices for ensuring type safety in the YTArchive project using MyPy. Adhering to these standards is crucial for catching bugs early, improving code readability, and enabling better developer tooling (like autocompletion).

## 1. Core Principle: Strive for Full Type Coverage

Our goal is to have a fully type-annotated codebase. MyPy is integrated into our pre-commit hooks, meaning that code with type errors cannot be committed. This enforces a high standard of quality and prevents type-related bugs from entering the main branch.

## 2. Common MyPy Issues and Solutions

Based on our project history, two issues have appeared frequently. Here are the standard solutions for them.

### Issue 1: Handling Dynamic Attributes with `getattr()`

**Problem**: MyPy correctly infers that the `getattr()` function returns a value of type `Any`. This sacrifices type safety, as MyPy cannot check how the returned value is used. This was a specific issue in our `ErrorRecoveryManager` when accessing a `RetryConfig` from a generic `RetryStrategy`.

**Error Message**: `error: "Any" has no attribute "..."` or similar warnings about using an untyped value.

**Solution**: Use `isinstance()` to perform a runtime type check. This acts as a type guard, narrowing the type from `Any` to a specific, known type within the `if` block, satisfying MyPy.

#### Incorrect Pattern
```python
# ❌ WRONG: MyPy cannot verify the type of 'strategy_config'
# and will complain if you try to access its attributes.

class ErrorRecoveryManager:
    def __init__(self, retry_strategy: RetryStrategy):
        self.retry_strategy = retry_strategy

    async def execute_with_retry(self, ..., retry_config: Optional[RetryConfig] = None):
        if retry_config is None:
            # getattr returns 'Any', losing type safety
            strategy_config = getattr(self.retry_strategy, "config", None)

            # This line would trigger a MyPy error because strategy_config is 'Any'
            if strategy_config and strategy_config.max_attempts > 3:
                pass
```

#### Correct Pattern
```python
# ✅ CORRECT: Use isinstance() to provide a type guard for MyPy.

class ErrorRecoveryManager:
    def __init__(self, retry_strategy: RetryStrategy):
        self.retry_strategy = retry_strategy

    async def execute_with_retry(self, ..., retry_config: Optional[RetryConfig] = None):
        if retry_config is None:
            strategy_config = getattr(self.retry_strategy, "config", None)

            # This isinstance() check narrows the type of strategy_config
            # from 'Any' to 'RetryConfig' inside this block.
            if isinstance(strategy_config, RetryConfig):
                # MyPy now knows that strategy_config is a RetryConfig object
                # and will allow access to its attributes.
                retry_config = strategy_config
            else:
                retry_config = RetryConfig() # Fallback to default
```

### Issue 2: Missing `Optional` Type Annotations

**Problem**: A function signature uses `Optional[...]` or defaults a parameter to `None` without importing `Optional` from the `typing` module. This leads to a `NameError` at runtime or a MyPy error during static analysis.

**Context**: This issue appeared frequently in our integration tests when defining method signatures that accepted optional lists of exceptions.

**Solution**: Always ensure `Optional` is imported from the `typing` module whenever you define an optional argument.

#### Incorrect Pattern
```python
# ❌ WRONG: 'Optional' is used without being imported.
from typing import List

# This will raise a NameError: name 'Optional' is not defined
def get_error_report(error_types: Optional[List[Exception]] = None):
    pass
```

#### Correct Pattern
```python
# ✅ CORRECT: Import 'Optional' from the 'typing' module.
from typing import List, Optional

# This is now a valid type hint.
def get_error_report(error_types: Optional[List[Exception]] = None):
    # Note: 'Optional[X]' is just shorthand for 'Union[X, None]'.
    pass
```

## 3. General MyPy Best Practices

1.  **Be Specific**: Prefer specific types over generic ones. Use `List[str]` instead of `list`, and `Dict[str, Any]` instead of `dict`.

2.  **Avoid `Any`**: Only use `typing.Any` as a last resort when a type is truly dynamic and cannot be narrowed. Every use of `Any` is a hole in the type system.

3.  **Annotate Everything**: All function signatures (arguments and return types) and module-level variables should be annotated.

    ```python
    # ✅ GOOD: Full annotation
    DEFAULT_TIMEOUT: float = 10.0

    def fetch_data(url: str, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        # ...
        return {"data": ...}
    ```

4.  **Use Type Aliases**: For complex, repeated types, create a type alias to improve readability.

    ```python
    from typing import Dict, Any, List, Tuple

    # Create a type alias for a complex data structure
    YouTubeAPIResponse = Dict[str, Any]
    VideoBatch = List[Tuple[str, YouTubeAPIResponse]]

    def process_batch(batch: VideoBatch) -> None:
        # Implementation code here...
    ```

5.  **Trust the Linter**: Our pre-commit hook runs MyPy. If it fails, do not ignore it. Address the type error before committing.

## 4. UV Environment Management for MyPy

When using the UV package manager (as we do in this project), special consideration is needed for MyPy and type stub management.

### Pre-commit Hook Configuration

Use the local hook pattern with `uv run mypy` rather than mirrors-mypy:

```yaml
# CORRECT CONFIGURATION for .pre-commit-config.yaml:
-   repo: local
    hooks:
    -   id: mypy
        name: mypy
        entry: uv run mypy
        language: system
        types: [python]
        require_serial: true
```

### Type Stub Installation & Management

To ensure MyPy can find your type stubs when using UV:

1. Always install type stubs in the same environment as your dependencies:
   ```bash
   uv add --dev types-toml types-requests  # etc
   ```

2. When adding new imports, check if type stubs are needed:
   ```bash
   uv run mypy --install-types --non-interactive
   ```

3. Regularly sync your environment to ensure consistency:
   ```bash
   uv sync --dev
   ```

4. Run development tools through the UV environment:
   ```bash
   uv run mypy  # instead of just 'mypy'
   uv run pytest  # instead of just 'pytest'
   ```

> **⚠️ WatchOut!** Even when type stubs are correctly installed, environment mismatches can cause MyPy to report "Library stubs not installed" errors. For detailed troubleshooting, see our [MyPy UV Environment Mismatch Guide](./mypy-uv-environment-mismatch.md).

## 6. Advanced Type Issues: Collection vs Mutable Types

**Problem**: MyPy infers dictionary literals as `Collection[str]` which doesn't support mutable operations.

**Error Messages**:
- `Unsupported target for indexed assignment ("Collection[str]")`
- `"Collection[str]" has no attribute "append"`

**Root Cause**: `Collection` is an abstract base class that doesn't guarantee mutability.

### Issue 3: Dictionary Type Inference

#### Incorrect Pattern
```python
# ❌ WRONG: MyPy may infer this as Collection, not Dict
def validate_config():
    result = {
        "status": "valid",
        "issues": [],        # List that needs .append()
        "warnings": [],      # List that needs .append()
        "configs": {}        # Dict that needs item assignment
    }

    result["issues"].append("error")      # ❌ MyPy error if Collection
    result["configs"]["new_key"] = "val"  # ❌ MyPy error if Collection
    return result
```

#### Correct Pattern
```python
# ✅ CORRECT: Explicitly type as mutable Dict
from typing import Dict, List, Any

def validate_config() -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "status": "valid",
        "issues": [],
        "warnings": [],
        "configs": {}
    }

    result["issues"].append("error")      # ✅ Works - Dict[str, Any]
    result["configs"]["new_key"] = "val"  # ✅ Works - Dict[str, Any]
    return result
```

**Key Solution**: Always import and use specific mutable types:
```python
from typing import Dict, List, Any, Optional
```

## 7. Pydantic Model Constructor Type Safety

**Problem**: Passing serialized string values instead of proper Python objects to Pydantic model constructors.

**Error Message**: `Argument 1 to "ModelName" has incompatible type "**dict[str, ...]"; expected "str"`

### Issue 4: Model Constructor Type Mismatches

#### Incorrect Pattern
```python
# ❌ WRONG: Passing string representations
job_data = {
    "job_id": "test-123",
    "job_type": "VIDEO_DOWNLOAD",           # String, not enum!
    "status": "PENDING",                    # String, not enum!
    "created_at": "2025-01-31T12:00:00Z",  # String, not datetime!
    "options": {"quality": "720p"}
}

# This fails because Pydantic expects Python objects
return JobResponse(**job_data)  # ❌ MyPy error!
```

#### Correct Pattern
```python
# ✅ CORRECT: Pass proper Python objects
from services.common.models import JobType, JobStatus
from datetime import datetime

# Explicit constructor with proper types
return JobResponse(
    job_id="test-123",
    job_type=JobType.VIDEO_DOWNLOAD,    # Enum object
    status=JobStatus.PENDING,           # Enum object
    created_at=datetime.now(),          # datetime object
    options={"quality": "720p"},
)
```

**Key Principle**: Pydantic models expect Python objects, not their serialized string representations.

## 8. Parameter Name Shadowing Prevention

**Problem**: Parameter names that shadow imported modules cause confusing attribute errors.

**Error Message**: `"bool" has no attribute "dumps"` (when `json` parameter shadows `json` module)

### Issue 5: Built-in and Module Shadowing

#### Incorrect Pattern
```python
# ❌ WRONG: Parameter shadows json module
import json

@click.option("--json", is_flag=True)
def process_data(data: Dict, json: bool):  # Shadows json module!
    if json:
        return json.dumps(data)  # ❌ Tries to call bool.dumps()!
```

#### Correct Pattern
```python
# ✅ CORRECT: Use descriptive, non-shadowing parameter names
import json

@click.option("--json", "json_output", is_flag=True)  # Map to different name
def process_data(data: Dict, json_output: bool):
    if json_output:
        return json.dumps(data)  # ✅ Uses json module correctly
```

**Safe Parameter Naming Patterns**:
```python
# Common shadowing issues and solutions
json_output, json_format     # Instead of 'json'
string_value, text_content   # Instead of 'str'
item_list, values, items     # Instead of 'list'
data_dict, mapping, config   # Instead of 'dict'
type_name, object_type       # Instead of 'type'
```

## 9. Type Safety Checklist

Before committing code, verify:

- [ ] All dictionary/list literals have explicit type annotations when used mutably
- [ ] Pydantic model constructors receive Python objects, not string representations
- [ ] No parameter names shadow built-in modules or functions
- [ ] All `from typing import` statements include necessary types (`Dict`, `List`, `Any`)
- [ ] `isinstance()` used for type narrowing instead of `getattr()` with `Any`
- [ ] All `Optional` imports are present when using `Optional[Type]`

By following these guidelines, we can maintain a high level of code quality, reduce runtime errors, and create a more maintainable and self-documenting codebase.
