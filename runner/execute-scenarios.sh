#!/usr/bin/env bash
# Run scenario steps from ticket-spec.yaml using api-catalog + per-ticket overrides.
set -euo pipefail
TDD_ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$TDD_ROOT/lib/prompt-env.sh"

TC_FILE="${1:-}"
[[ -f "$TC_FILE" ]] || { echo "Usage: $0 <ticket-spec.yaml>" >&2; exit 1; }
TDD_RUN_DIR="$(cd "$(dirname "$TC_FILE")" && pwd)"
export TDD_RUN_DIR
load_tdd_env "$TDD_RUN_DIR/tdd.env"
load_user_prefs 2>/dev/null || true

if ! curl -sf -o /dev/null "${CC_BASE}/actuator/health" 2>/dev/null; then
  echo "SKIP API: CC down at $CC_BASE"
  exit 2
fi

command -v python3 >/dev/null || { echo "python3 required"; exit 1; }
python3 "$TDD_ROOT/lib/tdd_engine.py" execute "$TDD_RUN_DIR"
