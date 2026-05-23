#!/usr/bin/env python3
"""Bob the Builder — product CLI entry."""
from __future__ import annotations

import runpy
from pathlib import Path

runpy.run_path(
    str(Path(__file__).resolve().parent / "runner" / "bob-the-builder.py"),
    run_name="__main__",
)
