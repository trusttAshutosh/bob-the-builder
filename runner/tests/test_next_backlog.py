"""Tests for bob next and --edit."""
from __future__ import annotations

import subprocess
from pathlib import Path

from builder_cli import _next_doc_path, _open_path_in_editor, _resolve_editor_argv, cmd_next


def test_resolve_editor_prefers_visual(monkeypatch) -> None:
    monkeypatch.setenv("VISUAL", "code --wait")
    monkeypatch.setenv("EDITOR", "nano")
    assert _resolve_editor_argv() == ["code", "--wait"]


def test_cmd_next_prints_backlog(tmp_path: Path, monkeypatch, capsys) -> None:
    doc = tmp_path / "docs" / "NEXT.md"
    doc.parent.mkdir()
    doc.write_text("## Now\n\n- [ ] item\n", encoding="utf-8")
    monkeypatch.setattr("builder_cli._next_doc_path", lambda: doc)

    rc = cmd_next([])
    out = capsys.readouterr().out

    assert rc == 0
    assert "Improvement backlog" in out
    assert "item" in out


def test_cmd_next_edit_invokes_editor(tmp_path: Path, monkeypatch) -> None:
    doc = tmp_path / "docs" / "NEXT.md"
    doc.parent.mkdir()
    doc.write_text("# backlog\n", encoding="utf-8")
    monkeypatch.setattr("builder_cli._next_doc_path", lambda: doc)
    monkeypatch.setenv("EDITOR", "echo-editor")

    captured: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        captured.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("builder_cli.subprocess.run", fake_run)

    rc = cmd_next(["--edit"])

    assert rc == 0
    assert captured
    assert captured[0][0] == "echo-editor"
    assert captured[0][-1] == str(doc)


def test_open_path_in_editor_missing_binary(monkeypatch) -> None:
    monkeypatch.setenv("EDITOR", "definitely-not-an-editor-xyz")
    rc = _open_path_in_editor(Path("docs/NEXT.md"))
    assert rc == 1
