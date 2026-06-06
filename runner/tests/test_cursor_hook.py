"""Tests for Cursor hook runner helpers."""
from __future__ import annotations

import json

from cursor_hook import LEGACY_HOOK_COMMANDS, merge_hooks_json, normalize_hooks_payload


def test_normalize_hooks_payload_replaces_legacy(tmp_path) -> None:
    data = {
        "version": 1,
        "hooks": {
            "sessionStart": [{"command": "./hooks/session-chat-hygiene.sh"}],
            "stop": [
                {"command": "./hooks/orchestrator-hygiene-stop.sh", "loop_limit": 1},
                {"command": "./hooks/other.sh"},
            ],
        },
    }
    out = normalize_hooks_payload(data)
    session_cmds = [e["command"] for e in out["hooks"]["sessionStart"]]
    stop_cmds = [e["command"] for e in out["hooks"]["stop"]]
    assert "./hooks/bob-hook-runner.sh session" in session_cmds
    assert "./hooks/bob-hook-runner.sh stop" in stop_cmds
    assert "./hooks/other.sh" in stop_cmds
    for legacy in LEGACY_HOOK_COMMANDS:
        assert legacy not in session_cmds
        assert legacy not in stop_cmds


def test_merge_hooks_json_upgrades_legacy(tmp_path) -> None:
    dest = tmp_path / "hooks.json"
    dest.write_text(
        json.dumps(
            {
                "version": 1,
                "hooks": {
                    "stop": [{"command": "./hooks/orchestrator-hygiene-stop.sh", "loop_limit": 1}]
                },
            }
        ),
        encoding="utf-8",
    )
    template = json.dumps(
        {
            "version": 1,
            "hooks": {
                "sessionStart": [{"command": "./hooks/bob-hook-runner.sh session"}],
                "stop": [{"command": "./hooks/bob-hook-runner.sh stop", "loop_limit": 1}],
            },
        }
    )
    merged = json.loads(merge_hooks_json(dest, template))
    stop_cmds = [e["command"] for e in merged["hooks"]["stop"]]
    assert "./hooks/orchestrator-hygiene-stop.sh" not in stop_cmds
    assert "./hooks/bob-hook-runner.sh stop" in stop_cmds
