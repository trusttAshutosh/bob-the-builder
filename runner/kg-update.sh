#!/usr/bin/env bash
set -euo pipefail
TDD_ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$TDD_ROOT/lib${PYTHONPATH:+:$PYTHONPATH}"
if [[ $# -eq 0 ]]; then
  exec python3 "$TDD_ROOT/lib/platform_graph.py"
fi
python3 "$TDD_ROOT/lib/platform_graph.py"
exec python3 "$TDD_ROOT/lib/session_graph.py" update "$@"
