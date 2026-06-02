# Bob documentation index

Everything below lives under `bob-the-builder/docs/` unless noted.

## Start here

| Doc | Use when |
|-----|----------|
| [../README.md](../README.md) | Clone, `bob setup`, daily commands |
| [TDD_SYSTEM_DEVELOPER_GUIDE.md](TDD_SYSTEM_DEVELOPER_GUIDE.md) | Full workflow, architecture, FAQ |
| [BOB_CHEATSHEET.md](BOB_CHEATSHEET.md) | Command quick reference |
| [NEXT.md](NEXT.md) | Improvement backlog + scorecard (`bob next`) |

## Workspace and host repo

| Doc | Use when |
|-----|----------|
| [WORKSPACE_AND_HOST_PROFILE.md](WORKSPACE_AND_HOST_PROFILE.md) | `BUILDER_WORKSPACE_ROOT`, `BOB_HOST_REPO`, `bob host`, CC defaults vs other services |
| [ADOPTING_BOB_FOR_ANOTHER_SERVICE.md](ADOPTING_BOB_FOR_ANOTHER_SERVICE.md) | Onboarding a non-CC Novopay service (one shared Bob, no fork) |
| [../templates/host-deploy-tdd/README.md](../templates/host-deploy-tdd/README.md) | Copy `deploy/tdd/` into a host repo |

## Validate-ticket and evidence

| Doc | Use when |
|-----|----------|
| [DATA_LAYOUT.md](DATA_LAYOUT.md) | Where Bob writes files; git policy |
| [BOB_CONTEXT_AND_EVAL.md](BOB_CONTEXT_AND_EVAL.md) | `CONTEXT_PACK.md`, hybrid graph retrieval, `bob eval` regression |
| [KAFKA_FOR_BOB.md](KAFKA_FOR_BOB.md) | `run.kafka.mode`, `bob kafka discover/setup/up`, `KAFKA_VERIFY.md` |
| [GRAPH_OBSIDIAN.md](GRAPH_OBSIDIAN.md) | `bob graph sync-obsidian`, live graph in Obsidian |

## Internals

| Doc | Use when |
|-----|----------|
| [../runner/ARCHITECTURE.md](../runner/ARCHITECTURE.md) | Runner modules, service boot |
| [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) | ADR-style decisions |

## Product config (not prose)

| Path | Role |
|------|------|
| `runner/config/bob-defaults.yaml` | CC/DSA fallbacks when host `deploy/tdd` is missing |
| `runner/lib/host_profile.py` | Host profile resolution (used by setup, discover-apis, validate) |
| `assets/examples/novopay-cc/` | Optional CC reference catalog — not auto-loaded |
