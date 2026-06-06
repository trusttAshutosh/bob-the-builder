#!/usr/bin/env bash
# stop hook: one optional follow-up when the working tree still has production CC / orchestration edits.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

export HOOK_STOP_JSON="$(cat)"

python3 <<'PY'
import json
import os
import subprocess
import sys

raw = os.environ.get("HOOK_STOP_JSON", "")
try:
    d = json.loads(raw)
except json.JSONDecodeError:
    print("{}")
    raise SystemExit(0)

if d.get("status") != "completed":
    print("{}")
    raise SystemExit(0)
try:
    loop = int(d.get("loop_count", 0))
except (TypeError, ValueError):
    print("{}")
    raise SystemExit(0)
if loop != 0:
    print("{}")
    raise SystemExit(0)

try:
    r = subprocess.run(
        ["git", "status", "--porcelain", "-u"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=".",
    )
except (FileNotFoundError, subprocess.TimeoutExpired):
    print("{}")
    raise SystemExit(0)

if r.returncode != 0:
    print("{}")
    raise SystemExit(0)


def norm(p: str) -> str:
    return p.replace(chr(92), "/")


main_touched = False
for line in r.stdout.splitlines():
    if not line.strip():
        continue
    path = line[3:].strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[0].strip()
    n = norm(path)
    if (
        "src/main/java/in/novopay/creditcard/" in n
        or "/src/main/java/in/novopay/creditcard/" in n
    ):
        main_touched = True
    if "deploy/application/orchestration/" in n and n.endswith(".xml"):
        main_touched = True

if not main_touched:
    print("{}")
    raise SystemExit(0)

msg = (
    "Follow-up (repo policy): git status still shows production or orchestration changes under "
    "credit-card scope. If tests are not already done in this session, apply diff-only scope "
    "(changed files + direct impacted collaborators), not repo-wide scan unless explicitly requested. Then apply "
    ".cursor/skills/cc-backend-test-generation/SKILL.md and .cursor/rules/cc-backend-tests-required.mdc, "
    "then run targeted ./gradlew test."
)
print(json.dumps({"followup_message": msg}))
PY
