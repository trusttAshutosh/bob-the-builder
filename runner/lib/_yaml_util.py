from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


def load(path: Path) -> dict:
    if not yaml:
        raise RuntimeError("PyYAML required: pip install -r runner/requirements.txt")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def dump(path: Path, data: dict) -> None:
    if not yaml:
        raise RuntimeError("PyYAML required")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def runner_root() -> Path:
    """Directory containing bob-the-builder.py, lib/, _seed/."""
    return Path(__file__).resolve().parents[1]


def tdd_root() -> Path:
    return runner_root()


def host_repo_root() -> Path:
    from host_repo import host_repo_root as _resolve

    return _resolve()


def repo_root() -> Path:
    """Active service repo (tickets, orchestration, deploy/tdd). Not the runner install."""
    return host_repo_root()
