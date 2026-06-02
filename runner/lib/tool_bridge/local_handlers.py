"""Local tool implementations (default backend — always available)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from tool_bridge.types import ToolResult


def _repo_root() -> Path:
    from host_repo import runner_bootstrap_repo

    return runner_bootstrap_repo()


def git_branch(*, cwd: str | None = None, **_kwargs: Any) -> ToolResult:
    root = Path(cwd) if cwd else _repo_root()
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        branch = (r.stdout or "").strip()
        return ToolResult(
            ok=r.returncode == 0,
            data=branch or "unknown",
            stdout=r.stdout or "",
            stderr=r.stderr or "",
            exit_code=r.returncode,
            backend="local",
            tool_id="git.branch",
        )
    except Exception as exc:
        return ToolResult(ok=False, data="unknown", error=str(exc), backend="local", tool_id="git.branch")


def git_rev_parse(*, cwd: str | None = None, ref: str = "HEAD", **_kwargs: Any) -> ToolResult:
    root = Path(cwd) if cwd else _repo_root()
    args = ["git", "rev-parse"]
    if ref == "--short" or ref.endswith(" --short"):
        parts = ref.split()
        args.extend(parts)
    else:
        args.append(ref)
    try:
        r = subprocess.run(args, cwd=root, capture_output=True, text=True, timeout=15)
        value = (r.stdout or "").strip()
        return ToolResult(
            ok=r.returncode == 0,
            data=value,
            stdout=r.stdout or "",
            stderr=r.stderr or "",
            exit_code=r.returncode,
            backend="local",
            tool_id="git.rev_parse",
        )
    except Exception as exc:
        return ToolResult(ok=False, error=str(exc), backend="local", tool_id="git.rev_parse")


def mysql_query(*, sql: str, schema: str | None = None, **_kwargs: Any) -> ToolResult:
    from mysql_runner import _mysql_query_local

    rc, out = _mysql_query_local(sql, schema=schema)
    return ToolResult(
        ok=rc == 0,
        data=out,
        stdout=out,
        exit_code=rc,
        backend="local",
        tool_id="mysql.query",
        error="" if rc == 0 else out[:500],
    )


def subprocess_run(
    *,
    argv: list[str] | None = None,
    cwd: str | None = None,
    timeout: float = 60,
    **_kwargs: Any,
) -> ToolResult:
    if not argv:
        return ToolResult(ok=False, error="argv required", backend="local", tool_id="subprocess.run")
    work = Path(cwd) if cwd else None
    try:
        r = subprocess.run(
            argv,
            cwd=work,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
        return ToolResult(
            ok=r.returncode == 0,
            data=(r.stdout or "") + (r.stderr or ""),
            stdout=r.stdout or "",
            stderr=r.stderr or "",
            exit_code=r.returncode,
            backend="local",
            tool_id="subprocess.run",
        )
    except Exception as exc:
        return ToolResult(ok=False, error=str(exc), backend="local", tool_id="subprocess.run")


HANDLERS: dict[str, Any] = {
    "git_branch": git_branch,
    "git_rev_parse": git_rev_parse,
    "mysql_query": mysql_query,
    "subprocess_run": subprocess_run,
}


def run_local_handler(handler_name: str, arguments: dict[str, Any]) -> ToolResult:
    fn = HANDLERS.get(handler_name)
    if fn is None:
        return ToolResult(ok=False, error=f"Unknown local handler: {handler_name}", backend="local")
    return fn(**arguments)
