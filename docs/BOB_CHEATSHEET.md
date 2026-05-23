# Bob the Builder — cheat sheet

**Once:** `bob setup` → enter **workspace root** (parent of all service git clones). Stored as `BUILDER_WORKSPACE_ROOT`.

| Command | What it does |
|---------|----------------|
| `bob setup` | Save workspace path, MySQL, URLs → `BOB_LOCAL/user.env` |
| `bob install` | Seed **empty** `assets/` from `_seed` + `local/` (CC reference lives under `assets/examples/`) |
| `bob install --launchers` | Optional: also write `{workspace}/bob.py` + `bob.cmd` shortcuts |
| `bob cleanup-workspace --apply` | One folder only: merge/remove stale `novopay-bob*`, `.bob-the-builder` |
| `bob init-ticket ID "Title"` | New folder `docs/tdd-runs/ID/` in host repo |
| `bob discover-apis` | Orchestration → `BOB_HOME/api-catalog/` |
| `bob sync-graph` | Processors/APIs → `BOB_HOME/platform-graph/` |
| `bob validate-ticket ID` | Run ticket + evidence |
| `bob ticket-status ID` | PASS/FAIL + decision trace |
| `bob open-report ID` | Paths to HTML / summary |
| `bob list-tickets` | List ticket IDs |
| `bob query-graph [words]` | Agent context slice |
| `bob help` | Full command list (`bob bobhelp`, `bob h`, `bob ?`) |
| `bob next` | Improvement backlog → [docs/NEXT.md](NEXT.md) |
| `bob verify-product` | Check feature registry; `--update` refreshes scorecard sections in NEXT.md |
| Host setup | Copy `templates/host-deploy-tdd/` → `deploy/tdd/` in service repo |

| Path | Contents |
|------|----------|
| `BOB_HOME` | Shared catalogs (`bob-the-builder/assets/`) — starts empty; version in git if your team chooses |
| `assets/examples/` | Reference packs only (e.g. `novopay-cc/`) — Bob does not load these automatically |
| `BOB_LOCAL` | `bob-the-builder/local/` — secrets + `agent/` (never commit) |

Short: `s` `i` `d` `r` `st` `o` `l` map to the above.

Guide: [TDD_SYSTEM_DEVELOPER_GUIDE.md](TDD_SYSTEM_DEVELOPER_GUIDE.md)
