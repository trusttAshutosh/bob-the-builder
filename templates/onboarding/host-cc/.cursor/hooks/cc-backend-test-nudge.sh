#!/usr/bin/env bash
# postToolUse hook: remind the agent to add/update CC backend tests after edits in scope.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STATE_DIR="$REPO_ROOT/.cursor/hooks/state"
mkdir -p "$STATE_DIR"

payload="$(cat)"

path="$(printf '%s' "$payload" | python3 -c "
import json, sys
try:
    d = json.loads(sys.stdin.read())
except json.JSONDecodeError:
    print('')
    raise SystemExit(0)
ti = d.get('tool_input') or {}
if isinstance(ti, str):
    try:
        ti = json.loads(ti)
    except json.JSONDecodeError:
        ti = {}
if not isinstance(ti, dict):
    ti = {}
p = ti.get('path') or ti.get('file_path') or ''
print(p.replace(chr(92), '/'))
" 2>/dev/null || true)"

if [[ -z "$path" ]]; then
  echo "{}"
  exit 0
fi

norm="$path"
in_cc=false
in_orch=false
[[ "$norm" == *"/in/novopay/creditcard/"* || "$norm" == *"src/main/java/in/novopay/creditcard/"* ]] && in_cc=true
[[ "$norm" == *"/deploy/application/orchestration/"* || "$norm" == *"deploy/application/orchestration/"* ]] && in_orch=true
if [[ "$in_cc" != true ]] && [[ "$in_orch" != true ]]; then
  echo "{}"
  exit 0
fi

if [[ "$norm" == *"/src/test/"* ]]; then
  echo "{}"
  exit 0
fi

now="$(date +%s 2>/dev/null || echo 0)"
throttle="$STATE_DIR/posttool-nudge-ts"
if [[ -f "$throttle" ]]; then
  last="$(cat "$throttle" 2>/dev/null || echo 0)"
  if [[ "$((now - last))" -lt 45 ]]; then
    echo "{}"
    exit 0
  fi
fi
printf '%s' "$now" > "$throttle"

msg="Project policy: you edited credit-card scope (in/novopay/creditcard or CC orchestration XML). Generate tests for changed files/diff scope only (plus direct impacted collaborators), not full-repo scan, unless explicitly requested. Follow .cursor/rules/cc-backend-tests-required.mdc and .cursor/skills/cc-backend-test-generation/SKILL.md, then run targeted ./gradlew test."

python3 -c 'import json,sys; print(json.dumps({"additional_context": sys.argv[1]}))' "$msg"
