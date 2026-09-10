"""Dependency-free entry point for the detached experiment manager.

The implementation lives under ``src/bridgetree`` so it can be unit tested as
part of the package.  Executing a Python file from that directory directly is
unsafe, however, because ``bridgetree/types.py`` can shadow the standard-library
``types`` module before the package is installed.  Running it through this
small script keeps the package directory off the import search path and lets a
fresh server use its system Python for the bootstrap step.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

manager = Path(__file__).resolve().parents[1] / "src" / "bridgetree" / "background.py"
sys.argv[0] = str(manager)
runpy.run_path(str(manager), run_name="__main__")
