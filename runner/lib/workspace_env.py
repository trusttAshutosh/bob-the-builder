"""Workspace root env (set via bob setup — never hardcoded in source)."""
from __future__ import annotations

import os

WORKSPACE_ENV = "BUILDER_WORKSPACE_ROOT"


def workspace_env_value() -> str:
    return os.environ.get(WORKSPACE_ENV, "").strip()


def set_workspace_env(path: str) -> None:
    os.environ[WORKSPACE_ENV] = path
