"""Tests for bob memory-budget."""
from __future__ import annotations

import json
from pathlib import Path

import json
from pathlib import Path

from memory_budget import (
    build_memory_budget_report,
    default_habits,
    format_agent_context_section,
    render_memory_budget_md,
    run_memory_budget_hook_session,
    write_workspace_status,
)


def test_default_habits_non_empty() -> None:
    assert len(default_habits()) >= 4


def test_format_agent_context_section() -> None:
    lines = format_agent_context_section()
    text = "\n".join(lines)
    assert "Memory budget" in text
    assert "60%" in text


def test_build_memory_budget_report() -> None:
    report = build_memory_budget_report()
    assert report.generated_at
    assert report.status in ("ok", "warn", "critical")
    assert report.habits


def test_render_memory_budget_md() -> None:
    report = build_memory_budget_report()
    md = render_memory_budget_md(report)
    assert "# Working memory budget" in md
    assert "Four buckets" in md


def test_write_workspace_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("memory_budget.infer_workspace_root", lambda: tmp_path)
    report = build_memory_budget_report()
    path = write_workspace_status(report, tmp_path)
    assert path is not None and path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] in ("ok", "warn", "critical")


def test_hook_session_writes_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("memory_budget.infer_workspace_root", lambda: tmp_path)
    assert run_memory_budget_hook_session() == 0
    assert (tmp_path / ".cursor" / "memory-budget-status.json").is_file()
