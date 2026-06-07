"""Tests for git hook install."""
from __future__ import annotations

import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from git_hooks import install_git_hooks  # noqa: E402


def test_install_git_hooks_returns_pair(tmp_path, monkeypatch) -> None:
    root = tmp_path / "bob-the-builder"
    hooks = root / "runner" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "pre-commit").write_text("# Bob — pre-commit\n", encoding="utf-8")
    (root / ".git" / "hooks").mkdir(parents=True)

    monkeypatch.setattr("git_hooks.runner_bootstrap_repo", lambda: root)

    ok, msg = install_git_hooks(force=True)
    assert ok is True
    assert isinstance(msg, str)
