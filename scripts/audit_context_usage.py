#!/usr/bin/env python3
"""Thin wrapper - prefer: bob context-audit"""
from __future__ import annotations

import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "runner" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from context_audit import run_context_audit  # noqa: E402

if __name__ == "__main__":
    sys.exit(run_context_audit(sys.argv[1:]))
