"""Resolve active host service repo vs runner install."""
from __future__ import annotations

import os
from pathlib import Path

from workspace_env import WORKSPACE_ENV, workspace_env_value


def workspace_root() -> Path | None:
    raw = workspace_env_value()
    if not raw:
        return None
    p = Path(raw).expanduser()
    return p.resolve() if p.is_dir() else None


def _is_git_repo(path: Path) -> bool:
    return (path / ".git").is_dir() or (path / ".git").is_file()


def _repo_under_workspace(repo: Path, workspace: Path) -> bool:
    try:
        repo.resolve().relative_to(workspace.resolve())
        return True
    except ValueError:
        return False


def infer_workspace_root() -> Path | None:
    """Parent folder with 2+ git clones (any names)."""
    for start in (Path.cwd().resolve(), runner_bootstrap_repo().resolve().parent):
        if not start.is_dir():
            continue
        git_repos = [p for p in start.iterdir() if p.is_dir() and _is_git_repo(p)]
        if len(git_repos) >= 2:
            return start.resolve()
    return None


def runner_bootstrap_repo() -> Path:
    """bob-the-builder product root (parent of runner/)."""
    return Path(__file__).resolve().parents[2]


def host_repo_root() -> Path:
    explicit = os.environ.get("BOB_HOST_REPO", "").strip()
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if p.is_dir():
            return p

    ws = workspace_root()
    if ws:
        cur = Path.cwd().resolve()
        while True:
            if _is_git_repo(cur) and cur != ws and _repo_under_workspace(cur, ws):
                return cur
            if cur == ws or cur.parent == cur:
                break
            cur = cur.parent

    last = os.environ.get("BOB_LAST_HOST_REPO", "").strip()
    if last:
        p = Path(last).expanduser().resolve()
        if p.is_dir():
            return p

    return runner_bootstrap_repo().resolve()


def host_repo_name() -> str:
    return host_repo_root().name


def host_repo_hint() -> str:
    ws = workspace_root()
    if ws:
        return f"host={host_repo_root()} (cwd under {ws}; override BOB_HOST_REPO)"
    return f"host={host_repo_root()} (run: bob setup — set {WORKSPACE_ENV})"
