#!/usr/bin/env bash
# Search LOGS_DIR for patterns listed in ticket-spec.yaml (or args).
set -euo pipefail
source "$(dirname "$0")/lib/prompt-env.sh"

TC_FILE="${1:-}"
if [[ -z "$TC_FILE" || ! -f "$TC_FILE" ]]; then
  echo "Usage: $0 <docs/tdd-runs/.../ticket-spec.yaml> [scenario_id]" >&2
  exit 1
fi
SCENARIO_FILTER="${2:-}"

TDD_RUN_DIR="$(dirname "$TC_FILE")"
export TDD_RUN_DIR
load_tdd_env "$TDD_RUN_DIR/tdd.env"
ensure_logs_dir

REPORT="$TDD_RUN_DIR/log-search.txt"
: >"$REPORT"
echo "LOGS_DIR=$LOGS_DIR" | tee -a "$REPORT"
echo "Searched: $(date -Iseconds)" | tee -a "$REPORT"

parse_patterns() {
  local sid="$1"
  awk -v sid="$sid" '
    $0 ~ /^  - id: / { cur=$3; gsub(/"/,"",cur) }
    sid != "" && cur != sid { next }
    sid == "" || cur == sid {
      if ($0 ~ /log_patterns:/) { inp=1; next }
      if (inp && $0 ~ /^      - /) { gsub(/^      - /,""); gsub(/"/,""); print }
      if (inp && $0 !~ /^      / && $0 !~ /^    log/) { inp=0 }
    }
  ' "$TC_FILE"
}

while IFS= read -r sid; do
  [[ -z "$sid" ]] && continue
  [[ -n "$SCENARIO_FILTER" && "$sid" != "$SCENARIO_FILTER" ]] && continue
  echo "" | tee -a "$REPORT"
  echo "=== Scenario $sid ===" | tee -a "$REPORT"
  while IFS= read -r pat; do
    [[ -z "$pat" ]] && continue
    echo "--- pattern: $pat ---" | tee -a "$REPORT"
    grep -rn --include="*.log" --include="*.out" --include="*.err" -m 20 "$pat" "$LOGS_DIR" 2>/dev/null | tee -a "$REPORT" || echo "(no matches)" | tee -a "$REPORT"
  done < <(parse_patterns "$sid")
done < <(awk '/^  - id: /{print $3}' "$TC_FILE" | tr -d '"')

echo "Wrote $REPORT"
