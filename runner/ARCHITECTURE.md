# Bob the Builder — architecture

Ticket-driven local validation for backend microservices.

- Guide: [`docs/TDD_SYSTEM_DEVELOPER_GUIDE.md`](../../docs/TDD_SYSTEM_DEVELOPER_GUIDE.md)
- ADR: [`docs/ARCHITECTURE_REVIEW.md`](../../docs/ARCHITECTURE_REVIEW.md)

## Layout

| Piece | Path |
|-------|------|
| Runner | `{workspace}/bob-the-builder/runner/` |
| CLI entry | `{workspace}/bob-the-builder/bob.py` |
| Assets | `BOB_HOME` → `bob-the-builder/assets/` |
| Local | `BOB_LOCAL` → `bob-the-builder/local/` (gitignored) |
| Tickets | Host repo `docs/tdd-runs/<id>/` |

Set `BUILDER_WORKSPACE_ROOT` via `bob setup` only — no hardcoded machine paths.

## CLI

`python bob.py <command>` or `bob <command>` (after first-run PATH shim) — see `bob help`.

Core commands: `setup`, `install`, `init-ticket`, `discover-apis`, `sync-graph`, `validate-ticket`, `ticket-status`, `open-report`, `list-tickets`, `query-graph`, `ensure-peers`, `need-service`, `discover-services`, `start-services`, `stop-services`.

## Service boot

| Module | Role |
|--------|------|
| `service_boot.py` | Gradle `bootRun`, health wait, pid/log under `local/.runtime-services/` |
| `service_discovery.py` | Fuzzy repo find, port inference, property + Java scan, session registry |
| `workspace_services.py` | Optional `deploy/tdd/workspace-services.yaml` map |

Bank/HDFC: WireMock only — never bootRun partner APIs.

## Skills

`builder-analyst`, `builder-implementer`, `builder-verifier`, `builder-one-shot` in [`skills/`](../skills/).
