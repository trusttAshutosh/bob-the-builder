#!/usr/bin/env bash
# Start WireMock using WIREMOCK_ROOT (per-ticket runtime dir from tdd_engine apply-stubs).
set -euo pipefail
TDD_ROOT="$(cd "$(dirname "$0")" && pwd)"
ROOT="${WIREMOCK_ROOT:-$TDD_ROOT/.runtime-wiremock/default}"
PORT="${WIREMOCK_PORT:-9090}"
JAR="${WIREMOCK_JAR:-$TDD_ROOT/lib/wiremock-standalone-3.13.2.jar}"

if [[ ! -f "$JAR" ]]; then
  mkdir -p "$(dirname "$JAR")"
  curl -fsSL -o "$JAR" \
    "https://repo1.maven.org/maven2/org/wiremock/wiremock-standalone/3.13.2/wiremock-standalone-3.13.2.jar"
fi

PID_FILE="$ROOT/.wiremock.pid"
mkdir -p "$ROOT/mappings" "$ROOT/__files"
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "WireMock already running pid $(cat "$PID_FILE") port $PORT root=$ROOT"
  exit 0
fi
nohup java -jar "$JAR" --port "$PORT" --root-dir "$ROOT" >>"$ROOT/wiremock.log" 2>&1 &
echo $! >"$PID_FILE"
sleep 2
curl -sf "http://localhost:$PORT/__admin/mappings" >/dev/null && echo "WireMock OK http://localhost:$PORT root=$ROOT"
