#!/usr/bin/env python3
"""Bob the Builder CLI entry."""
from __future__ import annotations

import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from builder_cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
