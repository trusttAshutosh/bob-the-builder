#!/usr/bin/env python3
"""postToolUse hook: remind the agent to add/update CC backend tests after edits in scope."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print("{}")
        return 0

    ti = payload.get("tool_input") or {}
    if isinstance(ti, str):
        try:
            ti = json.loads(ti)
        except json.JSONDecodeError:
            ti = {}
    if not isinstance(ti, dict):
        ti = {}

    path = (ti.get("path") or ti.get("file_path") or "").replace("\\", "/")
    if not path:
        print("{}")
        return 0

    in_cc = "/in/novopay/creditcard/" in path or "src/main/java/in/novopay/creditcard/" in path
    in_orch = "/deploy/application/orchestration/" in path or "deploy/application/orchestration/" in path
    if not in_cc and not in_orch:
        print("{}")
        return 0

    if "/src/test/" in path:
        print("{}")
        return 0

    repo_root = Path(__file__).resolve().parent.parent.parent
    state_dir = repo_root / ".cursor" / "hooks" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    throttle = state_dir / "posttool-nudge-ts"
    now = int(time.time())
    if throttle.is_file():
        try:
            last = int(throttle.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            last = 0
        if now - last < 45:
            print("{}")
            return 0
    throttle.write_text(str(now), encoding="utf-8")

    msg = (
        "Project policy: you edited credit-card scope (in/novopay/creditcard or CC orchestration XML). "
        "Generate tests for changed files/diff scope only (plus direct impacted collaborators), "
        "not full-repo scan, unless explicitly requested. Follow .cursor/rules/cc-backend-tests-required.mdc "
        "and .cursor/skills/cc-backend-test-generation/SKILL.md, then run targeted ./gradlew test."
    )
    print(json.dumps({"additional_context": msg}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
