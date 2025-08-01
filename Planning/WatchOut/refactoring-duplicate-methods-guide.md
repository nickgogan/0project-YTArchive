# Refactoring Duplicate Methods Guide

**Status**: ✅ COMPLETE - Based on interface compliance failures during error recovery refactoring
**Date**: 2025-01-31
**Context**: Duplicate Method Issues causing interface compliance failures

## Overview

This guide addresses a common but subtle issue that occurs during refactoring: duplicate method definitions that cause interface compliance failures, unexpected behavior, and hard-to-debug issues. The most common manifestation is when old method implementations aren't properly removed during interface updates.

## 🚨 The Core Problem: Ghost Methods from Refactoring

### Issue Description

During interface refactoring, developers often:
1. Add new method implementations to match updated interfaces
2. Forget to remove old method implementations
3. End up with multiple methods with the same name in the same class
4. Experience confusing behavior where the "wrong" method gets called

### Manifestation

```python
# ❌ PROBLEMATIC PATTERN: Duplicate methods after refactoring
class DownloadErrorHandler:
    def __init__(self):
        self.recovery_manager = ErrorRecoveryManager()

    # OLD METHOD (should have been removed)
    def get_recovery_suggestions(self, error: Exception) -> List[str]:
        """Old implementation - returns list of strings."""
        return ["retry download", "check connection"]

    def handle_error(self, error: Exception, context: Dict) -> bool:
        # Business logic here
        return True

    # NEW METHOD (added during interface update)
    def get_recovery_suggestions(self, error: Exception, context: ErrorContext) -> RecoveryPlan:
        """New implementation - returns RecoveryPlan object."""
        return RecoveryPlan(
            suggestions=["retry with backoff", "fallback to lower quality"],
            severity=ErrorSeverity.RECOVERABLE
        )
```

**Result**:
- Python uses the **last defined method**, silently overriding the first
- Interface compliance checks may pass or fail unpredictably
- Tests written for the old method may still pass, masking the problem
- Production code may call the wrong method signature

## 🎯 **Detection Patterns**

### Pattern 1: Method Signature Mismatch Errors

```python
# Symptoms in logs/errors:
TypeError: get_recovery_suggestions() takes 2 positional arguments but 3 were given
AttributeError: 'list' object has no attribute 'suggestions'
```

### Pattern 2: MyPy/Linting Warnings

```python
# MyPy warnings:
error: Name "get_recovery_suggestions" already defined on line 15  [no-redef]
```

### Pattern 3: Interface Compliance Test Failures

```python
# Interface tests fail intermittently:
AssertionError: Expected RecoveryPlan, got List[str]
```

## 🔧 **Prevention Strategies**

### Strategy 1: Systematic Refactoring Process (Recommended)

Use a systematic approach to interface updates:

```python
# ✅ STEP-BY-STEP REFACTORING PROCESS

# Step 1: Comment out old method (don't delete yet)
class DownloadErrorHandler:
    # def get_recovery_suggestions(self, error: Exception) -> List[str]:
    #     """OLD - marked for removal after interface update."""
    #     return ["retry download", "check connection"]

    # Step 2: Implement new method with new signature
    def get_recovery_suggestions(self, error: Exception, context: ErrorContext) -> RecoveryPlan:
        """NEW - matches updated interface."""
        return RecoveryPlan(
            suggestions=["retry with backoff", "fallback to lower quality"],
            severity=ErrorSeverity.RECOVERABLE
        )

    # Step 3: Update all call sites
    # Step 4: Run all tests
    # Step 5: Remove commented old method
```

### Strategy 2: Interface Validation Decorators

Add runtime validation to catch signature mismatches:

```python
# ✅ SOLUTION: Interface validation decorator
from functools import wraps
from typing import get_type_hints
import inspect

def implements_interface(interface_class):
    """Decorator to validate that a class implements an interface correctly."""
    def decorator(cls):
        # Get interface methods
        interface_methods = {
            name: method for name, method in inspect.getmembers(interface_class, inspect.isfunction)
        }

        # Validate each method
        for method_name, interface_method in interface_methods.items():
            if not hasattr(cls, method_name):
                raise TypeError(f"{cls.__name__} missing required method: {method_name}")

            cls_method = getattr(cls, method_name)

            # Check signature compatibility
            interface_sig = inspect.signature(interface_method)
            cls_sig = inspect.signature(cls_method)

            if interface_sig != cls_sig:
                raise TypeError(
                    f"{cls.__name__}.{method_name} signature mismatch.\n"
                    f"Expected: {interface_sig}\n"
                    f"Got: {cls_sig}"
                )

        return cls
    return decorator

# Usage:
@implements_interface(ServiceErrorHandler)
class DownloadErrorHandler:
    def get_recovery_suggestions(self, error: Exception, context: ErrorContext) -> RecoveryPlan:
        # Implementation here
        pass
```

### Strategy 3: Automated Duplicate Detection

Use static analysis to detect duplicate methods:

```python
# ✅ SOLUTION: Pre-commit hook for duplicate detection
#!/usr/bin/env python3
"""detect_duplicate_methods.py - Pre-commit hook to detect duplicate methods."""

import ast
import sys
from collections import defaultdict
from pathlib import Path

class DuplicateMethodDetector(ast.NodeVisitor):
    def __init__(self):
        self.methods = defaultdict(list)
        self.current_class = None

    def visit_ClassDef(self, node):
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node):
        if self.current_class:
            method_key = f"{self.current_class}.{node.name}"
            self.methods[method_key].append(node.lineno)

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)  # Same logic for async methods

def check_file_for_duplicates(file_path: Path) -> bool:
    """Check a Python file for duplicate methods. Returns True if duplicates found."""
    try:
        with open(file_path) as f:
            tree = ast.parse(f.read())

        detector = DuplicateMethodDetector()
        detector.visit(tree)

        has_duplicates = False
        for method, line_numbers in detector.methods.items():
            if len(line_numbers) > 1:
                print(f"DUPLICATE METHOD: {method} at lines {line_numbers} in {file_path}")
                has_duplicates = True

        return has_duplicates

    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}")
        return True  # Treat syntax errors as failures

if __name__ == "__main__":
    files_to_check = sys.argv[1:]
    has_any_duplicates = False

    for file_path in files_to_check:
        if file_path.endswith('.py'):
            if check_file_for_duplicates(Path(file_path)):
                has_any_duplicates = True

    sys.exit(1 if has_any_duplicates else 0)
```

## 🔧 **Resolution Strategies**

### Strategy 1: Method Archaeology

When duplicates are discovered, systematically determine which to keep:

```python
# ✅ SYSTEMATIC DUPLICATE RESOLUTION

# Step 1: Identify all duplicates
def get_recovery_suggestions(self, error: Exception) -> List[str]:  # Line 15
    """Version 1: Returns string list."""
    return ["retry", "fallback"]

def get_recovery_suggestions(self, error: Exception, context: ErrorContext) -> RecoveryPlan:  # Line 25
    """Version 2: Returns RecoveryPlan."""
    return RecoveryPlan(suggestions=["retry with backoff"])

# Step 2: Determine which version is correct
# - Check interface definition
# - Check call sites
# - Check test expectations
# - Check git history for intent

# Step 3: Migrate call sites to correct version
# Step 4: Remove incorrect version
# Step 5: Add tests to prevent regression
```

### Strategy 2: Gradual Migration with Deprecation

For public APIs, use deprecation warnings:

```python
# ✅ SOLUTION: Deprecation-based migration
import warnings
from typing import Union, overload

class DownloadErrorHandler:
    @overload
    def get_recovery_suggestions(self, error: Exception) -> List[str]: ...

    @overload
    def get_recovery_suggestions(self, error: Exception, context: ErrorContext) -> RecoveryPlan: ...

    def get_recovery_suggestions(self, error: Exception, context: ErrorContext = None) -> Union[List[str], RecoveryPlan]:
        """Get recovery suggestions for an error.

        Args:
            error: The exception that occurred
            context: Error context (required in v2.0+)

        Returns:
            RecoveryPlan if context provided, List[str] for backward compatibility
        """
        if context is None:
            warnings.warn(
                "get_recovery_suggestions() without context is deprecated. "
                "Use get_recovery_suggestions(error, context) instead.",
                DeprecationWarning,
                stacklevel=2
            )
            # Legacy behavior
            return ["retry download", "check connection"]
        else:
            # New behavior
            return RecoveryPlan(
                suggestions=["retry with backoff", "fallback to lower quality"],
                severity=ErrorSeverity.RECOVERABLE
            )
```

## 🧪 **Testing Strategies**

### Test 1: Interface Compliance Testing

```python
# ✅ CORRECT: Interface compliance test
import pytest
from services.error_recovery.contracts import ServiceErrorHandler

def test_download_error_handler_implements_interface():
    """Test that DownloadErrorHandler correctly implements ServiceErrorHandler."""
    handler = DownloadErrorHandler()

    # Test method exists
    assert hasattr(handler, 'get_recovery_suggestions')

    # Test method signature
    import inspect
    method = getattr(handler, 'get_recovery_suggestions')
    sig = inspect.signature(method)

    # Verify parameter count and types
    params = list(sig.parameters.keys())
    assert 'error' in params
    assert 'context' in params

    # Test return type annotation
    return_annotation = sig.return_annotation
    assert return_annotation == RecoveryPlan or 'RecoveryPlan' in str(return_annotation)
```

### Test 2: Method Uniqueness Testing

```python
# ✅ CORRECT: Method uniqueness test
def test_no_duplicate_methods():
    """Test that classes don't have duplicate method definitions."""
    import ast
    import inspect

    # Get source code of class
    source = inspect.getsource(DownloadErrorHandler)
    tree = ast.parse(source)

    # Find all method definitions
    methods = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(node.name)

    # Check for duplicates
    method_counts = {}
    for method in methods:
        method_counts[method] = method_counts.get(method, 0) + 1

    duplicates = {method: count for method, count in method_counts.items() if count > 1}
    assert not duplicates, f"Duplicate methods found: {duplicates}"
```

## 🚨 **Anti-Patterns to Avoid**

### Anti-Pattern 1: Quick Fix Without Investigation

```python
# ❌ ANTI-PATTERN: Removing methods without understanding
class Handler:
    # def old_method(self): pass  # ❌ Just commented out, never investigated

    def old_method(self, new_param):  # ❌ Quick fix without checking call sites
        pass
```

### Anti-Pattern 2: Ignoring Linter Warnings

```python
# ❌ ANTI-PATTERN: Suppressing warnings instead of fixing
class Handler:
    def method(self):  # type: ignore  # ❌ Suppressing duplicate method warning
        pass

    def method(self, param):  # This silently overwrites the first!
        pass
```

### Anti-Pattern 3: Copy-Paste Refactoring

```python
# ❌ ANTI-PATTERN: Copy-paste without cleanup
class NewHandler(OldHandler):
    # Copied all methods from OldHandler...
    def method(self): pass  # From OldHandler

    # ...then added new methods with same names
    def method(self, new_param): pass  # Overwrites inherited method!
```

## 🎯 **Best Practices**

### 1. Refactoring Checklist
- [ ] **Document intent**: Why is this method changing?
- [ ] **Identify all call sites**: Where is this method used?
- [ ] **Update tests first**: Test-driven refactoring
- [ ] **Use systematic process**: Comment old, implement new, migrate, remove
- [ ] **Run full test suite**: Ensure no regressions
- [ ] **Check for duplicates**: Use static analysis tools

### 2. Prevention Measures
- [ ] **Pre-commit hooks**: Check for duplicate methods
- [ ] **Interface validation**: Runtime checks for interface compliance
- [ ] **Code review focus**: Review for duplicate method definitions
- [ ] **Linter configuration**: Enable duplicate method detection

### 3. Team Practices
- [ ] **Refactoring documentation**: Document major interface changes
- [ ] **Migration guides**: Provide upgrade paths for breaking changes
- [ ] **Version compatibility**: Use deprecation warnings for public APIs

## 🚀 **Quick Fix Checklist**

When duplicate methods are discovered:

- [ ] **Stop and investigate**: Don't just delete one randomly
- [ ] **Check git history**: Understand why both methods exist
- [ ] **Find all call sites**: Search codebase for method usage
- [ ] **Check test coverage**: What do tests expect?
- [ ] **Verify interface contracts**: Which signature is correct?
- [ ] **Migrate systematically**: Update call sites before removing methods
- [ ] **Add prevention**: Add tests/hooks to prevent recurrence

## 📚 **Related Patterns**

- **Interface Design**: See `error-recovery-patterns-guide.md` for interface patterns
- **Testing**: See `testing-asyncmock-guide.md` for testing refactored code
- **Type Safety**: See `type-safety-guide.md` for signature validation

---

**Key Insight**: Duplicate methods are often symptoms of incomplete refactoring. Always investigate the intent behind each version before removing any code.
