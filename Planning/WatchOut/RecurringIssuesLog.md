# Recurring Issues & Solutions Log

This document tracks significant and long-running issues encountered during YTArchive development, organized for potential conversion into best practices guides.

## 🧪 Testing Issues

### AsyncMock Context Manager Pattern
**Issue**: AsyncMock objects appearing in test output instead of expected values
**Root Cause**: Missing `__aenter__` and `__aexit__` setup for async context managers
**Pattern**: `<AsyncMock name='mock.__aenter__().client.get().status_code'>`
**Solution**: Always set `mock_api.__aenter__.return_value = mock_api` and `mock_api.__aexit__.return_value = None`
**Frequency**: High - affected CLI tests, health commands, integration tests
**Documentation**: ✅ Created `docs/testing-asyncmock-guide.md`

### Test Hanging Issues
**Issue**: CLI tests hanging indefinitely during execution
**Root Cause**: Infinite monitoring loops without proper exit conditions
**Pattern**: Tests with `while True:` loops in CLI monitoring functions
**Solution**: Mock job status to return "completed/failed/cancelled" for loop exit
**Frequency**: Medium - primarily CLI playlist and monitoring tests
**Documentation**: ✅ Done

### Import Path Issues
**Issue**: `ModuleNotFoundError` for relocated modules
**Root Cause**: Test files using outdated import paths after reorganization
**Pattern**: `from tests.memory_leak_detection import` → `from tests.memory.memory_leak_detection import`
**Solution**: Update imports when moving files, use relative imports where appropriate
**Frequency**: High - occurred during test reorganization phases
**Documentation**: ✅ Done

### Click Command Naming Conflicts
**Issue**: CLI tests import wrong function due to namespace collisions in complex command hierarchies
**Root Cause**: Multiple Click commands using same Python function name, causing `from cli.main import download` to get last-defined function
**Pattern**: Tests expecting video download function get playlist download function instead
**Solution**: Use Click command name mapping to separate CLI command names from Python function names: `@playlist.command("download") def download_playlist(...)`
**Frequency**: Medium - affects complex CLI applications with nested command groups
**Documentation**: ✅ Created `click-command-naming-guide.md`

### Test Fixture Discovery
**Issue**: `fixture 'temp_dir' not found` errors
**Root Cause**: Missing fixture imports after centralization
**Pattern**: Tests expecting fixtures not available in their scope
**Solution**: Import fixtures from centralized utilities (`from tests.common.temp_utils import temp_dir`)
**Frequency**: Medium - occurred during centralization efforts
**Documentation**: ✅ Done (Covered in Test Structure & Import Path guides)

## 🔄 Retry & Error Recovery Issues

### Retry Configuration Resolution
**Issue**: Error recovery using default retry attempts instead of strategy config
**Root Cause**: `execute_with_retry` creating new `RetryConfig()` instead of using strategy config
**Pattern**: `retry_config = retry_config or RetryConfig()` # Wrong - default 3 attempts
**Solution**: `retry_config = retry_config or getattr(self.retry_strategy, 'config', RetryConfig())`
**Frequency**: High - affected multiple integration tests
**Documentation**: ✅ Done (Covered in Error Recovery Patterns guide)

### Service Handler Interface Compliance
**Issue**: Service error handlers not implementing required interface methods
**Root Cause**: Missing `get_recovery_suggestions` method, wrong return types
**Pattern**: `handle_error` returning `Dict` instead of `bool`
**Solution**: Implement full `ServiceErrorHandler` interface with correct signatures
**Frequency**: Medium - affected download service integration
**Documentation**: ✅ Done (Covered in Error Recovery Patterns guide)

### Circuit Breaker Failure Counting
**Issue**: Circuit breaker failure count being reset by successful operations
**Root Cause**: Successful job status reports resetting failure count during error recovery
**Pattern**: Circuit breaker not isolating retry operation from reporting operations
**Solution**: Mock non-failing operations or separate retry logic from reporting
**Frequency**: Low - specific to circuit breaker integration tests
**Documentation**: ✅ Done

## 💾 Memory & Performance Issues

### Memory Leak Detection Thresholds
**Issue**: Memory leak tests failing due to strict thresholds
**Root Cause**: Memory growth patterns not accounting for GC timing
**Pattern**: Peak memory exceeding thresholds during stress tests
**Solution**: Adjust thresholds based on actual memory patterns (40MB peak, 8MB final)
**Frequency**: Medium - occurred during memory testing implementation
**Documentation**: ✅ Done

### Long-Running Operation Memory Growth
**Issue**: Memory accumulation during extended retry sequences
**Root Cause**: Sliding window metrics not being cleaned up properly
**Pattern**: Memory growth in AdaptiveStrategy with large windows
**Solution**: Implement proper cleanup in sliding window and metrics collection
**Frequency**: Low - specific to adaptive retry strategy
**Documentation**: ✅ Created `adaptive-memory-cleanup-guide.md`

## 🏗️ Data Model & Validation Issues

### Pydantic Model Path Serialization
**Issue**: `ValidationError` for Path objects in Pydantic models
**Root Cause**: Path objects not JSON serializable for Pydantic validation
**Pattern**: `DownloadRequest` with `Path` objects failing validation
**Solution**: Convert Path objects to strings: `str(temp_storage_dir)`
**Frequency**: Medium - affected E2E workflow tests
**Documentation**: ✅ Done

### DateTime Serialization
**Issue**: DateTime objects not serializing to JSON properly
**Root Cause**: Default JSON encoder not handling datetime objects
**Pattern**: `TypeError: Object of type datetime is not JSON serializable`
**Solution**: Use `model_dump(mode="json")` for Pydantic models
**Frequency**: Medium - affected storage service tests
**Documentation**: ✅ Done (Covered in pydantic-validation-guide.md)

## 🔧 Type Safety Issues

### Pre-commit Hook Complex Failures
**Issue**: Multiple failing pre-commit hooks creating complex debugging scenarios requiring systematic resolution
**Root Cause**: Interdependent errors across Ruff F811, MyPy type issues, constructor mismatches, parameter shadowing
**Patterns**: F811 redefinitions, Collection[str] type errors, Pydantic constructor issues, json parameter shadowing
**Solution**: Use systematic debugging workflow - categorize errors by type, resolve in priority order, use pattern-based fixes
**Frequency**: High during major refactoring, dependency updates, or large feature additions
**Documentation**: ✅ Created `pre-commit-debugging-guide.md`

### MyPy Collection vs Mutable Type Issues
**Issue**: MyPy inferring dict literals as `Collection[str]` instead of mutable `Dict[str, Any]`
**Root Cause**: Type inference choosing abstract Collection over concrete mutable types
**Patterns**: `"Collection[str]" has no attribute "append"`, `Unsupported target for indexed assignment`
**Solution**: Explicit type annotations: `result: Dict[str, Any] = {...}` with proper imports
**Frequency**: High - affects data processing functions with dictionary operations
**Documentation**: ✅ Enhanced `type-safety-guide.md` with Collection vs Dict patterns

### Pydantic Constructor Type Mismatches
**Issue**: MyPy errors when passing dict with string values to Pydantic constructors expecting Python objects
**Root Cause**: Pydantic models expect enum/datetime objects, not serialized string representations
**Patterns**: `Argument 1 to "JobResponse" has incompatible type "**dict[str, ...]"; expected "str"`
**Solution**: Pass Python objects directly: `JobType.VIDEO_DOWNLOAD` not `"VIDEO_DOWNLOAD"`
**Frequency**: Medium - affects service model constructors and test data creation
**Documentation**: ✅ Enhanced `type-safety-guide.md` with Pydantic constructor patterns

### Parameter Name Shadowing
**Issue**: Function parameters shadowing built-in modules causing confusing attribute errors
**Root Cause**: Parameters named `json`, `str`, `list`, etc. shadow imported modules/built-ins
**Patterns**: `"bool" has no attribute "dumps"` when `json` parameter shadows `json` module
**Solution**: Use descriptive parameter names: `json_output`, `string_value`, `item_list`
**Frequency**: Medium - affects CLI commands and utility functions with generic parameter names
**Documentation**: ✅ Enhanced `type-safety-guide.md` with parameter shadowing patterns

### MyPy Type Checking Errors (Legacy)
**Issue**: MyPy errors for `Any` type returns from `getattr()`
**Root Cause**: Dynamic attribute access returning `Any` type
**Pattern**: `getattr(strategy_config, 'field')` causing type errors
**Solution**: Use `isinstance()` checks for proper type narrowing
**Frequency**: Medium - occurred during error recovery refactoring
**Documentation**: ✅ Done

### Optional Type Annotations
**Issue**: Missing `Optional` imports causing type annotation errors
**Root Cause**: Method signatures using `Optional[List[Exception]]` without import
**Pattern**: `error_types: Optional[List[Exception]] = None`
**Solution**: Add `Optional` to typing imports
**Frequency**: Medium - affected integration test files
**Documentation**: ✅ Done (Covered in type-safety-guide.md)

## 🗂️ Project Organization Issues

### Test Structure Reorganization
**Issue**: Scattered test files at project root level
**Root Cause**: Tests created without proper categorization structure
**Pattern**: `test_*.py` files in root instead of categorized directories
**Solution**: Move tests to appropriate subdirectories (`unit/`, `integration/`, `memory/`, etc.)
**Frequency**: Medium - occurred during project maturity phases
**Documentation**: ✅ Done

### Centralized Directory Management
**Issue**: Temporary files and logs scattered across project
**Root Cause**: Services creating directories without central coordination
**Pattern**: `download_service/` at root, temp files in system temp
**Solution**: Centralize all temporary files to `logs/temp/`, all logs to `logs/`
**Frequency**: Medium - occurred during infrastructure improvements
**Documentation**: ✅ Done

### Duplicate Method Issues
**Issue**: Method overrides causing interface compliance failures
**Root Cause**: Old method implementations not removed during refactoring
**Pattern**: Two `get_recovery_suggestions` methods in same file
**Solution**: Remove duplicate/obsolete method implementations during refactoring
**Frequency**: Low - specific to error recovery refactoring
**Documentation**: ✅ Created `refactoring-duplicate-methods-guide.md`

## 🎯 Integration & Coordination Issues

### Service Dependency Chain Failures
**Issue**: Integration tests failing due to service coordination issues
**Root Cause**: Services not properly coordinating during failure scenarios
**Pattern**: Jobs → Storage → Download coordination breaking under retry conditions
**Solution**: Proper error propagation and retry coordination between services
**Frequency**: High - affected multiple integration test phases
**Documentation**: ✅ Done (Covered in Service Coordination guide)

### API Mocking Consistency
**Issue**: Integration tests failing due to inconsistent API mocking
**Root Cause**: Different mock response formats across test files
**Pattern**: Some tests using `MagicMock`, others using proper response structure
**Solution**: Standardize mock response helpers and YouTube API mocking
**Frequency**: Medium - occurred during integration test development
**Documentation**: ✅ Done

## 📊 Priority for Documentation

### High Priority (Frequent, High Impact)
1. **AsyncMock Context Manager Pattern** ✅ Done
2. **Import Path Management** - Guidelines for module reorganization
3. **Retry Configuration Best Practices** - Error recovery patterns
4. **Integration Test Mocking Standards** - Consistent API mocking

### Medium Priority (Moderate Frequency)
5. **Pydantic Model Validation Patterns** - Path/DateTime serialization
6. **Test Structure Organization** - Project test hierarchy standards
7. **Memory Leak Testing Guidelines** - Thresholds and patterns
8. **Type Safety Best Practices** - MyPy compliance patterns

### Low Priority (Specific Cases)
9. **Circuit Breaker Integration Patterns** - Advanced retry scenarios
10. **Centralized Directory Management** - Infrastructure organization
11. **Service Coordination Error Handling** - Multi-service failure patterns

---

**Last Updated**: January 31, 2025
**Total Issues Tracked**: 20+
**Documentation Created**: 20/20 priority guides ✅ COMPLETE
**Next Candidate**: All recurring issues now have comprehensive documentation.
