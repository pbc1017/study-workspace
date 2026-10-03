#!/usr/bin/env python3
"""Run from any cwd without installing packages."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_workspace.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
