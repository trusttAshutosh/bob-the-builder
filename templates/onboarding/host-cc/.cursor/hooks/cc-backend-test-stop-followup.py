#!/usr/bin/env python3
"""stop hook: one optional follow-up when the working tree still has production CC / orchestration edits."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _norm(path: str) -> str:
    return path.replace("\\", "/")


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print("{}")
        return 0

    if payload.get("status") != "completed":
        print("{}")
        return 0
    try:
        loop = int(payload.get("loop_count", 0))
    except (TypeError, ValueError):
        print("{}")
        return 0
    if loop != 0:
        print("{}")
        return 0

    repo_root = Path(__file__).resolve().parent.parent.parent
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "-u"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=repo_root,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("{}")
        return 0

    if result.returncode != 0:
        print("{}")
        return 0

    main_touched = False
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[0].strip()
        normalized = _norm(path)
        if (
            "src/main/java/in/novopay/creditcard/" in normalized
            or "/src/main/java/in/novopay/creditcard/" in normalized
        ):
            main_touched = True
        if "deploy/application/orchestration/" in normalized and normalized.endswith(".xml"):
            main_touched = True

    if not main_touched:
        print("{}")
        return 0

    msg = (
        "Follow-up (repo policy): git status still shows production or orchestration changes under "
        "credit-card scope. If tests are not already done in this session, apply diff-only scope "
        "(changed files + direct impacted collaborators), not repo-wide scan unless explicitly requested. "
        "Then apply .cursor/skills/cc-backend-test-generation/SKILL.md and "
        ".cursor/rules/cc-backend-tests-required.mdc, then run targeted ./gradlew test."
    )
    print(json.dumps({"followup_message": msg}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
