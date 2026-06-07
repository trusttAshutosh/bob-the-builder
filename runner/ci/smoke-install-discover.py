#!/usr/bin/env python3
"""CI smoke: bob install + bob discover-apis against runner/tests/fixtures/ci-host."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "runner"
FIXTURE = RUNNER / "tests" / "fixtures" / "ci-host"
EXPECTED_APIS = ("smokeGetHealth", "smokeSubmitOrder")


def _run_bob(command: str, *, cwd: Path, env: dict[str, str]) -> int:
    proc = subprocess.run(
        [sys.executable, str(REPO / "bob.py"), command],
        cwd=str(cwd),
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        print(f"FAIL: bob {command} exited {proc.returncode}", file=sys.stderr)
    return proc.returncode


def main() -> int:
    if not FIXTURE.is_dir():
        print(f"Missing fixture host: {FIXTURE}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="bob-smoke-") as td:
        ws = Path(td) / "workspace"
        ws.mkdir()
        host = ws / "novopay-fixture-host"
        shutil.copytree(FIXTURE, host)

        bob_home = Path(td) / "bob-home"
        bob_local = Path(td) / "bob-local"
        env = os.environ.copy()
        env["BUILDER_WORKSPACE_ROOT"] = str(ws)
        env["BOB_PRODUCT_ROOT"] = str(REPO)
        env["BOB_HOST_REPO"] = str(host)
        env["BOB_HOME"] = str(bob_home)
        env["BOB_LOCAL"] = str(bob_local)
        env["BOB_IGNORE_PREFS"] = "1"
        env["PYTHONPATH"] = str(RUNNER / "lib")

        if _run_bob("install", cwd=REPO, env=env) != 0:
            return 1
        if not (bob_home / ".bob-initialized").is_file():
            print("FAIL: bob install did not seed BOB_HOME", file=sys.stderr)
            return 1

        if _run_bob("discover-apis", cwd=host, env=env) != 0:
            return 1

        apis_dir = bob_home / "api-catalog" / "apis"
        missing = [name for name in EXPECTED_APIS if not (apis_dir / f"{name}.yaml").is_file()]
        if missing:
            print(f"FAIL: missing API skeletons: {', '.join(missing)}", file=sys.stderr)
            return 1

        index = bob_home / "api-catalog" / "index.yaml"
        if not index.is_file():
            print("FAIL: missing api-catalog/index.yaml", file=sys.stderr)
            return 1

        print(f"smoke-install-discover: OK ({len(EXPECTED_APIS)} APIs)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
