#!/usr/bin/env bash
set -euo pipefail
exec python3 "$(dirname "$0")/lib/tdd_engine.py" discover "$@"
