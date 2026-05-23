#!/usr/bin/env bash
# Persistent Bob the Builder preferences (all tickets in this repo).
set -euo pipefail

TDD_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$TDD_LIB/common.sh"

USER_PREFS_FILE="${TDD_USER_PREFS_FILE:-$REPO_ROOT/.local/tdd-user.env}"
GLOBAL_PREFS_FILE="${HOME}/.bob-the-builder.env"
GLOBAL_PREFS_LEGACY="${HOME}/.novopay-cc-tdd.env"

load_user_prefs() {
  if [[ -f "$GLOBAL_PREFS_LEGACY" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$GLOBAL_PREFS_LEGACY"
    set +a
  fi
  if [[ -f "$GLOBAL_PREFS_FILE" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$GLOBAL_PREFS_FILE"
    set +a
  fi
  if [[ -f "$USER_PREFS_FILE" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$USER_PREFS_FILE"
    set +a
  fi
  return 0
}

save_user_prefs() {
  mkdir -p "$(dirname "$USER_PREFS_FILE")"
  cat >"$USER_PREFS_FILE" <<EOF
# Bob the Builder — saved for all tickets (do not commit; .local/ is gitignored)
# Updated: $(date -Iseconds)

NOVOPAY_WORKSPACE_ROOT=${NOVOPAY_WORKSPACE_ROOT:-}
LOGS_DIR=${LOGS_DIR:-}
MYSQL_HOST=${MYSQL_HOST:-127.0.0.1}
MYSQL_PORT=${MYSQL_PORT:-3306}
MYSQL_USER=${MYSQL_USER:-root}
MYSQL_PASS=${MYSQL_PASS:-root}
CC_BASE=${CC_BASE:-http://localhost:8016/cc-mgmt}
MD_BASE=${MD_BASE:-http://localhost:8015/masterdata}
GIT_BASE_BRANCH=${GIT_BASE_BRANCH:-ddp-prod}
GIT_BRANCH_PREFIX=${GIT_BRANCH_PREFIX:-ddp-fea-}
TENANT=${TENANT:-dsa}
CLIENT=${CLIENT:-dsa_agent_app}
TDD_REUSE_CURRENT=${TDD_REUSE_CURRENT:-1}
EOF
  chmod 600 "$USER_PREFS_FILE" 2>/dev/null || true
  echo "Saved preferences → $USER_PREFS_FILE"
}

prompt_keep_or_new() {
  local varname="$1" label="$2" default="${3:-}"
  local current="${!varname:-}"
  local input
  if [[ -n "$current" ]]; then
    if [[ "$TDD_NONINTERACTIVE" == "1" || "$TDD_USE_SAVED_PREFS" == "1" ]]; then
      return 0
    fi
    read -r -p "$label [$current] (Enter=keep): " input || true
    input="${input:-$current}"
  else
    read -r -p "$label [$default]: " input || true
    input="${input:-$default}"
  fi
  printf -v "$varname" '%s' "$input"
  export "$varname"
}

run_prefs_wizard() {
  echo ""
  echo "=== Bob the Builder — first-time / reconfigure setup ==="
  load_user_prefs
  if [[ -f "$USER_PREFS_FILE" ]]; then
    echo "Using saved prefs from $USER_PREFS_FILE (Enter = keep value)"
  else
    echo "First run — answers are remembered in .local/tdd-user.env"
  fi

  echo ""
  echo "Novopay services usually live in ONE parent folder (multiple git repos)."
  echo "Bob needs that path to point you at application.properties and DB setup per service."
  local ws_default="${NOVOPAY_WORKSPACE_ROOT:-$(dirname "$REPO_ROOT")}"
  prompt_keep_or_new NOVOPAY_WORKSPACE_ROOT "Novopay workspace root (parent of all service repos)" "$ws_default"
  if [[ ! -d "$NOVOPAY_WORKSPACE_ROOT" ]]; then
    echo "WARN: workspace path does not exist yet: $NOVOPAY_WORKSPACE_ROOT"
  else
    echo "Workspace OK. See deploy/tdd/workspace-services.yaml for repo names under this path."
  fi
  export NOVOPAY_WORKSPACE_ROOT

  prompt_keep_or_new LOGS_DIR "Logs directory (searched for evidence)" "$REPO_ROOT"
  prompt_keep_or_new MYSQL_HOST "MySQL host" "127.0.0.1"
  prompt_keep_or_new MYSQL_PORT "MySQL port" "3306"
  prompt_keep_or_new MYSQL_USER "MySQL user" "root"

  local bin
  bin="$(find_mysql)" || true
  if [[ -n "${bin:-}" ]] && mysql_ping "$bin" 2>/dev/null; then
    echo "MySQL: connection OK (user=$MYSQL_USER)"
  else
    if [[ "$TDD_NONINTERACTIVE" != "1" ]]; then
      read -r -p "MySQL password [$MYSQL_PASS]: " -s input || true
      echo
      [[ -n "${input:-}" ]] && MYSQL_PASS="$input"
    fi
    export MYSQL_PASS
    if [[ -n "${bin:-}" ]] && ! mysql_ping "$bin"; then
      read -r -p "MySQL password (retry): " -s MYSQL_PASS
      echo
      export MYSQL_PASS
      mysql_ping "$bin" || { echo "MySQL failed — fix creds in .local/tdd-user.env" >&2; return 1; }
    fi
  fi
  export MYSQL_BIN="${bin:-$(find_mysql)}"

  echo ""
  echo "Service base URLs (only if you run those services locally):"
  prompt_keep_or_new CC_BASE "credit-card-management base URL" "http://localhost:8016/cc-mgmt"
  prompt_keep_or_new MD_BASE "masterdata-management base URL" "http://localhost:8015/masterdata"
  prompt_keep_or_new GIT_BASE_BRANCH "Git base branch" "ddp-prod"
  prompt_keep_or_new TENANT "Tenant code" "dsa"
  prompt_keep_or_new CLIENT "Client code" "dsa_agent_app"

  save_user_prefs
  echo ""
  echo "Before bob validate-ticket: ensure deploy/tdd/ is configured; Bob can bootRun services automatically."
  echo "Reference: deploy/tdd/workspace-services.yaml"
  echo ""
}

collect_ticket_interactive() {
  if [[ -n "${TICKET_ID:-}" && -n "${TICKET_TITLE:-}" ]]; then
    return 0
  fi
  echo "=== Ticket ==="
  prompt_if_empty TICKET_ID "Ticket id (e.g. CC-12345)" "TICKET-$(date +%Y%m%d)"
  read -r -p "Ticket title: " TICKET_TITLE || true
  [[ -n "${TICKET_TITLE:-}" ]] || TICKET_TITLE="TDD $TICKET_ID"
  echo "Description (end with empty line):"
  local line desc=""
  while IFS= read -r line; do
    [[ -z "$line" ]] && break
    desc+="$line"$'\n'
  done
  TICKET_DESC="${desc:-$TICKET_DESC}"
  export TICKET_ID TICKET_TITLE TICKET_DESC
}

write_ticket_artifacts() {
  local dir="$REPO_ROOT/docs/tdd-runs/$TICKET_ID"
  mkdir -p "$dir"
  export TDD_RUN_DIR="$dir"

  if [[ ! -f "$dir/ticket-spec.yaml" ]]; then
    python "$TDD_ROOT/../bob.py" init-ticket "$TICKET_ID" "$TICKET_TITLE" 2>/dev/null || \
      cp "$TDD_ROOT/schemas/ticket-spec.schema.yaml" "$dir/ticket-spec.yaml"
  fi

  cat >"$dir/ticket.md" <<EOF
# $TICKET_TITLE

**Id:** $TICKET_ID  
**Created:** $(date -Iseconds)

## Description

${TICKET_DESC:-_(none provided)_}

## Raw notes / logs / images

_Add paths or paste below when sharing with the agent._
EOF

  save_tdd_env "$dir"
  echo "Ticket folder: $dir"
  echo "  ticket-spec.yaml, TEST_PLAN.md, evidence/"
}
