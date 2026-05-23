#!/usr/bin/env bash
# Read git.branch_policy from ticket-spec.yaml. Prints: policy base_branch branch_prefix
set -euo pipefail
SPEC="${1:-}"
[[ -f "$SPEC" ]] || { echo "none ddp-prod ddp-fea-"; exit 0; }
TDD_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$TDD_ROOT/lib${PYTHONPATH:+:$PYTHONPATH}"
python3 - "$SPEC" <<'PY'
import sys
from pathlib import Path

from _yaml_util import load
from ticket_spec import git_checkout_env

spec = load(Path(sys.argv[1]))
env = git_checkout_env(spec)
print(env["branch_policy"], env["base_branch"], env["branch_prefix"])
PY
