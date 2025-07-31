# YTArchive Debug Scripts

This directory contains specialized debugging tools for investigating complex issues in the YTArchive codebase. These scripts are not part of the standard test suite but are valuable for diagnosing specific problems.

## Purpose

These debug scripts serve multiple purposes:
- Investigating edge cases that are difficult to reproduce in unit tests
- Debugging complex exception handling behavior
- Testing validation logic with problematic inputs
- Demonstrating error recovery patterns

## Available Debug Scripts

| Script | Purpose |
|--------|---------|
| `debug_exception.py` | Tests exception handling in validation functions with mocked exceptions. Useful for diagnosing how the system responds to unexpected file system errors. |
| `debug_exception_final.py` | Provides enhanced exception analysis with full trace information, offering deeper insights into error propagation. |
| `debug_exception_trace.py` | Traces exception flow through multiple layers of the application, with special focus on service and error context. |
| `debug_invalid_pyproject.py` | Tests how the application handles malformed or invalid pyproject.toml files, important for configuration validation. |
| `debug_line_by_line.py` | Enables line-by-line execution analysis for complex code paths, with detailed state inspection at each step. |
| `debug_mocks.py` | Demonstrates proper mocking techniques for external services and dependencies, useful for testing isolated components. |
| `debug_status_logic.py` | Investigates status logic in validation processes, particularly useful for understanding "warnings_only" vs "issues_found" status determination. |

## Usage

These scripts can be run directly or with specific arguments to diagnose particular issues:

```bash
# Run a debug script
python -m tests.debug.debug_exception_trace

# Run with specific arguments
python -m tests.debug.debug_status_logic --verbose
```

## Development Notes

- All scripts have been updated to comply with project linting standards
- Import order follows the project convention (sys.path.insert before other imports)
- Type annotations are properly implemented
- Functions in debug scripts avoid shadowing built-in types (e.g., `list`, `dict`)

## When to Use

Consider using these scripts when:
- Standard unit tests aren't revealing the root cause of an issue
- You need to trace complex exception flows
- You want to understand how validation logic handles edge cases
- You're introducing changes to error handling or recovery logic

These tools are particularly valuable for new developers trying to understand the system's behavior in exceptional circumstances.
