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
        # ...
    ```

5.  **Trust the Linter**: Our pre-commit hook runs MyPy. If it fails, do not ignore it. Address the type error before committing.

By following these guidelines, we can maintain a high level of code quality, reduce runtime errors, and create a more maintainable and self-documenting codebase.
