# Bob the Builder — architecture (ADR)

**Product name:** Bob the Builder  
**Install folder:** `bob-the-builder/`  
**CLI:** `bob` / `bob-the-builder` (same engine)

## One git repo

Publish **`bob-the-builder`** containing `runner/`, `assets/`, `skills/`, `docs/`.

## Paths (never hardcoded)

| Variable | Role |
|----------|------|
| `BUILDER_WORKSPACE_ROOT` | Parent of service git clones (from `bob setup`) |
| `BOB_HOME` | `{workspace}/bob-the-builder/assets` — catalogs |
| `BOB_LOCAL` | `{workspace}/bob-the-builder/local` — `user.env`, session |

## Agent skills

| Skill | Role |
|-------|------|
| `builder-analyst` | Spec + plan |
| `builder-implementer` | Code |
| `builder-verifier` | `validate-ticket` + evidence review |
| `builder-one-shot` | Full flow |

## Commands (name = purpose)

See `bob help` — e.g. `init-ticket`, `validate-ticket`, `discover-apis`, `sync-graph`, `host`, `context`, `eval`, `kafka`, `tools`, `graph sync-obsidian`, `ensure-peers`.

## Diagrams

End-to-end **mermaid** diagram: [TDD_SYSTEM_DEVELOPER_GUIDE.md](TDD_SYSTEM_DEVELOPER_GUIDE.md#architecture-end-to-end) — includes `evidence/kafka` and `evidence/redis` nodes.  
Runtime **topology graph**: `bob graph sync-obsidian` → see [GRAPH_OBSIDIAN.md](GRAPH_OBSIDIAN.md).

## Evidence and verification

`validate-ticket` writes verify docs and `evidence/` subdirs in the host ticket folder:

| Kind | Doc | Folder |
|------|-----|--------|
| DB | `DB_VERIFY_QUERIES.sql` | `evidence/db/` |
| Logs | `LOG_VERIFY_COMMANDS.md` | `evidence/logs/` |
| Kafka | `KAFKA_VERIFY.md` | `evidence/kafka/` |
| Redis | `REDIS_VERIFY.md` | `evidence/redis/` |

Canonical map: [EVIDENCE_AND_VERIFY.md](EVIDENCE_AND_VERIFY.md).  
Human report: `REPORT.md` (not legacy `RUN_SUMMARY.md`).

## Host service repo

Keeps orchestration XML, `deploy/tdd/`, `docs/tdd-runs/<ticket>/`.

## Improvement backlog (Bob product)

Living list of next **engine** work: [NEXT.md](NEXT.md) — `bob next`. Host tickets use `<host>/docs/tdd-runs/<id>/`, not this file.
