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
| `builder-verifier` | `validate-ticket` |
| `builder-one-shot` | Full flow |

## Commands (name = purpose)

See `bob help` — e.g. `init-ticket`, `validate-ticket`, `discover-apis`, `sync-graph`, `host`, `context`, `eval`, `kafka`, `graph sync-obsidian`, `ensure-peers`.

## Diagrams

End-to-end **mermaid** diagram: [TDD_SYSTEM_DEVELOPER_GUIDE.md](TDD_SYSTEM_DEVELOPER_GUIDE.md#architecture-end-to-end).  
Runtime **topology graph**: `bob graph sync-obsidian` → see [GRAPH_OBSIDIAN.md](GRAPH_OBSIDIAN.md).

## Host service repo

Keeps orchestration XML, `deploy/tdd/`, `docs/tdd-runs/<ticket>/`.

## Improvement backlog

Living list of next product work: [NEXT.md](NEXT.md) — `bob next`.
