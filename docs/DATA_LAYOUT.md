# Where Bob writes files (no git from Bob)

**Bob never runs `git commit`, `git push`, or opens PRs.** Only humans do that, when they choose.

By default **`git.branch_policy: none`** — `validate-ticket` does not checkout branches. Set **`novopay-feature`** in `ticket-spec.yaml` for optional Novopay `ddp-fea-*` checkout.

## Bob the Builder repo (`bob-the-builder/`)

| Path | Purpose |
|------|---------|
| `runner/`, `skills/`, `docs/` | Product source (versioned by your team in git) |
| `assets/api-catalog/` | Gateway API defs after `discover-apis` (starts **empty**) |
| `assets/platform-graph/` | Knowledge graph after `sync-graph` |
| `local/obsidian-vault/` | Obsidian export for live graph view (`bob graph sync-obsidian`) |
| `assets/stub-registry/` | Shared WireMock fixtures (starts **empty**) |
| `assets/examples/novopay-cc/` | **Reference only** — CC/LOC catalog snapshot; not loaded by Bob |
| `local/` | **Machine-only** — `user.env`, agent session, WireMock runtime (gitignored) |
| `local/agent/required-services.yaml` | Session peer registry (from `need-service` / discovery) |
| `local/agent/kg-context-last.md` | Last `query-graph` / hybrid retrieval slice |
| `local/agent/context-pack-last.md` | Last `bob context` output copy |
| `local/.runtime-services/` | Bob-started `bootRun` pid + logs |
| `local/bin/` | `bob` / `bob.cmd` shims; added to user PATH **once** on first command |

Bob updates files under `assets/` and `local/` on disk. Whether those land in git is **your** decision, not Bob’s.

**Product improvements:** [NEXT.md](NEXT.md) (`bob next`) — Bob engine backlog only. Host-ticket scope lives under `<host>/docs/tdd-runs/<ticket-id>/` (see table below).

## Host service repo (e.g. credit-card-management)

| Path | Purpose |
|------|---------|
| `docs/tdd-runs/<ticket-id>/ticket-spec.yaml` | Ticket definition |
| `docs/tdd-runs/<ticket-id>/evidence/` | Proof from `validate-ticket` (`api/`, `db/`, `logs/`, `kafka/`, `redis/`, `unit/`) |
| `docs/tdd-runs/<ticket-id>/REPORT.md`, `REPORT.html`, `run-summary.json` | Single human + machine report (`RUN_SUMMARY.md` not used) |
| `docs/tdd-runs/<ticket-id>/DB_VERIFY_QUERIES.sql` | MySQL dashboard + per-scenario SELECTs |
| `docs/tdd-runs/<ticket-id>/LOG_VERIFY_COMMANDS.md` | Copy-paste grep/rg for applogs (`LOGS_DIR`) |
| `docs/tdd-runs/<ticket-id>/CONTEXT_PACK.md` | Prefs, stale warnings, hybrid KG slice (`bob context` / validate) |
| `docs/tdd-runs/<ticket-id>/KAFKA_VERIFY.md` | Kafka bindings + verify notes when `run.kafka.mode` is on/auto |
| `docs/tdd-runs/<ticket-id>/REDIS_VERIFY.md` | Redis redis-cli commands + capture notes when `run.redis` / `evidence_required: redis` |
| `docs/tdd-runs/<ticket-id>/EVAL_REGRESSION.md` | Eval drift vs `eval-baseline.json` when `run.eval.mode: check` |
| `docs/tdd-runs/<ticket-id>/kafka-discovered.json` | Discovered topics/listeners for the ticket flow |
| `docs/tdd-runs/<ticket-id>/log-search.txt` | Log grep output when `LOGS_DIR` is set |

Full verify/evidence map: [EVIDENCE_AND_VERIFY.md](EVIDENCE_AND_VERIFY.md).

Ticket folders stay in the **service** repo. Generated proof is gitignored in the host repo so it stays local.

## Novopay CC reference (optional)

- Live catalogs: `bob-the-builder/assets/api-catalog/`, `stub-registry/` — from **`bob discover-apis`** on your host repo
- CC snapshot for copy/compare: `bob-the-builder/assets/examples/novopay-cc/`
- Ticket + run output stays in the **host** repo under `docs/tdd-runs/<ticket-id>/`
