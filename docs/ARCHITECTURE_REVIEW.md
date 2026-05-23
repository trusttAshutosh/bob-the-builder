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

See `bob help` — e.g. `init-ticket`, `validate-ticket`, `discover-apis`, `sync-graph`, `ticket-status`.

## Host service repo

Keeps orchestration XML, `deploy/tdd/`, `docs/tdd-runs/<ticket>/`.

## Improvement backlog

Living list of next product work: [docs/NEXT.md](NEXT.md) — `bob next`.
