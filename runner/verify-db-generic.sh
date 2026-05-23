#!/usr/bin/env bash
# DB assertions from ticket-spec.yaml for a given scenario + CRN.
set -euo pipefail
source "$(dirname "$0")/lib/prompt-env.sh"

TC_FILE="${1:-}"
SCENARIO="${2:-}"
CRN="${3:-}"

if [[ -z "$TC_FILE" || -z "$SCENARIO" || -z "$CRN" ]]; then
  echo "Usage: $0 <ticket-spec.yaml> <scenario_id> <client_reference_code>" >&2
  exit 1
fi

TDD_RUN_DIR="$(dirname "$TC_FILE")"
export TDD_RUN_DIR
load_tdd_env "$TDD_RUN_DIR/tdd.env"
ensure_mysql_creds || exit 1
export MYSQL_BIN="${MYSQL_BIN:-$(find_mysql)}"

AUDIT_DB="$(awk '/^run:/{f=1} f && /audit_db:/{print $2; exit}' "$TC_FILE")"
AUDIT_DB="${AUDIT_DB:-dsa_credit_card_mgmt}"

mysql_query() {
  local bin="${MYSQL_BIN:-$(find_mysql)}"
  "$bin" -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PASS" \
    --batch --skip-column-names "$AUDIT_DB" -e "$1"
}

row="$(mysql_query "
  SELECT txn_status, txn_result_code, txn_result_description, internal_txn_desc
  FROM transaction_audit
  WHERE client_reference_code = '${CRN}'
  ORDER BY updated_on DESC LIMIT 1;
" 2>/dev/null || true)"

if [[ -z "$row" ]]; then
  echo "FAIL $SCENARIO DB: no row for CRN=$CRN"
  exit 1
fi

IFS=$'\t' read -r st code desc internal <<<"$row"
echo "DB row CRN=$CRN status=$st code=$code desc=$desc internal=$internal"

# Parse expect block (simple key: value under scenario)
in_sc=0
fail=0
while IFS= read -r line; do
  [[ "$line" =~ ^[[:space:]]*-[[:space:]]*id:[[:space:]]*$SCENARIO ]] && in_sc=1 && continue
  [[ $in_sc -eq 1 && "$line" =~ ^[[:space:]]*-[[:space:]]*id: ]] && break
  [[ $in_sc -eq 0 ]] && continue
  if [[ "$line" =~ txn_status:[[:space:]]*(.+) ]]; then
    exp="${BASH_REMATCH[1]}"; exp="${exp//\"/}"; exp="${exp// /}"
    [[ "$st" == "$exp" ]] || { echo "  mismatch txn_status: want=$exp got=$st"; fail=1; }
  fi
  if [[ "$line" =~ txn_result_code:[[:space:]]*(.+) ]]; then
    exp="${BASH_REMATCH[1]}"; exp="${exp//\"/}"; exp="${exp// /}"
    [[ "$code" == "$exp" ]] || { echo "  mismatch txn_result_code: want=$exp got=$code"; fail=1; }
  fi
  if [[ "$line" =~ txn_result_description:[[:space:]]*(.+) ]]; then
    exp="${BASH_REMATCH[1]}"; exp="${exp//\"/}"; exp="${exp// /}"
    [[ "$desc" == "$exp" ]] || { echo "  mismatch txn_result_description: want=$exp got=$desc"; fail=1; }
  fi
  if [[ "$line" =~ internal_txn_desc:[[:space:]]*(.+) ]]; then
    exp="${BASH_REMATCH[1]}"; exp="${exp//\"/}"; exp="${exp// /}"
    [[ "$internal" == "$exp" ]] || { echo "  mismatch internal_txn_desc: want=$exp got=$internal"; fail=1; }
  fi
  if [[ "$line" =~ internal_txn_desc_prefix:[[:space:]]*(.+) ]]; then
    exp="${BASH_REMATCH[1]}"; exp="${exp//\"/}"; exp="${exp// /}"
    [[ "$internal" == "$exp"* ]] || { echo "  mismatch internal_txn_desc prefix: want=$exp* got=$internal"; fail=1; }
  fi
done < "$TC_FILE"

# must_not_contain (crude: Sorry in desc)
if [[ "$desc" == *Sorry,* ]]; then
  echo "  FAIL: txn_result_description contains Sorry,"
  fail=1
fi

if [[ $fail -eq 0 ]]; then
  echo "PASS $SCENARIO DB"
  exit 0
fi
echo "FAIL $SCENARIO DB"
exit 1
