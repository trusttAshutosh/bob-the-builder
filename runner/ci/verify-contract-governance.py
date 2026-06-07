#!/usr/bin/env python3
"""CI entry: block contract weakening without recorded human approval."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_LIB = ROOT / "runner" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from contract_governance import resolve_base_ref, verify_governance  # noqa: E402


def _merge_base(root: Path) -> str:
    for pair in (
        ("HEAD", "origin/main"),
        ("HEAD", "origin/master"),
        ("HEAD", "main"),
    ):
        out = subprocess.run(
            ["git", "merge-base", pair[0], pair[1]],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    return resolve_base_ref(root, None)


def main() -> int:
    p = argparse.ArgumentParser(description="Verify contract governance (no silent weakening)")
    p.add_argument("--base", default="", help="Git ref to compare (default: merge-base with main)")
    p.add_argument("--check", action="store_true", help="Run check (default)")
    args = p.parse_args()

    base = args.base.strip()
    if not base:
        env_base = os.environ.get("BOB_CONTRACT_BASE", "").strip()
        if env_base:
            base = env_base
        elif os.environ.get("GITHUB_EVENT_NAME") == "pull_request":
            gh_base = os.environ.get("GITHUB_BASE_REF", "main")
            base = gh_base if gh_base.startswith("origin/") else f"origin/{gh_base}"
            # merge-base is safer when origin ref missing in shallow clone
            mb = _merge_base(ROOT)
            if mb:
                base = mb
        else:
            base = _merge_base(ROOT)

    rc, msg = verify_governance(ROOT, base_ref=base)
    print(msg)
    return rc


if __name__ == "__main__":
    sys.exit(main())
