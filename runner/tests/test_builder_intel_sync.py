"""Tests for builder_intel_sync."""
from __future__ import annotations

from pathlib import Path

from builder_intel_sync import (
    AUTO_END,
    AUTO_START,
    render_auto_section,
    sync_builder_intel,
    verify_builder_intel_sync,
)


def test_render_auto_section_lists_features(tmp_path, monkeypatch) -> None:
    root = tmp_path / "bob"
    (root / "docs").mkdir(parents=True)
    (root / "runner" / "lib").mkdir(parents=True)
    (root / "docs" / "product-features.yaml").write_text(
        "features:\n  - id: demo\n    name: Demo feature\n    commands: [demo-cmd]\n",
        encoding="utf-8",
    )
    (root / "docs" / "NEXT.md").write_text(
        "## Later (P2)\n\n- [ ] **Future thing** — someday\n",
        encoding="utf-8",
    )
    (root / "runner" / "lib" / "builder_cli.py").write_text(
        'handlers = {\n        "demo-cmd": cmd_demo,\n    }\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(root)
    body = render_auto_section(root)
    assert "Demo feature" in body
    assert "`demo`" in body
    assert "Future thing" in body
    assert "[Later]" in body


def test_sync_builder_intel_writes_markers(tmp_path, monkeypatch) -> None:
    root = tmp_path / "bob"
    (root / "docs").mkdir(parents=True)
    (root / "runner" / "lib").mkdir(parents=True)
    (root / "docs" / "internal").mkdir(parents=True)
    intel = root / "docs" / "internal" / "BUILDER_INTEL.md"
    intel.write_text(
        f"# Test\n\n{AUTO_START}\nplaceholder\n{AUTO_END}\n",
        encoding="utf-8",
    )
    (root / "docs" / "product-features.yaml").write_text(
        "features:\n  - id: x\n    name: X\n    commands: []\n",
        encoding="utf-8",
    )
    (root / "docs" / "NEXT.md").write_text("## Now\n\n_None open._\n", encoding="utf-8")
    (root / "runner" / "lib" / "builder_cli.py").write_text("handlers = {}\n", encoding="utf-8")

    changed, _ = sync_builder_intel(root, write=True)
    assert changed is True
    text = intel.read_text(encoding="utf-8")
    assert "| X | `x` |" in text
    ok, _ = verify_builder_intel_sync(root)
    assert ok is True
