#!/usr/bin/env python3
"""CI + local: verify bob install seeds empty catalog; discover-apis works on non-CC host."""
from __future__ import annotations

import sys
from pathlib import Path

RUNNER_LIB = Path(__file__).resolve().parents[1] / "lib"
if str(RUNNER_LIB) not in sys.path:
    sys.path.insert(0, str(RUNNER_LIB))

from fresh_install_verify import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
