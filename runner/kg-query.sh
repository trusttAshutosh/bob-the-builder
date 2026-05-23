#!/usr/bin/env bash
set -euo pipefail
TDD_ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$TDD_ROOT/lib${PYTHONPATH:+:$PYTHONPATH}"
exec python3 "$TDD_ROOT/lib/session_graph.py" "$@"
