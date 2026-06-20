#!/usr/bin/env python3
"""Bob Cursor hook runner - do not edit; logic lives in `bob cursor-hook`."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _read_bob_py() -> Path | None:
    bob_py_file = Path.home() / ".cursor" / "hooks" / ".bob-py"
    if not bob_py_file.is_file():
        return None
    raw = bob_py_file.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_file() else None


def _subprocess_kwargs() -> dict:
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if flags:
            return {"creationflags": flags}
    return {}


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv
    kind = (args[1] if len(args) > 1 else "").strip().lower()
    bob_py = _read_bob_py()
    if not bob_py:
        if kind == "stop":
            print("{}")
        return 0

    kwargs = _subprocess_kwargs()
    if kind == "session":
        subprocess.run(
            [sys.executable, str(bob_py), "cursor-hook", "session"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **kwargs,
        )
        return 0
    if kind == "stop":
        os.environ["HOOK_STOP_JSON"] = sys.stdin.read()
        proc = subprocess.run(
            [sys.executable, str(bob_py), "cursor-hook", "stop"],
            **kwargs,
        )
        return proc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
