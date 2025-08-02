# WatchOut: MyPy Type Stub Recognition Issues with UV Package Manager

**Problem**: MyPy reports "Library stubs not installed for 'X'" errors even when type stubs are properly installed via UV package manager.

> **Related Resources**: This guide complements our [Type Safety and MyPy Compliance Guide](./type-safety-guide.md) with specific solutions for UV environment issues.

## 🚨 **Symptoms**
- MyPy errors: `error: Library stubs not installed for "toml" [import-untyped]`
- Type stubs appear installed when running `uv pip freeze | grep types-`
- Pre-commit hooks fail on mypy but other tools (black, ruff) pass
- Direct `mypy` commands fail with "mypy command not found"

## 🔍 **Root Cause Analysis**

### Primary Issue: Environment Mismatch
The most common cause is **environment mismatch** where:
- Type stubs are installed in UV's managed environment
- Pre-commit hooks run mypy in a different environment (typically using `mirrors-mypy`)
- MyPy cannot find the stubs because it's running in the wrong environment

### Secondary Issue: Function Name Shadowing
MyPy may also report confusing `isinstance` errors when functions shadow built-in types:
```python
# BAD: This shadows the built-in 'list' type
def list(json_output: bool) -> None:
    pass

# Later in code, this confuses mypy:
if isinstance(data, list):  # mypy thinks 'list' refers to the function above!
```

## ✅ **Diagnostic Steps**

### 1. Verify Type Stubs Installation
```bash
# Check if stubs are installed in UV environment
uv pip freeze | grep types-

# Should show entries like:
# types-toml==0.10.8.20240310
```

### 2. Test MyPy in UV Environment
```bash
# This should work if mypy is properly installed
uv run mypy --version

# If this fails with "mypy command not found", mypy isn't installed in UV environment
```

### 3. Check Pre-commit Configuration
Look for `mirrors-mypy` usage in `.pre-commit-config.yaml`:
```yaml
# PROBLEMATIC CONFIGURATION:
-   repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
    -   id: mypy
```

## 🔧 **Solutions**

### Solution 1: Configure Pre-commit to Use UV Environment

Replace the `mirrors-mypy` hook with a local hook that uses `uv run mypy`:

```yaml
# CORRECT CONFIGURATION:
-   repo: local
    hooks:
    -   id: mypy
        name: mypy
        entry: uv run mypy
        language: system
        types: [python]
        require_serial: true
```

### Solution 2: Ensure MyPy is Installed in UV Environment

Add mypy to your dev dependencies:
```bash
uv add --dev mypy
```

Or in `pyproject.toml`:
```toml
[project.optional-dependencies]
dev = [
    "mypy~=1.7.1",
    # ... other dev dependencies
]
```

### Solution 3: Install Missing Type Stubs

After fixing the environment:
```bash
uv run mypy --install-types --non-interactive
```

### Solution 4: Fix Function Name Shadowing

Rename functions that shadow built-in types:
```python
# BEFORE (problematic):
def list(json_output: bool) -> None:
    pass

# AFTER (fixed):
@recovery.command("list")  # Explicitly name the command
def list_plans(json_output: bool) -> None:  # Rename function
    pass
```

## 🎯 **Prevention Best Practices**

1. **Always use UV environment for development tools**:
   ```bash
   uv run mypy
   uv run pytest
   uv run black
   ```

2. **Configure pre-commit hooks consistently**:
   - Use `local` repo with `uv run` for Python tools
   - Avoid `mirrors-*` repos when using UV

3. **Avoid shadowing built-in types**:
   - Never name functions `list`, `dict`, `set`, `str`, etc.
   - Use descriptive names like `list_items`, `show_dict`, etc.

4. **Regular environment sync**:
   ```bash
   uv sync --dev  # Ensure all dev dependencies are installed
   ```

## 🚀 **Quick Fix Checklist**

- [ ] Check `uv pip freeze` shows required type stubs
- [ ] Verify `uv run mypy --version` works
- [ ] Update `.pre-commit-config.yaml` to use `uv run mypy`
- [ ] Add mypy to dev dependencies if missing
- [ ] Run `uv run mypy --install-types --non-interactive`
- [ ] Check for function names shadowing built-in types
- [ ] Test commit with `git commit` to verify all hooks pass

## 📚 **Related Issues**

This pattern applies to other UV + pre-commit combinations:
- pytest in UV environment
- custom linting tools
- any Python tool that requires environment-specific packages

The key principle: **Keep your development tools in the same environment as your dependencies**.

---

**When you encounter "Library stubs not installed" errors, remember: the stubs might be installed, but mypy might be looking in the wrong place!**

## Further Reading

- For general MyPy best practices in this project, see our [Type Safety and MyPy Compliance Guide](./type-safety-guide.md)
- For related environmental issues, check the [Circuit Breaker Integration Patterns Guide](./circuit-breaker-guide.md) which demonstrates proper environment management for testing
- The [Testing AsyncMock Guide](./testing-asyncmock-guide.md) also provides related insights on environment compatibility
