"""Tests for bob meta-review helpers."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from meta_review import (
    _boot_failures,
    _normalize_rule_text,
    MetaReviewReport,
    TicketStat,
    build_suggestions,
    meta_review_hook_due,
    parse_next_backlog,
    run_meta_review_hook,
)


def test_boot_failures_detects_health_steps() -> None:
    steps = [
        {"id": "health_cc", "label": "Health credit_card_management", "status": "fail"},
        {"id": "context", "label": "Assemble CONTEXT_PACK", "status": "pass"},
    ]
    assert _boot_failures(steps) == ["Health credit_card_management"]


def test_parse_next_open_items(tmp_path: Path) -> None:
    nxt = tmp_path / "NEXT.md"
    nxt.write_text(
        "## Now (P0)\n\n- [ ] **Publish product repo** — details\n\n## Next (P1)\n\n- [x] **Done item**\n- [ ] **meta item**\n",
        encoding="utf-8",
    )
    open_items, sections = parse_next_backlog(nxt)
    assert ("Now", "Publish product repo") in open_items
    assert ("Next", "meta item") in open_items
    assert sections["Now"] == 1
    assert sections["Next"] == 1


def test_normalize_rule_strips_workspace_path() -> None:
    ws = Path("C:/Users/dev/Desktop/novopay")
    text = "root C:/Users/dev/Desktop/novopay and Desktop/novopay/AGENTS.md"
    out = _normalize_rule_text(text, ws)
    assert "{{WORKSPACE_ROOT}}" in out
    assert "C:/Users/dev/Desktop/novopay" not in out


def test_meta_review_hook_due_when_never_run() -> None:
    assert meta_review_hook_due({}) is True


def test_meta_review_hook_not_due_after_recent_run() -> None:
    import time

    state = {"last_run_epoch": time.time()}
    assert meta_review_hook_due(state, interval_days=30) is False


def test_meta_review_hook_stop_skips_invalid_payload() -> None:
    import io
    import os
    import sys

    buf = io.StringIO()
    old_stdout = sys.stdout
    old_env = os.environ.get("HOOK_STOP_JSON")
    try:
        os.environ["HOOK_STOP_JSON"] = '{"status":"aborted"}'
        sys.stdout = buf
        assert run_meta_review_hook() == 0
        assert buf.getvalue().strip() == "{}"
    finally:
        sys.stdout = old_stdout
        if old_env is None:
            os.environ.pop("HOOK_STOP_JSON", None)
        else:
            os.environ["HOOK_STOP_JSON"] = old_env


def test_build_suggestions_for_low_pass_rate() -> None:
    report = MetaReviewReport(
        generated_at="2026-06-06",
        workspace="C:/novopay",
        tickets=[
            TicketStat("t1", "host", "PASS", "", ""),
            TicketStat("t2", "host", "FAIL", "", "", boot_failures=["Health cc"]),
        ],
        boot_failure_counts=Counter({"Health cc": 1}),
        rule_drift="differs",
        hooks_ok=False,
        next_open=[("Now", "item")],
        next_sections={"Now": 1},
        plugin_signals={"Superpowers": "not detected in local plugin cache"},
    )
    suggestions = build_suggestions(report)
    assert any("pass rate" in s.lower() for s in suggestions)
    assert any("boot" in s.lower() for s in suggestions)
    assert any("rule drift" in s.lower() for s in suggestions)
