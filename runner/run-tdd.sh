#!/usr/bin/env bash
# Run validation from ticket-spec.yaml (generic pipeline).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/lib/prompt-env.sh"
source "$ROOT/lib/user-prefs.sh" 2>/dev/null || true

TC_FILE="${1:-}"
[[ -f "$TC_FILE" ]] || { echo "Usage: $0 <ticket-spec.yaml>" >&2; exit 1; }

export TDD_RUN_DIR="$(cd "$(dirname "$TC_FILE")" && pwd)"
load_tdd_env "$TDD_RUN_DIR/tdd.env"
load_user_prefs
ensure_logs_dir
ensure_mysql_creds
export MYSQL_AUDIT_SCHEMA="${MYSQL_AUDIT_SCHEMA:-dsa_credit_card_mgmt}"
save_tdd_env "$TDD_RUN_DIR"

# Prefer ticket-spec filename
if [[ -f "$TDD_RUN_DIR/ticket-spec.yaml" ]]; then
  TC_FILE="$TDD_RUN_DIR/ticket-spec.yaml"
fi

echo "=== Bob the Builder — validate-ticket ==="
echo "Spec: $TC_FILE"

TICKET_ID="$(python3 -c "import yaml; d=yaml.safe_load(open('$TC_FILE')); print((d.get('ticket')or{}).get('id',''))" 2>/dev/null || true)"

read -r BRANCH_POLICY GIT_BASE GIT_PREFIX <<<"$(bash "$ROOT/lib/read-git-policy.sh" "$TC_FILE" 2>/dev/null || echo 'none ddp-prod ddp-fea-')"
case "$BRANCH_POLICY" in
  none|'')
    echo "git.branch_policy=none — skipping branch checkout (Bob does not mutate git)"
    ;;
  novopay-feature)
    if [[ -n "$TICKET_ID" ]]; then
      export GIT_BASE_BRANCH="${GIT_BASE:-ddp-prod}"
      export GIT_BRANCH_PREFIX="${GIT_PREFIX:-ddp-fea-}"
      bash "$ROOT/ensure-feature-branch.sh" --ticket "$TICKET_ID" --run-dir "$TDD_RUN_DIR" || true
    fi
    ;;
  *)
    echo "Unknown git.branch_policy: $BRANCH_POLICY (use none or novopay-feature)" >&2
    ;;
esac

if [[ -n "$TICKET_ID" ]]; then
  python3 "$ROOT/lib/session_graph.py" 2>/dev/null || true
  bash "$ROOT/kg-query.sh" "$TICKET_ID" 2>/dev/null | head -50 || true
fi

# Masterdata SQL via python stub registry (after run_flow applies stubs)
export CRN="${CRN:-TDD$(date +%s)}"

if ! command -v python3 >/dev/null; then
  echo "python3 required" >&2
  exit 1
fi

[[ -f "$TC_FILE" ]] && bash "$ROOT/search-logs.sh" "$TC_FILE" 2>/dev/null || true

RC=0
python3 "$ROOT/lib/run_flow.py" "$TDD_RUN_DIR" || RC=$?

if [[ -f "$TDD_RUN_DIR/masterdata-stub-urls.sql" && -n "${MYSQL_BIN:-}" ]]; then
  "$MYSQL_BIN" -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PASS" dsa_masterdata \
    <"$TDD_RUN_DIR/masterdata-stub-urls.sql" 2>/dev/null || true
fi

echo "Report: $TDD_RUN_DIR/REPORT.md"
echo "HTML report: $TDD_RUN_DIR/REPORT.html"
echo "Machine summary: $TDD_RUN_DIR/run-summary.json"
echo "Evidence: $TDD_RUN_DIR/evidence/"
echo ""
echo "Judge run: bob ticket-status ${TICKET_ID:-}"
exit "$RC"
