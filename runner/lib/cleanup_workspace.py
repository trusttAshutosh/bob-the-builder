"""Merge old workspace folders into bob-the-builder/ and remove stale names."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from bob_home import (
    ASSETS_SUB,
    LOCAL_SUB,
    PRODUCT_DIR,
    STALE_WORKSPACE_DIRS,
    _copy_tree,
    bob_assets_root,
    bob_local_root,
    bob_product_root,
    stale_workspace_dirs,
)
from host_repo import workspace_root
from workspace_env import WORKSPACE_ENV


def _merge_assets_from(src: Path, dest: Path) -> list[str]:
    actions: list[str] = []
    asset_names = ("api-catalog", "stub-registry", "assertion-catalog", "platform-graph", "assets")
    for name in asset_names:
        if name == "assets" and (src / "assets").is_dir():
            _copy_tree(src / "assets", dest)
            actions.append(f"merged {src / 'assets'} -> {dest}")
            continue
        sub = src / name
        if sub.is_dir():
            _copy_tree(sub, dest / name if name != "assets" else dest)
            actions.append(f"merged {sub} -> {dest}")
    return actions


def _merge_local_from(src: Path, dest: Path) -> list[str]:
    actions: list[str] = []
    for name in ("agent", ".runtime-wiremock", "user.env"):
        sub = src / name
        if sub.is_file() and not (dest / name).exists():
            shutil.copy2(sub, dest / name)
            actions.append(f"copied {sub}")
        elif sub.is_dir():
            _copy_tree(sub, dest / name)
            actions.append(f"merged {sub}")
    if src.name in STALE_WORKSPACE_DIRS and (src / "assets").is_dir():
        pass  # assets handled separately
    elif src.name == ".bob-the-builder":
        _merge_assets_from(src, bob_assets_root())
        for name in ("agent", ".runtime-wiremock", "user.env"):
            sub = src / name
            if sub.exists():
                if sub.is_dir():
                    _copy_tree(sub, dest / name)
                elif not (dest / name).exists():
                    shutil.copy2(sub, dest / name)
                actions.append(f"merged local bits from {src}")
    return actions


def _merge_flat_runner(old: Path, product: Path) -> list[str]:
    """Old install copied runner files into novopay-bob/ root."""
    actions: list[str] = []
    runner_dest = product / "runner"
    if (old / "novopay-tdd.py").is_file() or (old / "bob-the-builder.py").is_file():
        if not runner_dest.is_dir():
            runner_dest.mkdir(parents=True)
        for item in old.iterdir():
            if item.name in STALE_WORKSPACE_DIRS or item.name in ("assets", "skills", "local", "runner"):
                continue
            target = runner_dest / item.name
            if item.is_dir() and not target.exists():
                shutil.copytree(item, target)
                actions.append(f"runner tree {item.name}")
            elif item.is_file() and not target.exists():
                shutil.copy2(item, target)
                actions.append(f"runner file {item.name}")
    return actions


def cleanup_workspace(*, apply: bool = False) -> int:
    ws = workspace_root()
    if not ws:
        print(f"{WORKSPACE_ENV} not set. Run: bob setup", file=sys.stderr)
        return 1

    ws = ws.resolve()
    product = bob_product_root()
    assets = bob_assets_root()
    local = bob_local_root()
    stale = stale_workspace_dirs(ws)

    print(f"Workspace: {ws}")
    print(f"Canonical product folder: {product}")
    print(f"  {ASSETS_SUB}/ -> {assets}")
    print(f"  {LOCAL_SUB}/  -> {local}")
    print()

    if not stale:
        print("No stale folders (.bob-the-builder, bob-the-builder-local, novopay-bob, novopay-bob-local).")
        return 0

    print("Stale folders found:")
    for s in stale:
        print(f"  - {s}")
    print()

    all_actions: list[str] = []
    for s in stale:
        all_actions.extend(_merge_assets_from(s, assets))
        if s.name == "novopay-bob":
            all_actions.extend(_merge_flat_runner(s, product))
        if (s / "assets").is_dir():
            all_actions.extend(_merge_assets_from(s / "assets", assets))
        all_actions.extend(_merge_local_from(s, local))

    if all_actions:
        print("Merge plan:")
        for a in all_actions:
            print(f"  {a}")
    else:
        print("Nothing to merge (targets already populated).")

    if not apply:
        print()
        print("Dry run. Re-run with: bob cleanup-workspace --apply")
        print("Then removes stale folders listed above.")
        return 0

    for s in stale:
        if s.exists():
            shutil.rmtree(s)
            print(f"Removed: {s}")

    print()
    print("Done. Use only:")
    print(f"  {product}/")
    print("    runner/  assets/  skills/  local/  (local is machine-only)")
    return 0
