#!/usr/bin/env bash
# Merge API/DB/log results into docs/tdd-runs/<ticket>/REPORT.md
set -euo pipefail
source "$(dirname "$0")/lib/prompt-env.sh"

TC_FILE="${1:-}"
if [[ ! -f "$TC_FILE" ]]; then
  echo "Usage: $0 <ticket-spec.yaml>" >&2
  exit 1
fi

TDD_RUN_DIR="$(dirname "$TC_FILE")"
export TDD_RUN_DIR
load_tdd_env "$TDD_RUN_DIR/tdd.env"

TICKET_ID="$(awk '/^  id:/{print $2; exit}' "$TC_FILE" | tr -d '"')"
TICKET_TITLE="$(awk '/^  title:/{print $2; exit}' "$TC_FILE" | tr -d '"')"
REPORT="$TDD_RUN_DIR/REPORT.md"
TS="$(date -Iseconds)"

{
  echo "# Bob the Builder — Validation report"
  echo ""
  echo "**Ticket:** \`$TICKET_ID\`"
  echo ""
  echo "- **Title:** $TICKET_TITLE"
  echo "- **When:** $TS"
  echo "- **Logs dir:** \`$LOGS_DIR\`"
  echo "- **CC:** $CC_BASE"
  echo "- **Masterdata:** $MD_BASE"
  echo ""
  echo "## Test cases"
  if [[ -f "$TDD_RUN_DIR/TEST_PLAN.md" ]]; then
    echo "See [TEST_PLAN.md](./TEST_PLAN.md)"
  else
    echo "See [ticket-spec.yaml](./ticket-spec.yaml)"
  fi
  echo ""
  echo "## Execution summary"
  if [[ -f "$TDD_RUN_DIR/execution-summary.txt" ]]; then
    echo '```'
    cat "$TDD_RUN_DIR/execution-summary.txt"
    echo '```'
  else
    echo "_No execution-summary.txt_"
  fi
  echo ""
  echo "## Log search"
  if [[ -f "$TDD_RUN_DIR/log-search.txt" ]]; then
    echo '```'
    head -200 "$TDD_RUN_DIR/log-search.txt"
    echo '```'
    echo "_Full output: log-search.txt_"
  else
    echo "_Run search-logs.sh first_"
  fi
  echo ""
  echo "## DB verification"
  if [[ -f "$TDD_RUN_DIR/db-verify.txt" ]]; then
    echo '```'
    cat "$TDD_RUN_DIR/db-verify.txt"
    echo '```'
  else
    echo "_No db-verify.txt_"
  fi
  echo ""
  echo "## API responses (last run)"
  if [[ -d "$TDD_RUN_DIR/evidence/api" ]]; then
    for f in "$TDD_RUN_DIR"/evidence/api/*.json; do
      [[ -f "$f" ]] || continue
      echo "### $(basename "$f")"
      echo '```json'
      head -80 "$f"
      echo '```'
    done
  fi
  echo ""
  echo "## Sign-off"
  echo "- [ ] All scenarios PASS"
  echo "- [ ] Logs show stub URLs (9090) when using WireMock"
  echo "- [ ] DB columns match ticket expectations"
} >"$REPORT"

echo "Published $REPORT"

# Enrich with REPORT.md / REPORT.html when Python available
if command -v python3 >/dev/null; then
  python3 -c "
import sys
sys.path.insert(0, '$(dirname "$0")/lib')
from pathlib import Path
from run_summary import build_summary_from_artifacts, publish_run_summary
td = Path('$TDD_RUN_DIR')
data = build_summary_from_artifacts(td)
if data:
    publish_run_summary(td, data)
    print('Published REPORT.md and REPORT.html')
" 2>/dev/null || true
fi
