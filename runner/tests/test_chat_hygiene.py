"""Tests for chat sidebar hygiene target selection."""
from __future__ import annotations

from chat_hygiene import (
    ArchiveTarget,
    ComposerEntry,
    is_protected,
    select_archive_targets,
)

NOW_MS = 1_700_000_000_000
DAY_MS = 86_400_000


def _entry(
    composer_id: str,
    *,
    last_ms: int = NOW_MS,
    pinned: bool = False,
    archived: bool = False,
    draft: bool = False,
    subagent: bool = False,
    name: str = "",
) -> ComposerEntry:
    return ComposerEntry(
        composer_id=composer_id,
        name=name or composer_id,
        is_archived=archived,
        is_pinned=pinned,
        is_draft=draft,
        is_subagent=subagent,
        last_activity_ms=last_ms,
        raw={},
    )


def test_select_archive_targets_stale_only() -> None:
    entries = [
        _entry("old", last_ms=NOW_MS - 8 * DAY_MS),
        _entry("recent", last_ms=NOW_MS - DAY_MS),
    ]
    targets = select_archive_targets(
        entries,
        stale_days=7,
        max_active=8,
        now_ms=NOW_MS,
    )
    ids = {t.composer_id for t in targets}
    assert ids == {"old"}
    assert targets[0].reason == "stale>7d"


def test_select_archive_targets_skips_pinned_and_current() -> None:
    entries = [
        _entry("pinned-old", last_ms=NOW_MS - 10 * DAY_MS, pinned=True),
        _entry("current-old", last_ms=NOW_MS - 10 * DAY_MS),
        _entry("other-old", last_ms=NOW_MS - 10 * DAY_MS),
    ]
    targets = select_archive_targets(
        entries,
        stale_days=7,
        max_active=8,
        now_ms=NOW_MS,
        current_composer_id="current-old",
    )
    ids = {t.composer_id for t in targets}
    assert "pinned-old" not in ids
    assert "current-old" not in ids
    assert ids == {"other-old"}


def test_select_archive_targets_cap_overflow() -> None:
    entries = [
        _entry(f"c{i}", last_ms=NOW_MS - i * 1_000)
        for i in range(10)
    ]
    targets = select_archive_targets(
        entries,
        stale_days=365,
        max_active=8,
        now_ms=NOW_MS,
    )
    assert len(targets) == 2
    ids = {t.composer_id for t in targets}
    assert ids == {"c8", "c9"}
    assert all(t.reason == "cap>8" for t in targets)


def test_select_archive_targets_skips_archived_and_drafts() -> None:
    entries = [
        _entry("archived", archived=True, last_ms=NOW_MS - 30 * DAY_MS),
        _entry("draft", draft=True, last_ms=NOW_MS - 30 * DAY_MS),
        _entry("live", last_ms=NOW_MS - DAY_MS),
    ]
    targets = select_archive_targets(entries, stale_days=7, max_active=8, now_ms=NOW_MS)
    assert targets == []


def test_is_protected_subagent() -> None:
    entry = _entry("sub", subagent=True)
    assert is_protected(entry, current_composer_id=None) is True
