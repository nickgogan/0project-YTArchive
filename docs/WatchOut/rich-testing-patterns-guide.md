# 📚 Rich Library Testing Patterns Guide

This guide provides the standard, robust pattern for testing functions that generate output using the `rich` library. Adhering to this pattern ensures that tests are reliable, easy to debug, and not tightly coupled to implementation details.

---

## 🎯 The Core Problem: Brittle Output Tests

Testing `rich` output can be challenging. Two common but flawed approaches often lead to brittle tests:

1.  **Asserting on `print` output**: Patching `console.print` and asserting that a specific string (e.g., a table title) was in the arguments is unreliable. `rich` renders complex components, and the exact string might not be passed directly to `print`.
2.  **Mocking `rich` components**: Patching `rich.table.Table` or other components is an anti-pattern. It couples the test to the implementation and can break the rendering logic of other components, leading to confusing `NotRenderableError` exceptions.

These approaches caused significant delays in fixing the CLI diagnostics tests.

## ✅ The Standard Solution: Record and Export

The correct and most robust way to test `rich` output is to treat the function's output as a whole and verify the final rendered text. This is achieved using `rich`'s built-in testing capabilities.

### Step 1: Make Your Function Testable (Dependency Injection)

Modify the function that produces `rich` output to accept an optional `console` object. This allows you to "inject" a special test console during testing.

**Before:**
```python
# cli/main.py

console = Console()

def _display_diagnostics_results(diagnostics_data: Dict[str, Any]):
    """Display diagnostics results in rich format."""
    # ... logic uses the global 'console' object
    console.print(...)
```

**After (Testable):**
```python
# cli/main.py

console = Console() # Default console for the app

def _display_diagnostics_results(diagnostics_data: Dict[str, Any], console: Optional[Console] = None):
    """Display diagnostics results in rich format."""
    # If no console is provided, use the default one
    if console is None:
        from cli.main import console as default_console
        console = default_console

    # ... logic uses the provided or default 'console' object
    console.print(...)
```

### Step 2: Use a Recording Console in Your Test

In your test, create a `Console` instance with `record=True`, pass it to your function, and then assert against the exported text.

```python
# tests/cli/test_diagnostics_command.py

from rich.console import Console

def test_display_diagnostics_results_with_testing_infrastructure(self):
    # 1. Arrange: Prepare your test data
    diagnostics_data = {
        # ... valid data that should produce the desired output
    }

    # 2. Act: Create a recording console and call the function
    test_console = Console(record=True, width=120) # Use a fixed width for consistent output
    _display_diagnostics_results(diagnostics_data, console=test_console)

    # 3. Assert: Check the final rendered text
    output = test_console.export_text()
    assert "Testing Infrastructure" in output
    assert "Unit Tests" in output
```

### 💡 Key Benefits of This Pattern

- **Robustness**: It tests the final, user-visible output, not the implementation details.
- **Reliability**: It is not affected by the internal rendering logic of `rich`.
- **Clarity**: The test's intent is clear: "Does the final output contain this text?"
- **Maintainability**: The test is less likely to break if the internal implementation of the display function is refactored.
