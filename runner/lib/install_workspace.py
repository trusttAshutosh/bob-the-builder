"""bob install — seed assets/local under this repo only."""
from __future__ import annotations

import sys
from pathlib import Path

from bob_home import LOCAL_SUB, bob_product_root, ensure_bob_home
from host_repo import runner_bootstrap_repo, workspace_root
from setup_prefs import load_prefs_into_environ
from workspace_env import WORKSPACE_ENV


def install_workspace(*, force: bool = False, workspace_launchers: bool = False) -> int:
    load_prefs_into_environ()
    ws = workspace_root()
    if not ws:
        print(
            f"{WORKSPACE_ENV} is not set. Run: bob setup\n"
            "Enter the parent folder of your service git clones.",
            file=sys.stderr,
        )
        return 1

    ws = ws.resolve()
    product = bob_product_root()
    clone = runner_bootstrap_repo().resolve()

    from cleanup_workspace import cleanup_workspace

    cleanup_workspace(apply=True)

    if product.resolve() != clone.resolve():
        expected = ws / "bob-the-builder"
        print(
            f"Bob product root is {product}\n"
            f"This CLI runs from {clone}\n"
            f"Clone bob-the-builder at: {expected}",
            file=sys.stderr,
        )
        return 1

    ensure_bob_home()
    print(f"Product folder: {product}")
    print("  runner/  (this git repo)")
    print("  assets/  (empty catalogs; grow via discover-apis / sync-graph)")
    print("  assets/examples/  (reference packs, e.g. novopay-cc)")
    print("  local/   (user.env, agent, WireMock runtime)")
    print()
    print("Run Bob only from this repo:")
    print("  python bob.py <command>")
    print("From a service repo:")
    print("  python ../bob-the-builder/bob.py <command>")

    if workspace_launchers:
        launcher_py = ws / "bob.py"
        launcher_cmd = ws / "bob.cmd"
        bob_entry = product / "bob.py"
        if not bob_entry.is_file():
            print(f"Missing {bob_entry}", file=sys.stderr)
            return 1
        py_body = '''#!/usr/bin/env python3
"""Optional workspace shortcut — prefer: bob-the-builder/bob.py"""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).parent / "bob-the-builder" / "bob.py"), run_name="__main__")
'''
        cmd_body = r'''@echo off
cd /d "%~dp0"
python "%~dp0bob-the-builder\bob.py" %*
'''
        if force or not launcher_py.exists():
            launcher_py.write_text(py_body, encoding="utf-8")
            launcher_cmd.write_text(cmd_body, encoding="utf-8")
            print(f"Optional workspace shortcuts: {launcher_py} , {launcher_cmd}")
        else:
            print(f"Shortcuts exist: {launcher_py}  (use install --launchers --force to rewrite)")
    else:
        print()
        print("No files written outside bob-the-builder/ (Bob lives in one repo).")
        print("Optional parent shortcuts: bob install --launchers")
        print()
        print("Host repos: copy deploy/tdd template (~2 min):")
        print(f"  {product / 'templates' / 'host-deploy-tdd' / 'README.md'}")

    print()
    print(f"  BOB_HOME={product / 'assets'}")
    print(f"  BOB_LOCAL={product / LOCAL_SUB}")

    from git_hooks import install_git_hooks

    _ok, hook_msg = install_git_hooks(force=force)
    print()
    print(hook_msg)
    print("  After each git commit, Bob auto-refreshes docs/NEXT.md (separate [bob] commit).")
    print()
    print("Bob: Install recommended Cursor plugins for plan/review/memory workflows.")
    print("     Run: bob plugins   (see docs/CURSOR_PLUGINS.md)")
    return 0
