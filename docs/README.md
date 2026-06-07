# Bob documentation index

Everything below lives under `bob-the-builder/docs/` unless noted.

## Start here

| Doc | Use when |
|-----|----------|
| [BOB_GUIDE.md](BOB_GUIDE.md) | **One doc for everything** - KT, presentation, Cursor vs Bob, full vs minimal TDD, setup, FAQ |
| [KT_CURSOR_AND_BOB.md](KT_CURSOR_AND_BOB.md) | Short pointer → [BOB_GUIDE.md](BOB_GUIDE.md) (legacy bookmark) |
| [ONBOARDING_DEVELOPER.md](ONBOARDING_DEVELOPER.md) | New dev machine setup + `bob onboard` |
| [CURSOR_PLUGINS.md](CURSOR_PLUGINS.md) | Marketplace plugins that pair with Bob workflows (`bob plugins`) |
| [META_REVIEW.md](META_REVIEW.md) | Latest `bob meta-review` output (generated locally; optional in git) |
| [CONTEXT_USAGE_AUDIT.md](CONTEXT_USAGE_AUDIT.md) | Latest `bob context-audit` report (generated locally) |
| [MCP_AUDIT.md](MCP_AUDIT.md) | Latest `bob mcp-audit` report (generated locally) |
| [../README.md](../README.md) | Clone, `bob setup`, daily commands |
| [../assets/examples/sample-validate-output/README.md](../assets/examples/sample-validate-output/README.md) | **See sample outputs** — requirement → generated files (refreshed with engine) |
| [TDD_SYSTEM_DEVELOPER_GUIDE.md](TDD_SYSTEM_DEVELOPER_GUIDE.md) | Full workflow, architecture, FAQ |
| [BOB_CHEATSHEET.md](BOB_CHEATSHEET.md) | Command quick reference |
| [NEXT.md](NEXT.md) | **Bob product** backlog + scorecard (`bob next`) — not host-ticket scope; tickets use `<host>/docs/tdd-runs/<id>/` |

## Workspace and host repo

| Doc | Use when |
|-----|----------|
| [WORKSPACE_AND_HOST_PROFILE.md](WORKSPACE_AND_HOST_PROFILE.md) | `BUILDER_WORKSPACE_ROOT`, `BOB_HOST_REPO`, `bob host`, CC defaults vs other services |
| [ADOPTING_BOB_FOR_ANOTHER_SERVICE.md](ADOPTING_BOB_FOR_ANOTHER_SERVICE.md) | Onboarding a non-CC Novopay service (one shared Bob, no fork) |
| [FRESH_INSTALL_VERIFY.md](FRESH_INSTALL_VERIFY.md) | Prove empty catalog + non-CC `discover-apis` (`bob verify-fresh-install`) |
| [CONTRIBUTING_REFERENCE_PACKS.md](CONTRIBUTING_REFERENCE_PACKS.md) | Optional `assets/examples/<service>/` via branch + PR (after dogfood) |
| [../templates/host-deploy-tdd/README.md](../templates/host-deploy-tdd/README.md) | Copy `deploy/tdd/` into a host repo |

## Validate-ticket and evidence

| Doc | Use when |
|-----|----------|
| [EVIDENCE_AND_VERIFY.md](EVIDENCE_AND_VERIFY.md) | **Master map** — DB / logs / Kafka / Redis verify files + `evidence/` subdirs |
| [DATA_LAYOUT.md](DATA_LAYOUT.md) | Where Bob writes files; git policy |
| [BOB_CONTEXT_AND_EVAL.md](BOB_CONTEXT_AND_EVAL.md) | `CONTEXT_PACK.md`, hybrid graph retrieval, `bob eval` regression |
| [KAFKA_FOR_BOB.md](KAFKA_FOR_BOB.md) | `run.kafka.mode`, `bob kafka discover/setup/up`, `KAFKA_VERIFY.md`, `evidence/kafka/` |
| [REDIS_FOR_BOB.md](REDIS_FOR_BOB.md) | `run.redis.mode`, `REDIS_VERIFY.md`, `evidence/redis/`, `redis_scenarios` |
| [GRAPH_OBSIDIAN.md](GRAPH_OBSIDIAN.md) | `bob graph sync-obsidian`, live graph in Obsidian |

## Architecture diagrams

| Where | What |
|-------|------|
| [TDD_SYSTEM_DEVELOPER_GUIDE.md](TDD_SYSTEM_DEVELOPER_GUIDE.md) | **Mermaid flowchart** (validate-ticket pipeline) — renders on GitHub |
| [GRAPH_OBSIDIAN.md](GRAPH_OBSIDIAN.md) | Live API/processor graph via Obsidian or `graph-overview.mmd` |
| [../runner/ARCHITECTURE.md](../runner/ARCHITECTURE.md) | Module map + links to the above |

## Agents and MCP

| Doc | Use when |
|-----|----------|
| [MCP_TOOL_BRIDGE.md](MCP_TOOL_BRIDGE.md) | Local-first tools with optional MCP backend (`bob tools`, `BOB_TOOL_BACKEND`) |

## Internals

| Doc | Use when |
|-----|----------|
| [../runner/ARCHITECTURE.md](../runner/ARCHITECTURE.md) | Runner modules, service boot |
| [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) | ADR-style decisions |

## Product config (not prose)

| Doc | Role |
|------|------|
| [doc-invariants.yaml](doc-invariants.yaml) | Machine-checked doc contract (`bob verify-docs`) |
| [CONTRACT_GOVERNANCE.md](CONTRACT_GOVERNANCE.md) | Human approval required to weaken contracts (`bob approve-contract-change`) |
| [product-features.yaml](product-features.yaml) | Registered product features (`bob verify-product`) |
| [bob-defaults.yaml](../runner/config/bob-defaults.yaml) | CC/DSA fallbacks when host `deploy/tdd` is missing |
| [host_profile.py](../runner/lib/host_profile.py) | Host profile resolution (used by setup, discover-apis, validate) |
| [novopay-cc reference pack](../assets/examples/novopay-cc/README.md) | Optional CC reference catalog — not auto-loaded |
