# Bob the Builder — cheat sheet

**Once:** `bob setup` → enter **workspace root** (parent of all service git clones). Stored as `BUILDER_WORKSPACE_ROOT`.

| Command | What it does |
|---------|----------------|
| `bob plugins` | Recommended Cursor marketplace plugins (manual install; maps to squad workflows) |
| `bob meta-review [--dry-run]` | Monthly usage audit -> `docs/META_REVIEW.md` + context/MCP audits (stop hook every 30d) |
| `bob context-audit [--dry-run]` | Cursor context % audit across active/archived chats |
| `bob memory-budget [--dry-run] [--json]` | Working memory budget -> `docs/MEMORY_BUDGET.md` + workspace status JSON |
| `bob mcp-audit [--dry-run] [--json]` | MCP + plugin keep/disable list for this machine -> `docs/MCP_AUDIT.md` |
| `bob prune-overhead --dry-run` / `--apply` | Apply Bob squad MCP/plugin policy; reload Cursor after apply |
| `bob chat-hygiene [--dry-run] [--auto]` | Archive stale/overflow Cursor chats (never delete) |
| `bob onboard` | Setup + install + full squad Cursor kit (skills, rules, hooks, CC junction) + plugin notice |
| `bob setup` | Workspace, MySQL, `{SERVICE}_BASE` URLs from host `deploy/tdd` → `BOB_LOCAL/user.env` |
| `bob path-shim [--force]` | Put `bob` + hyphenated commands on PATH (`validate-ticket`, `verify-all`, …) |
| `bob doctor` | Diagnose PATH/python/shims; shows exact fix if commands fail |
| `bob host` | Show `BOB_HOST_REPO`, workspace repos, active `deploy/tdd` profile |
| `bob install` | Seed **empty** `assets/` from `_seed` + `local/`; install post-commit hook |
| `bob install-hooks` | Re-install git post-commit hook (auto NEXT.md after commit) |
| `bob install --launchers` | Optional: also write `{workspace}/bob.py` + `bob.cmd` shortcuts |
| `bob cleanup-workspace --apply` | One folder only: merge/remove stale `novopay-bob*`, `.bob-the-builder` |
| `bob init-ticket ID "Title"` | New folder `docs/tdd-runs/ID/` in host repo |
| `bob discover-apis` | Orchestration → `BOB_HOME/api-catalog/` |
| `bob sync-graph` | Processors/APIs → `BOB_HOME/platform-graph/` (+ Obsidian vault if enabled) |
| `bob graph sync-obsidian` | Export platform/session graph → `local/obsidian-vault/` |
| `bob context --ticket ID` | Write `CONTEXT_PACK.md` (prefs, stale, hybrid KG) |
| `bob eval baseline\|check\|update ID` | REPORT artifact regression vs baseline |
| `bob kafka discover\|setup\|up …` | Flow-scoped Kafka bindings (see [KAFKA_FOR_BOB.md](KAFKA_FOR_BOB.md)) |
| `bob tools list\|run\|backend` | Tool bridge: git, MySQL, context (local default; optional MCP) |
| `bob validate-ticket ID` | Run ticket + evidence: api/db/logs/kafka/redis (+ context, eval) |
| `bob ticket-status ID` | PASS/FAIL + decision trace |
| `bob open-report ID` | Paths to HTML / summary |
| `bob list-tickets` | List ticket IDs |
| `bob query-graph [words]` | Agent context slice |
| `bob help` | Full command list (`bob bobhelp`, `bob h`, `bob ?`) |
| `bob next` | Print **Bob product** backlog → [NEXT.md](NEXT.md) (engine work only; not ticket Plan/Build/Prove) |
| `bob next --edit` | Open [NEXT.md](NEXT.md) in `$EDITOR` |
| `bob verify-product` | Check feature registry; `--update` refreshes scorecard sections in NEXT.md |
| `bob verify-docs` | Check docs vs [doc-invariants.yaml](doc-invariants.yaml) + CLI (wrong/incomplete product docs) |
| `bob verify-all` | `verify-product` + `verify-docs` + `verify-contract-governance` |
| `bob verify-contract-governance` | Block contract weakening without recorded human approval |
| `bob contract-diff [--vs REF]` | Show contract weakenings vs base (read before approving) |
| `bob approve-contract-change --reason "..."` | Human-only: type **APPROVE** after review; writes `docs/contract-approvals/` |
| `bob verify-fresh-install` | Prove empty catalog after install + non-CC `discover-apis` (CI fixture) |
| `bob ensure-peers` | Scan host code/properties; boot peer services not already up (no deploy/tdd required) |
| `bob need-service NAME` | Register + boot one peer by hint (`notifications`, `consents`, `masterdata`, …) |
| `bob discover-services` | List peers; add `--boot` to start all |
| `bob start-services` | Gradle bootRun from env profile / ticket |
| `bob services-status` | Health + pid |
| `bob stop-services` | Stop Bob-started bootRun |
| Host setup | Copy `templates/host-deploy-tdd/` → `deploy/tdd/` in service repo (optional; helps env profiles) |

| Path | Contents |
|------|----------|
| `BOB_HOME` | Shared catalogs (`bob-the-builder/assets/`) — starts empty; version in git if your team chooses |
| `assets/examples/` | Reference only: `sample-validate-output/` (generated bundle), `novopay-cc/` (CC catalog snapshot) |
| `BOB_LOCAL` | `bob-the-builder/local/` — secrets + `agent/` (never commit) |

Short: `s` `i` `d` `r` `st` `o` `l` map to the above.

Guides: [README.md](README.md) (index) · [EVIDENCE_AND_VERIFY.md](EVIDENCE_AND_VERIFY.md) · [TDD_SYSTEM_DEVELOPER_GUIDE.md](TDD_SYSTEM_DEVELOPER_GUIDE.md) · [WORKSPACE_AND_HOST_PROFILE.md](WORKSPACE_AND_HOST_PROFILE.md) · [MOBILE_CURSOR_RELAY.md](MOBILE_CURSOR_RELAY.md)
