#!/usr/bin/env bash
# Run from host service repo with bob-the-builder cloned alongside (BUILDER_WORKSPACE_ROOT).
set -euo pipefail
RUNNER="$(cd "$(dirname "$0")/.." && pwd)"
PRODUCT="$(cd "$RUNNER/.." && pwd)"
export PYTHONPATH="$RUNNER/lib"
python3 "$RUNNER/lib/tdd_engine.py" discover
CATALOG="${BOB_HOME:-$PRODUCT/assets}/api-catalog"
if ! git diff --quiet "$CATALOG" 2>/dev/null; then
  echo "ERROR: api-catalog drift — run discover-apis and commit under BOB_HOME"
  git diff --stat "$CATALOG" || true
  exit 1
fi
echo "api-catalog OK"
