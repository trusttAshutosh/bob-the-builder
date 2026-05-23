# Where Bob writes files (no git from Bob)

**Bob never runs `git commit`, `git push`, or opens PRs.** Only humans do that, when they choose.

By default **`git.branch_policy: none`** — `validate-ticket` does not checkout branches. Set **`novopay-feature`** in `ticket-spec.yaml` for optional Novopay `ddp-fea-*` checkout.

## Bob the Builder repo (`bob-the-builder/`)

| Path | Purpose |
|------|---------|
| `runner/`, `skills/`, `docs/` | Product source (versioned by your team in git) |
| `assets/api-catalog/` | Gateway API defs after `discover-apis` (starts **empty**) |
| `assets/platform-graph/` | Knowledge graph after `sync-graph` |
| `assets/stub-registry/` | Shared WireMock fixtures (starts **empty**) |
| `assets/examples/novopay-cc/` | **Reference only** — CC/LOC catalog snapshot; not loaded by Bob |
| `local/` | **Machine-only** — `user.env`, agent session, WireMock runtime (gitignored) |
| `local/agent/required-services.yaml` | Session peer registry (from `need-service` / discovery) |
| `local/.runtime-services/` | Bob-started `bootRun` pid + logs |
| `local/bin/` | `bob` / `bob.cmd` shims; added to user PATH **once** on first command |

Bob updates files under `assets/` and `local/` on disk. Whether those land in git is **your** decision, not Bob’s.

**Product improvements:** [NEXT.md](NEXT.md) (`bob next`).

## Host service repo (e.g. credit-card-management)

| Path | Purpose |
|------|---------|
| `docs/tdd-runs/<ticket-id>/ticket-spec.yaml` | Ticket definition |
| `docs/tdd-runs/<ticket-id>/evidence/` | API/DB/log proof from `validate-ticket` |
| `docs/tdd-runs/<ticket-id>/REPORT.*`, `RUN_SUMMARY.*` | Run output |

Ticket folders stay in the **service** repo. Generated proof is gitignored in the host repo so it stays local.

## Novopay CC reference (optional)

- Live catalogs: `bob-the-builder/assets/api-catalog/`, `stub-registry/` — from **`bob discover-apis`** on your host repo
- CC snapshot for copy/compare: `bob-the-builder/assets/examples/novopay-cc/`
- Ticket + run output stays in the **host** repo under `docs/tdd-runs/<ticket-id>/`
