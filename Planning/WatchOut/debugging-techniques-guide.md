# Debugging Techniques Guide

This guide outlines effective debugging approaches for the YTArchive project, with special emphasis on leveraging specialized debug scripts and tools.

## Standard Debugging Approaches

When encountering issues in the YTArchive codebase, follow these escalating debugging approaches:

1. **Check Logs First**: Review logs in the `logs/` directory structure to identify patterns
2. **Run Unit Tests**: Execute targeted tests related to the problematic component
3. **Use Print Debugging**: Add strategic print statements to trace execution flow
4. **Leverage IDE Debugger**: Set breakpoints and step through code execution
5. **Specialized Debug Scripts**: Use the tools in `tests/debug/` for complex issues

## Specialized Debug Scripts

YTArchive includes purpose-built debugging scripts located in `tests/debug/` for diagnosing complex issues that are difficult to troubleshoot through standard methods.

### Available Debug Scripts

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `debug_exception.py` | Tests exception handling in validation functions | Diagnosing unexpected exception behavior |
| `debug_exception_final.py` | Enhanced exception analysis with full trace | Deep-diving into error propagation |
| `debug_exception_trace.py` | Traces exception flow through multiple layers | Understanding error context across services |
| `debug_invalid_pyproject.py` | Tests handling of invalid configuration | Configuration validation issues |
| `debug_line_by_line.py` | Enables line-by-line execution analysis | When exact execution flow is unclear |
| `debug_mocks.py` | Demonstrates proper mocking techniques | Integration test mocking issues |
| `debug_status_logic.py` | Investigates validation status determination | Status logic problems (warnings vs. errors) |

### Effective Usage

To effectively use these scripts:

```bash
# Run a debug script directly
python -m tests.debug.debug_exception_trace

# Use with specific arguments
python -m tests.debug.debug_status_logic --verbose
```

## For Human Developers

When standard debugging approaches fail:

1. **Choose the appropriate debug script** that most closely matches your issue
2. **Modify parameters** within the script to replicate your specific scenario
3. **Add print statements** to the debug script to get more detailed information
4. **Compare expected vs. actual** state at each step of execution

## For Developer Agents (AI Assistants)

AI coding assistants should leverage these scripts to diagnose issues more effectively:

### Recommended AI Debugging Workflow

1. **Identify the issue domain**: Error handling, configuration validation, status logic, etc.
2. **Select relevant debug script**: Match the script to the issue domain
3. **Run diagnostic command**: Execute the script with appropriate parameters
4. **Analyze output patterns**: Look for divergence from expected behavior
5. **Locate root cause**: Identify exact line or component causing the issue
6. **Propose targeted fix**: Based on precise diagnostic information

### Key Benefits for AI Assistants

- **Isolated Component Testing**: Debug scripts isolate specific components, making root cause identification easier
- **State Visibility**: Get insights into internal state at each execution step
- **Pattern Recognition**: Compare successful vs. failed execution paths
- **Rapid Diagnosis**: Skip time-consuming trial-and-error approaches

## Common Issues and Debug Script Selection

| Issue Type | Recommended Script | Expected Output |
|------------|-------------------|-----------------|
| Exception handling problems | `debug_exception_trace.py` | Full exception propagation chain |
| Configuration validation | `debug_invalid_pyproject.py` | Validation errors and status codes |
| Status logic confusion | `debug_status_logic.py` | Status determination details |
| Mock integration issues | `debug_mocks.py` | Proper mock pattern examples |
| Line-by-line execution | `debug_line_by_line.py` | State changes at each step |

## Creating New Debug Scripts

When creating new debug scripts:

1. Follow the naming convention `debug_[issue_area].py`
2. Add proper docstring explaining purpose
3. Include sys.path.insert before other imports
4. Add appropriate type annotations
5. Avoid shadowing built-in types
6. Document the script in the README.md

## Conclusion

Leveraging these specialized debug scripts can dramatically reduce the time required to identify complex issues. By isolating components and providing detailed execution insights, these tools enable both human developers and AI assistants to pinpoint root causes with greater accuracy.
