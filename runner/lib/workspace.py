"""Resolve multi-repo workspace root and service paths."""
from __future__ import annotations

import os
from pathlib import Path

from _yaml_util import host_repo_root, load, runner_root
from bob_home import bob_assets_root


def workspace_services_path() -> Path:
    """Host repo map first; then Bob assets; then runner package template."""
    host = host_repo_root() / "deploy/tdd/workspace-services.yaml"
    if host.is_file():
        return host
    central = bob_assets_root() / "workspace-services.yaml"
    if central.is_file():
        return central
    bundled = runner_root() / "deploy/tdd/workspace-services.yaml"
    return bundled if bundled.is_file() else host


def workspace_root() -> Path | None:
    from host_repo import workspace_root as _ws

    return _ws()


def service_repo_path(service_key: str) -> Path | None:
    root = workspace_root()
    if not root:
        return None
    data = load(workspace_services_path())
    svc = (data.get("services") or {}).get(service_key) or {}
    repo_dir = svc.get("repo_dir")
    if not repo_dir:
        return None
    p = root / repo_dir
    return p if p.is_dir() else None


def list_service_hints() -> list[str]:
    """Human-readable lines for run decision trace / setup."""
    root = workspace_root()
    if not root:
        from workspace_env import WORKSPACE_ENV

        return [f"{WORKSPACE_ENV}: (not set — run: bob setup)"]
    data = load(workspace_services_path())
    lines = [f"workspace: {root}"]
    for key, svc in (data.get("services") or {}).items():
        repo_dir = svc.get("repo_dir", "")
        p = root / repo_dir
        exists = "ok" if p.is_dir() else "missing"
        cfg = ", ".join(svc.get("config_files") or [])[:80]
        lines.append(f"  {key}: {repo_dir} [{exists}] props: {cfg}")
    return lines


def properties_files_for_ticket(spec: dict) -> list[str]:
    """Paths (relative to workspace) the implementer may need to edit."""
    root = workspace_root()
    if not root:
        return []
    data = load(workspace_services_path())
    repos = (spec.get("impacted") or {}).get("repos") or []
    out: list[str] = []
    for key, svc in (data.get("services") or {}).items():
        repo_dir = svc.get("repo_dir", "")
        if repos and repo_dir not in repos and key not in repos:
            continue
        for rel in svc.get("config_files") or []:
            out.append(str(root / repo_dir / rel))
    return out
