#!/usr/bin/env bash
# Bob Cursor hook runner - do not edit; logic lives in `bob cursor-hook`.
set -euo pipefail
KIND="${1:-}"
BOB_PY_FILE="${HOME}/.cursor/hooks/.bob-py"
if [ ! -f "$BOB_PY_FILE" ]; then
  exit 0
fi
BOB_PY="$(tr -d '\r\n' < "$BOB_PY_FILE")"
if [ -z "$BOB_PY" ] || [ ! -f "$BOB_PY" ]; then
  exit 0
fi
case "$KIND" in
  session)
    python3 "$BOB_PY" cursor-hook session >/dev/null 2>&1 || true
    ;;
  stop)
    export HOOK_STOP_JSON="$(cat)"
    exec python3 "$BOB_PY" cursor-hook stop
    ;;
  *)
    exit 0
    ;;
esac
