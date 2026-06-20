"""Tests for bob onboard template planning and deploy helpers."""
from __future__ import annotations

import json
from pathlib import Path

from cursor_hook import bob_hook_runner_command
from onboard import (
    HOST_CC_FOLDER,
    WORKSPACE_CURSOR_BUNDLE,
    ensure_skills_junction,
    merge_hooks_json,
    plan_writes,
    render_workspace_json,
    substitute,
    sync_bundle_tree,
    template_root,
)


def test_substitute_workspace_placeholders() -> None:
    ws = Path("C:/Users/dev/novopay")
    text = "root={{WORKSPACE_ROOT}} name={{WORKSPACE_NAME}}"
    out = substitute(text, ws)
    assert "C:\\Users\\dev\\novopay" in out or "C:/Users/dev/novopay" in out
    assert "name=novopay" in out


def test_render_workspace_json_only_existing_folders(tmp_path: Path) -> None:
    (tmp_path / "bob-the-builder").mkdir()
    (tmp_path / "novopay-platform-lib").mkdir()
    doc = json.loads(render_workspace_json(tmp_path))
    paths = {f["path"] for f in doc["folders"]}
    assert "." in paths
    assert "bob-the-builder" in paths
    assert "novopay-platform-lib" in paths
    assert "novopay-platform-actor" not in paths


def test_merge_hooks_json_appends_stop_hook(tmp_path: Path) -> None:
    dest = tmp_path / "hooks.json"
    dest.write_text(
        json.dumps({"version": 1, "hooks": {"stop": [{"command": "./hooks/other.sh"}]}}),
        encoding="utf-8",
    )
    template = json.dumps(
        {
            "version": 1,
            "hooks": {
                "stop": [{"command": bob_hook_runner_command("stop"), "loop_limit": 1}]
            },
        }
    )
    merged = json.loads(merge_hooks_json(dest, template))
    cmds = [e["command"] for e in merged["hooks"]["stop"]]
    assert "./hooks/other.sh" in cmds
    assert bob_hook_runner_command("stop") in cmds


def test_merge_hooks_json_idempotent(tmp_path: Path) -> None:
    dest = tmp_path / "hooks.json"
    template = json.dumps(
        {
            "version": 1,
            "hooks": {
                "stop": [{"command": bob_hook_runner_command("stop"), "loop_limit": 1}]
            },
        }
    )
    first = merge_hooks_json(dest, template)
    dest.write_text(first, encoding="utf-8")
    second = merge_hooks_json(dest, template)
    assert json.loads(first) == json.loads(second)


def test_plan_writes_skips_existing_rule(monkeypatch, tmp_path: Path) -> None:
    cursor = tmp_path / ".cursor"
    rules = cursor / "rules"
    rules.mkdir(parents=True)
    (rules / "novopay-orchestrator.mdc").write_text("existing", encoding="utf-8")
    monkeypatch.setattr("onboard.cursor_home", lambda: cursor)

    plans = plan_writes(tmp_path, force=False)
    rule_plan = next(p for p in plans if "orchestrator rule" in p.label.lower())
    assert rule_plan.action == "skip"


def test_template_bundle_exists() -> None:
    root = template_root()
    assert (root / "cursor" / "novopay-orchestrator.mdc").is_file()
    assert (root / "novopay" / "AGENTS.md.stub").is_file()
    assert (root / WORKSPACE_CURSOR_BUNDLE / "skills" / "ticket-breakdown-planning" / "SKILL.md").is_file()
    assert (root / WORKSPACE_CURSOR_BUNDLE / "rules" / "development-guidelines.mdc").is_file()
    assert (root / "host-cc" / ".cursor" / "rules" / "cc-backend-tests-required.mdc").is_file()


def test_sync_bundle_tree_writes_and_skips(tmp_path: Path, monkeypatch) -> None:
    bundle = tmp_path / "bundle" / WORKSPACE_CURSOR_BUNDLE
    bundle.mkdir(parents=True)
    (bundle / "skills" / "demo").mkdir(parents=True)
    (bundle / "skills" / "demo" / "SKILL.md").write_text("demo", encoding="utf-8")
    monkeypatch.setattr(
        "onboard.template_root",
        lambda: tmp_path / "bundle",
    )
    dest = tmp_path / "ws" / ".cursor"
    rows = sync_bundle_tree(WORKSPACE_CURSOR_BUNDLE, dest, tmp_path / "ws", force=False)
    assert any(action == "write" for _, action in rows)
    assert (dest / "skills" / "demo" / "SKILL.md").read_text(encoding="utf-8") == "demo"
    rows2 = sync_bundle_tree(WORKSPACE_CURSOR_BUNDLE, dest, tmp_path / "ws", force=False)
    assert all(action == "skip" for _, action in rows2)


def test_ensure_skills_junction_creates_link(tmp_path: Path) -> None:
    target = tmp_path / "canonical" / "skills"
    target.mkdir(parents=True)
    link = tmp_path / "host" / ".cursor" / "skills"
    action = ensure_skills_junction(link, target, force=False)
    assert action == "junction"
    assert link.exists()
    assert link.resolve() == target.resolve()
    action2 = ensure_skills_junction(link, target, force=False)
    assert action2 == "skip (junction ok)"


def test_plan_writes_includes_cursor_kit(tmp_path: Path, monkeypatch) -> None:
    cursor = tmp_path / ".cursor"
    cursor.mkdir()
    monkeypatch.setattr("onboard.cursor_home", lambda: cursor)
    (tmp_path / HOST_CC_FOLDER).mkdir()
    plans = plan_writes(tmp_path, force=False)
    labels = [p.label for p in plans]
    assert any("Cursor kit" in label for label in labels)
    assert any("junction" in label.lower() for label in labels)


def test_plugin_notice_lists_recommended_plugins() -> None:
    from cursor_plugins import RECOMMENDED_PLUGINS, format_plugin_notice, format_plugin_status_summary

    text = format_plugin_notice(prominent=True)
    for plug in RECOMMENDED_PLUGINS:
        assert plug.name in text
    assert "ticket-breakdown-planning" in format_plugin_notice()
    status_lines, missing = format_plugin_status_summary()
    assert status_lines
    assert any("Superpowers" in line for line in status_lines)
