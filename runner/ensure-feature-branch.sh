#!/usr/bin/env bash
# Optional Novopay feature-branch checkout for validate-ticket. Never commits.
# Invoked only when ticket-spec.yaml has git.branch_policy: novopay-feature
#
# Usage:
#   bob-the-builder/runner/ensure-feature-branch.sh --ticket MY-TICKET-123
#   bob-the-builder/runner/ensure-feature-branch.sh --branch ddp-fea-loc-loggers-stage-capture
#   bob-the-builder/runner/ensure-feature-branch.sh --slug loc-audit-001
#   TDD_USE_CURRENT_BRANCH=1 bob-the-builder/runner/ensure-feature-branch.sh --ticket X
#
# Env:
#   BOB_HOST_REPO          host service git root (preferred)
#   GIT_BASE_BRANCH=ddp-prod
#   GIT_BRANCH_PREFIX=ddp-fea-
#   TDD_ALLOW_DIRTY=1          # allow checkout with uncommitted changes
#   TDD_USE_CURRENT_BRANCH=1   # stay on current branch if it matches ddp-fea-*
#
set -euo pipefail

RUNNER_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -n "${BOB_HOST_REPO:-}" ]]; then
  ROOT="$(cd "$BOB_HOST_REPO" && pwd)"
elif git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ROOT="$(git rev-parse --show-toplevel)"
else
  echo "Not a git repository — set BOB_HOST_REPO or run from host service repo" >&2
  exit 1
fi
cd "$ROOT"

BASE_BRANCH="${GIT_BASE_BRANCH:-ddp-prod}"
PREFIX="${GIT_BRANCH_PREFIX:-ddp-fea-}"
TICKET=""
SLUG=""
BRANCH=""
RUN_DIR=""
EXPLICIT_BRANCH=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ticket) TICKET="${2:-}"; shift 2 ;;
    --slug) SLUG="${2:-}"; shift 2 ;;
    --branch) BRANCH="${2:-}"; EXPLICIT_BRANCH=1; shift 2 ;;
    --run-dir) RUN_DIR="${2:-}"; shift 2 ;;
    -h|--help)
      sed -n '2,14p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

slugify() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g'
}

if [[ -z "$BRANCH" ]]; then
  if [[ -z "$SLUG" && -n "$TICKET" ]]; then
    SLUG="$(slugify "$TICKET")"
  fi
  [[ -n "$SLUG" ]] || { echo "Provide --ticket, --slug, or --branch" >&2; exit 1; }
  BRANCH="${PREFIX}${SLUG}"
fi

if [[ "$BRANCH" != "${PREFIX}"* ]]; then
  echo "Branch must start with ${PREFIX} (got $BRANCH)" >&2
  exit 1
fi

current="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
if [[ -z "$current" ]]; then
  echo "Not a git repository: $ROOT" >&2
  exit 1
fi

dirty=0
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
  dirty=1
fi

write_branch_meta() {
  local dir="${1:-}"
  [[ -n "$dir" ]] || return 0
  mkdir -p "$dir"
  {
    echo "feature_branch=$BRANCH"
    echo "base_branch=$BASE_BRANCH"
    echo "ticket=$TICKET"
    echo "prepared_at=$(date -Iseconds)"
    echo "commit_policy=no_commit"
  } >"$dir/branch.env"
  echo "$BRANCH" >"$dir/branch.txt"
}

checkout_branch() {
  local target="$1"
  if [[ "$current" == "$target" ]]; then
    echo "Already on $target"
    write_branch_meta "$RUN_DIR"
    return 0
  fi
  if [[ $dirty -eq 1 && "${TDD_ALLOW_DIRTY:-0}" != "1" ]]; then
    echo "Uncommitted changes on $current — stash or commit elsewhere, or set TDD_ALLOW_DIRTY=1" >&2
    git status -sb >&2 || true
    exit 1
  fi
  if git show-ref --verify --quiet "refs/heads/$target"; then
    git checkout "$target"
    echo "Checked out existing branch $target"
  elif git show-ref --verify --quiet "refs/remotes/origin/$target"; then
    git checkout -b "$target" "origin/$target"
    echo "Checked out local branch from origin/$target"
  else
    echo "Creating $target from $BASE_BRANCH..."
    git fetch origin "$BASE_BRANCH" 2>/dev/null || git fetch origin 2>/dev/null || true
    if git show-ref --verify --quiet "refs/heads/$BASE_BRANCH"; then
      git checkout "$BASE_BRANCH"
      git pull --ff-only origin "$BASE_BRANCH" 2>/dev/null || true
    elif git show-ref --verify --quiet "refs/remotes/origin/$BASE_BRANCH"; then
      git checkout -b "$BASE_BRANCH" "origin/$BASE_BRANCH" 2>/dev/null || git checkout "$BASE_BRANCH"
    else
      echo "Base branch $BASE_BRANCH not found locally or on origin" >&2
      exit 1
    fi
    git checkout -b "$target"
    echo "Created and checked out $target from $BASE_BRANCH"
  fi
  write_branch_meta "$RUN_DIR"
}

# Stay on current ddp-fea-* branch when allowed
if [[ "${TDD_USE_CURRENT_BRANCH:-0}" == "1" && "$current" == "${PREFIX}"* ]]; then
  BRANCH="$current"
  echo "Using current feature branch: $BRANCH (TDD_USE_CURRENT_BRANCH=1)"
  write_branch_meta "$RUN_DIR"
  exit 0
fi

# If already on the target branch, done
if [[ "$current" == "$BRANCH" ]]; then
  echo "Already on $BRANCH"
  write_branch_meta "$RUN_DIR"
  exit 0
fi

# If on another ddp-fea-* branch and no explicit --branch, reuse current when slug matches
if [[ $EXPLICIT_BRANCH -eq 0 && "$current" == "${PREFIX}"* ]]; then
  if [[ "$current" == "$BRANCH" ]] || [[ "$current" == *"${SLUG:-}"* ]]; then
    BRANCH="$current"
    echo "Reusing current branch $BRANCH (matches ticket slug)"
    write_branch_meta "$RUN_DIR"
    exit 0
  fi
  if [[ "${TDD_REUSE_CURRENT:-1}" == "1" ]]; then
    echo "Reusing existing feature branch $current (set TDD_REUSE_CURRENT=0 to create $BRANCH)"
    BRANCH="$current"
    write_branch_meta "$RUN_DIR"
    exit 0
  fi
fi

checkout_branch "$BRANCH"
echo ""
echo "Branch ready: $BRANCH (from $BASE_BRANCH). Policy: implement changes here — do NOT git commit unless user asks."
