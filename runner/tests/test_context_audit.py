"""Tests for bob context-audit helpers."""
from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from context_audit import (
    build_context_audit,
    build_context_suggestions,
    context_bucket,
    normalize_header,
    render_context_audit_summary_md,
)


def test_context_bucket_thresholds() -> None:
    assert context_bucket(85) == "80-100% (critical)"
    assert context_bucket(65) == "60-79% (high)"
    assert context_bucket(45) == "40-59% (medium)"
    assert context_bucket(25) == "20-39% (low)"
    assert context_bucket(10) == "0-19% (minimal)"


def test_normalize_header_prefers_name() -> None:
    row = normalize_header(
        {
            "composerId": "abc",
            "name": "My chat",
            "subtitle": "ignored",
            "contextUsagePercent": 72.5,
            "isArchived": False,
        }
    )
    assert row["name"] == "My chat"
    assert row["pct"] == 72.5


def _seed_state_db(path: Path, composers: list[dict]) -> None:
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
        payload = json.dumps({"allComposers": composers})
        db.execute(
            "INSERT INTO ItemTable (key, value) VALUES (?, ?)",
            ("composer.composerHeaders", payload),
        )
        db.commit()


SCRATCH = Path(__file__).resolve().parent / "_scratch_context_audit"


def test_build_context_audit_from_fixture() -> None:
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH, ignore_errors=True)
    SCRATCH.mkdir(parents=True)
    db_path = SCRATCH / "state.vscdb"
    _seed_state_db(
        db_path,
        [
            {
                "composerId": "hot-chat",
                "name": "Long thread",
                "contextUsagePercent": 82.0,
                "isArchived": False,
                "isDraft": False,
            },
            {
                "composerId": "old-chat",
                "name": "Archived",
                "contextUsagePercent": 40.0,
                "isArchived": True,
                "isDraft": False,
            },
            {
                "composerId": "draft-chat",
                "isDraft": True,
                "contextUsagePercent": 99.0,
            },
        ],
    )
    transcript_root = SCRATCH / "projects" / "demo"
    transcript_dir = transcript_root / "agent-transcripts" / "hot-chat"
    transcript_dir.mkdir(parents=True)
    (transcript_dir / "hot-chat.jsonl").write_text(
        '{"role":"user","message":{"content":[{"type":"text","text":"hi"}]}}\n',
        encoding="utf-8",
    )

    report = build_context_audit(db_path=db_path, transcript_root=transcript_root)
    assert report.error is None
    assert report.total_chats == 2
    assert report.active_high_count == 1
    assert report.top_chats[0].name == "Long thread"
    assert report.matched_headers == 1

    suggestions = build_context_suggestions(report)
    assert any("active chat" in s.lower() for s in suggestions)

    summary = render_context_audit_summary_md(report)
    assert any("Cursor context usage" in line for line in summary)
    assert any("active 1" in line for line in summary)


def test_build_context_audit_missing_db(tmp_path: Path) -> None:
    report = build_context_audit(db_path=tmp_path / "missing.vscdb")
    assert report.error is not None
    assert "not found" in report.error.lower()
