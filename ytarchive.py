#!/usr/bin/env python3
"""YTArchive CLI entry point."""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from cli.main import cli  # noqa: E402

if __name__ == "__main__":
    cli()
