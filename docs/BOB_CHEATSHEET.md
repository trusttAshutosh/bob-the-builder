# Bob the Builder — cheat sheet

**Once:** `bob setup` → enter **workspace root** (parent of all service git clones). Stored as `BUILDER_WORKSPACE_ROOT`.

| Command | What it does |
|---------|----------------|
| `bob setup` | Workspace, MySQL, `{SERVICE}_BASE` URLs from host `deploy/tdd` → `BOB_LOCAL/user.env` |
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
| `bob kafka discover\|setup\|up …` | Flow-scoped Kafka bindings (see KAFKA_FOR_BOB.md) |
| `bob validate-ticket ID` | Run ticket + evidence (+ context pack, eval check by default) |
| `bob ticket-status ID` | PASS/FAIL + decision trace |
| `bob open-report ID` | Paths to HTML / summary |
| `bob list-tickets` | List ticket IDs |
| `bob query-graph [words]` | Agent context slice |
| `bob help` | Full command list (`bob bobhelp`, `bob h`, `bob ?`) |
| `bob next` | Improvement backlog → [docs/NEXT.md](NEXT.md) |
| `bob verify-product` | Check feature registry; `--update` refreshes scorecard sections in NEXT.md |
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
| `assets/examples/` | Reference packs only (e.g. `novopay-cc/`) — Bob does not load these automatically |
| `BOB_LOCAL` | `bob-the-builder/local/` — secrets + `agent/` (never commit) |

Short: `s` `i` `d` `r` `st` `o` `l` map to the above.

Guides: [README.md](README.md) (index) · [TDD_SYSTEM_DEVELOPER_GUIDE.md](TDD_SYSTEM_DEVELOPER_GUIDE.md) · [WORKSPACE_AND_HOST_PROFILE.md](WORKSPACE_AND_HOST_PROFILE.md)
