# Click Command Naming and Architecture Guide

**Status**: ✅ COMPLETE - Based on systematic resolution of CLI command conflicts
**Date**: 2025-01-31
**Context**: CLI Command Namespace Conflicts During Enterprise CLI Development

## Overview

This guide documents critical patterns and anti-patterns for structuring Click-based CLI applications with complex command hierarchies. These lessons were learned during the development of a comprehensive CLI with both root-level and nested commands that had naming conflicts.

## 🚨 The Core Problem: Click Command vs Python Function Namespace Collision

### Issue Description

When building complex CLI applications with Click, you often need:
- **Root-level commands**: `ytarchive download video_id`
- **Nested subcommands**: `ytarchive playlist download playlist_url`

This creates a namespace collision where both commands logically want to be named `download`.

### The Manifestation

```python
# ❌ PROBLEMATIC STRUCTURE:
@cli.command()
def download(video_id):  # Root level: ytarchive download
    """Download a single video."""
    pass

@playlist.command()
def download(playlist_url):  # Nested: ytarchive playlist download
    """Download a playlist."""
    pass

# Tests import functions by name:
from cli.main import download  # ❌ Gets the LAST defined function!
```

**Result**:
- `from cli.main import download` imports the playlist function, not the video function
- Tests that expect the video download function fail with confusing errors
- CLI structure appears correct but Python imports are broken

## 🎯 **Solution Patterns**

### Pattern 1: Command Name Mapping (Recommended)

Use Click's command name mapping to decouple CLI command names from Python function names:

```python
# ✅ SOLUTION: Separate CLI names from Python function names

@cli.command("download")  # CLI: ytarchive download
def download_video(video_id):  # Python function: download_video
    """Download a single video."""
    pass

@playlist.command("download")  # CLI: ytarchive playlist download
def download_playlist(playlist_url):  # Python function: download_playlist
    """Download a playlist."""
    pass

# Tests import by function name:
from cli.main import download_video  # ✅ Clear, unambiguous import
```

### Pattern 2: Descriptive Function Names

Use descriptive Python function names that reflect their scope:

```python
# ✅ ALTERNATIVE: Descriptive function names

@cli.command()
def download(video_id):  # CLI: ytarchive download
    """Download a single video."""
    pass

@playlist.command()
def download(playlist_url):  # CLI: ytarchive playlist download
    """Download a playlist."""
    pass

# But use descriptive names for the actual functions:
@cli.command("download")
def download_single_video(video_id):
    pass

@playlist.command("download")
def download_playlist_videos(playlist_url):
    pass
```

### Pattern 3: Explicit Command Groups (Enterprise Scale)

For large CLI applications, use explicit command naming:

```python
# ✅ ENTERPRISE PATTERN: Explicit command structure

# Video operations
@video.command("download")
def download_video(video_id):
    pass

@video.command("info")
def get_video_info(video_id):
    pass

# Playlist operations
@playlist.command("download")
def download_playlist(playlist_url):
    pass

@playlist.command("info")
def get_playlist_info(playlist_url):
    pass

# Usage:
# ytarchive video download VIDEO_ID
# ytarchive playlist download PLAYLIST_URL
```

## 🔧 **Testing Patterns**

### Import Testing with Multiple Commands

```python
# ✅ CORRECT: Import by descriptive function names
from cli.main import download_video, download_playlist

# ✅ CORRECT: Test each function independently
def test_video_download():
    # Direct function testing
    result = download_video("dQw4w9WgXcQ")

def test_playlist_download():
    # Direct function testing
    result = download_playlist("PLtest123")
```

### CLI Integration Testing

```python
# ✅ CORRECT: Test via Click's CliRunner
from click.testing import CliRunner
from cli.main import cli

def test_video_download_cli():
    runner = CliRunner()
    result = runner.invoke(cli, ["download", "dQw4w9WgXcQ"])
    assert result.exit_code == 0

def test_playlist_download_cli():
    runner = CliRunner()
    result = runner.invoke(cli, ["playlist", "download", "PLtest123"])
    assert result.exit_code == 0
```

## 🚨 **Common Anti-Patterns to Avoid**

### Anti-Pattern 1: Function Name Reuse

```python
# ❌ ANTI-PATTERN: Same function names
def download(video_id):     # First definition
    pass

def download(playlist_url): # ❌ Overwrites first definition!
    pass

from cli.main import download  # ❌ Gets second definition only
```

### Anti-Pattern 2: Unclear Command Structure

```python
# ❌ ANTI-PATTERN: Unclear nesting
@cli.command("download-video")      # ytarchive download-video
@cli.command("download-playlist")   # ytarchive download-playlist
# Better to use: ytarchive download vs ytarchive playlist download
```

### Anti-Pattern 3: Inconsistent Naming Conventions

```python
# ❌ ANTI-PATTERN: Mixed naming styles
@cli.command("download")
def downloadVideo(video_id):  # ❌ camelCase

@playlist.command("download")
def download_playlist_cmd(url):  # ❌ Inconsistent suffix
```

## 🎯 **Best Practices**

### 1. Naming Conventions

- **CLI Commands**: Use kebab-case (`download-video`) or single words (`download`)
- **Python Functions**: Use snake_case with descriptive names (`download_video`)
- **Command Groups**: Use singular nouns (`video`, `playlist`, not `videos`)

### 2. Function Organization

```python
# ✅ GOOD: Group related functions
# Video commands
@cli.command("download")
def download_video(...): pass

@cli.command("info")
def get_video_info(...): pass

# Playlist commands
@playlist.command("download")
def download_playlist(...): pass

@playlist.command("info")
def get_playlist_info(...): pass
```

### 3. Documentation and Help

```python
# ✅ GOOD: Clear documentation distinguishes commands
@cli.command("download")
def download_video(video_id):
    """Download a single YouTube video."""
    pass

@playlist.command("download")
def download_playlist(playlist_url):
    """Download all videos from a YouTube playlist."""
    pass
```

### 4. Import Safety

```python
# ✅ SAFE: Import by unique, descriptive names
from cli.main import (
    download_video,      # Not just 'download'
    download_playlist,   # Clear distinction
    get_video_info,      # Descriptive
    list_recovery_plans  # Unambiguous
)
```

## 🚀 **Quick Fix Checklist**

When you encounter CLI naming conflicts:

- [ ] **Identify the conflict**: Which functions have naming collisions?
- [ ] **Check imports**: What functions do tests import by name?
- [ ] **Choose pattern**: Command mapping vs descriptive names vs restructuring?
- [ ] **Update function names**: Use descriptive, unique Python function names
- [ ] **Update imports**: Fix all test imports to use new function names
- [ ] **Test CLI commands**: Verify command line interface still works as expected
- [ ] **Test function imports**: Verify all tests import the correct functions

## 🔍 **Debugging Command Conflicts**

### Quick Test for Import Issues

```bash
# Test which function gets imported:
uv run python -c "from cli.main import download; print(download.__doc__)"

# Should print the docstring of the function you expect
# If it's wrong, you have a naming conflict
```

### CLI Structure Verification

```bash
# Test actual CLI commands work:
uv run python -m cli.main --help                    # Root help
uv run python -m cli.main playlist --help           # Group help
uv run python -m cli.main playlist download --help  # Command help
```

## 📚 **Related Patterns**

- **Error Recovery**: See `error-recovery-patterns-guide.md` for retry patterns in CLI commands
- **Testing**: See `testing-asyncmock-guide.md` for async CLI command testing
- **Rich UI**: See `rich-testing-patterns-guide.md` for testing Rich console output
- **Import Structure**: See `import-path-guide.md` for broader import organization

---

**Key Insight**: Click command names are part of the user interface, while Python function names are part of the code interface. Keep them separate and descriptive to avoid conflicts and improve maintainability.
