# Bob the Builder

Ticket-driven local TDD for backend services: **Bob proves** work from `ticket-spec.yaml`; **Cursor** (the IDE agent) plans and implements. This repo ships the Bob CLI, evidence tooling, and optional Cursor `builder-*` skill playbooks.

**This is the only repository for Bob.** Service repos (e.g. credit-card-management) do not ship the engine — they only hold ticket folders and host-specific deploy config.

**Clone:**

```bash
git clone https://github.com/trusttAshutosh/bob-the-builder.git
```

## Cursor vs Bob

Bob is **not** a second AI and does **not** write Java. It is a **CLI + ticket layout** for standardized local proof. Cursor is the agent that thinks, drafts specs, and writes code.

| | **Cursor** (IDE + agent) | **Bob** (`bob.py` CLI) |
|---|--------------------------|-------------------------|
| **Role** | Plan, implement, review in chat | Run `validate-ticket` and write evidence |
| **Typical work** | Raw requirement → `ticket-spec.yaml`, `TEST_PLAN.md`, Java/tests | Boot services + WireMock, hit APIs, DB/log/Kafka/Redis checks |
| **Skills** | Workspace skills + optional `builder-analyst`, `builder-implementer`, `builder-verifier` (playbooks for the agent - not auto-on) | Commands: `init-ticket`, `discover-apis`, `validate-ticket`, … |
| **Output** | Code, unit tests, ticket docs under `<host>/docs/tdd-runs/<id>/` | `REPORT.md`, `GATE_SUMMARY.md`, `evidence/` |

### Was Bob required if Cursor is enough?

| Need | Cursor alone | Bob |
|------|--------------|-----|
| Understand requirement, write Java | Yes | No |
| Unit tests (`gradle test`) | Yes (when you ask) | Opt-in via `run.unit_tests: true`; default proof is E2E |
| WireMock bank APIs in a repeatable run | Painful / manual | **Core Bob** |
| Boot CC + peers + same proof every time | Manual | **Core Bob** |
| `REPORT.md` / `GATE_SUMMARY` for the squad | No standard | **Core Bob** |

Bob was not redundant for bank mimicry + standardized local proof. It was never meant to replace thinking and coding - that was always Cursor (+ you).

### Full Bob TDD vs minimal Bob

**Full Bob TDD** (recommended for non-trivial tickets):

```text
raw thoughts → (Cursor) ticket-spec + TEST_PLAN → (Cursor) code + unit tests
             → (Bob) validate-ticket → evidence/ → (you) GATE_SUMMARY gates → ship
```

**Minimal Bob** (also valid): implement in Cursor, then `bob validate-ticket <id>` when you want proof. You still need a ticket folder/spec for Bob to run scenarios; code-first without a spec means less automated proof until someone fills `ticket-spec.yaml`.

Saying **"bob"** in chat does not switch modes automatically. Explicit commands work best: *"plan only: init adhoc-foo, no code"* or *"bob validate-ticket adhoc-foo"*.

**Team guide (one doc - KT / presentation):** [docs/BOB_GUIDE.md](docs/BOB_GUIDE.md)

## Layout

```text
bob-the-builder/
  bob.py              # CLI entry
  runner/             # engine (Python + shell)
  assets/             # shared catalogs (api, stubs, platform graph) — starts empty
  assets/examples/    # reference packs + sample validate-ticket output bundle
  local/              # gitignored — user.env, agent session, WireMock
  skills/             # Cursor builder-* skills (copy or symlink into ~/.cursor)
  docs/               # developer guide, cheatsheet
```

## Squad setup (Cursor + Bob)

One command after clone. Everything squad-owned is in `templates/onboarding/` and deploys via `bob onboard`.

### Prerequisites

| Tool | Notes |
|------|-------|
| **Git** | Clone repos below |
| **Python 3** | Runs `bob.py` |
| **JDK 21** | Gradle `bootRun` during `validate-ticket` |
| **MySQL** | Local; default creds `root` / `root` (prompted in onboard) |
| **Cursor 2.5+** | IDE + agent |

### 1. Clone under one parent folder

```bash
mkdir -p ~/Desktop/novopay && cd ~/Desktop/novopay
git clone https://github.com/trusttAshutosh/bob-the-builder.git
# clone your host service repo(s) alongside Bob (CC example below)
```

Example layout (adjust drive/path; onboard asks you to confirm the parent):

```text
Desktop/novopay/                          <- workspace root (BUILDER_WORKSPACE_ROOT)
  bob-the-builder/
  novopay-platform-creditcard-management/   <- host service (CC)
  novopay-platform-lib/                     <- composite build from CC
  novopay-platform-api-gateway/             <- optional peer
  novopay-platform-actor/                   <- optional peer
```

Open the multi-root workspace after onboard: `novopay.code-workspace` (created at workspace root).

**Host service glue** (optional): copy [`templates/host-deploy-tdd/`](templates/host-deploy-tdd/README.md) into CC `deploy/tdd/`. Bob can also discover and boot peers without it - see [Service boot](#service-boot-dynamic-peers).

### 2. One command

```bash
cd bob-the-builder
python bob.py onboard
```

Answer prompts once: **workspace root** (parent of clones), MySQL host/user/password, service base URLs (defaults from `deploy/tdd` when CC is cloned).

Flags teammates often use:

| Flag | When |
|------|------|
| `--yes` | Skip the final "apply changes?" prompt |
| `--smoke` | Run sample `validate-ticket` at the end |
| `--force --skip-setup` | Refresh squad skills/rules after template updates in git |

You do **not** run `bob setup` + `bob install` separately on first use - `onboard` runs both.

### 3. What `bob onboard` creates

| Artifact | Path |
|----------|------|
| Agent memory stub | `{workspace}/AGENTS.md` |
| Squad skills (3) | `{workspace}/.cursor/skills/` |
| Squad workspace rules | `{workspace}/.cursor/rules/` |
| CC rules + test hooks | `{workspace}/novopay-platform-creditcard-management/.cursor/` |
| CC skills junction | CC `.cursor/skills` -> workspace `.cursor/skills` |
| Multi-root workspace | `{workspace}/novopay.code-workspace` |
| Orchestrator rule (always on) | `~/.cursor/rules/novopay-orchestrator.mdc` |
| Bob lifecycle hooks | merged into `~/.cursor/hooks.json` |
| Bob prefs | `bob-the-builder/local/user.env` (`BUILDER_WORKSPACE_ROOT`, MySQL, `{SERVICE}_BASE`) |
| Plugin checklist | `{workspace}/.cursor/CURSOR_PLUGINS.md` + `bob plugins` |

Skills deployed: `ticket-breakdown-planning`, `cc-backend-test-generation`, `generate-test-plan-change-flow-based`.

Bob builder skills (`builder-analyst`, `builder-implementer`, `builder-verifier`, `builder-one-shot`) load from `bob-the-builder/skills/` when that repo is in the workspace - no extra copy step.

### 4. Cursor plugins (built into onboard)

`bob onboard` runs the same step as `bob plugins` after opening the workspace:

- Writes `docs/CURSOR_PLUGINS.md` and `{workspace}/.cursor/CURSOR_PLUGINS.md`
- Shows OK/MISSING for Superpowers, Team Kit, Continual Learning
- Prints the install guide (marketplace search terms)
- Waits for Enter so you can install missing plugins in Cursor (skip wait: `--yes` or `--skip-plugin-pause`)

Bob still cannot click Install for you - Cursor has no headless marketplace API. Re-check anytime: `bob plugins`.

Optional: `python bob.py prune-overhead --apply` then reload Cursor (MCP/plugin policy for Novopay backend work).

### 5. Verify

```bash
python bob.py memory-budget
python bob.py validate-ticket sample-gateway-health-check
```

`memory-budget` writes `docs/MEMORY_BUDGET.md` and refreshes `{workspace}/.cursor/memory-budget-status.json` (also on each Cursor session start).

Read [docs/BOB_GUIDE.md](docs/BOB_GUIDE.md) for the 4-gate workflow (Plan / Build / Prove / Ship) and team KT.

### Power-user commands (not first-time)

| Command | Use |
|---------|-----|
| `bob setup` | Reconfigure workspace root, MySQL, service URLs |
| `bob install` | Re-seed assets or reinstall git hooks |
| `bob onboard --force` | Overwrite existing Cursor rules / AGENTS.md / skills (after template updates in git) |

More detail: [docs/ONBOARDING_DEVELOPER.md](docs/ONBOARDING_DEVELOPER.md).

## Daily use (any service repo)

The **first** Bob command adds `local/bin` to your user PATH (once per machine). After that, open a new terminal and use `bob` from anywhere.

```bash
cd novopay-platform-creditcard-management
bob init-ticket MY-123 "Short title"
bob discover-apis
bob validate-ticket MY-123
```

Until then: `python bob.py <command>` from `bob-the-builder/`.

Tickets and evidence live in the **host** repo: `docs/tdd-runs/<ticket-id>/` (API, DB, logs, **Kafka**, **Redis** under `evidence/`; see [docs/EVIDENCE_AND_VERIFY.md](docs/EVIDENCE_AND_VERIFY.md)).

**Other Novopay services:** Bob is not CC-only — point `BOB_HOST_REPO` at your service and copy `templates/host-deploy-tdd/`. See [docs/ADOPTING_BOB_FOR_ANOTHER_SERVICE.md](docs/ADOPTING_BOB_FOR_ANOTHER_SERVICE.md).

## Service boot (dynamic peers)

Bob can **`gradlew bootRun` Novopay microservices** when a ticket or agent session needs them — **no** `deploy/tdd/workspace-services.yaml` entry required.

| Command | Purpose |
|---------|---------|
| `bob ensure-peers` | Scan host code + properties; boot peers not already healthy |
| `bob need-service NAME` | Register + boot one repo by hint (`notifications`, `consents`, …) |
| `bob discover-services` | List discovered peers; `--boot` to start all |
| `bob start-services` | Boot from env profile / ticket spec |
| `bob services-status` | Health + pid for profile services |
| `bob stop-services` | Stop Bob-started bootRun processes |

Bank/HDFC partner APIs stay on **WireMock** — never bootRun the real bank.

`validate-ticket` auto-boots when `run.auto_boot_services: true` (default) and discovers peers when `run.auto_discover_services: true` (default). Session registry: `local/agent/required-services.yaml`.

## Environment

| Variable | Meaning |
|----------|---------|
| `BUILDER_WORKSPACE_ROOT` | Parent folder containing service clones + this repo |
| `BOB_HOME` | Override for `assets/` (default: `./assets`) |
| `BOB_LOCAL` | Override for `local/` |
| `BOB_HOST_REPO` | Force active service repo (else inferred from `cwd`) |

Run `bob host` to print resolved host, workspace clones, and `deploy/tdd` profile.

## Docs

Full index: [docs/README.md](docs/README.md).  
**See what Bob generates:** [assets/examples/sample-validate-output/](assets/examples/sample-validate-output/README.md) (refreshed via `bob refresh-samples`).

- [docs/BOB_GUIDE.md](docs/BOB_GUIDE.md) — team guide (KT / presentation)
- [docs/TDD_SYSTEM_DEVELOPER_GUIDE.md](docs/TDD_SYSTEM_DEVELOPER_GUIDE.md) — deep technical guide + architecture
- [docs/BOB_CHEATSHEET.md](docs/BOB_CHEATSHEET.md) — commands
- [docs/WORKSPACE_AND_HOST_PROFILE.md](docs/WORKSPACE_AND_HOST_PROFILE.md) — multi-repo workspace + CC defaults
- [docs/ADOPTING_BOB_FOR_ANOTHER_SERVICE.md](docs/ADOPTING_BOB_FOR_ANOTHER_SERVICE.md) — other Novopay services
- [docs/FRESH_INSTALL_VERIFY.md](docs/FRESH_INSTALL_VERIFY.md) — empty catalog + non-CC discover proof (`bob verify-fresh-install`)
- [docs/CONTRIBUTING_REFERENCE_PACKS.md](docs/CONTRIBUTING_REFERENCE_PACKS.md) — optional `assets/examples/` via branch + PR
- [docs/BOB_CONTEXT_AND_EVAL.md](docs/BOB_CONTEXT_AND_EVAL.md) — context pack + eval regression
- [docs/EVIDENCE_AND_VERIFY.md](docs/EVIDENCE_AND_VERIFY.md) — DB / logs / Kafka / Redis verify docs + `evidence/`
- [docs/KAFKA_FOR_BOB.md](docs/KAFKA_FOR_BOB.md) — Kafka discover / verify / `evidence/kafka/`
- [docs/REDIS_FOR_BOB.md](docs/REDIS_FOR_BOB.md) — Redis verify / `evidence/redis/`
- [docs/MCP_TOOL_BRIDGE.md](docs/MCP_TOOL_BRIDGE.md) — optional MCP backend for tools (`BOB_TOOL_BACKEND=local` default)
- [docs/GRAPH_OBSIDIAN.md](docs/GRAPH_OBSIDIAN.md) — Obsidian graph export
- [docs/DATA_LAYOUT.md](docs/DATA_LAYOUT.md) — paths; **Bob never commits or pushes**
- [docs/doc-invariants.yaml](docs/doc-invariants.yaml) — doc contract checked by `bob verify-docs`
- [docs/NEXT.md](docs/NEXT.md) — **Bob product** backlog + scorecard (`bob next`; not host-ticket scope)
- [runner/ARCHITECTURE.md](runner/ARCHITECTURE.md) — runner internals
- **Architecture diagram:** mermaid in [docs/TDD_SYSTEM_DEVELOPER_GUIDE.md](docs/TDD_SYSTEM_DEVELOPER_GUIDE.md#architecture-end-to-end); live graph via [docs/GRAPH_OBSIDIAN.md](docs/GRAPH_OBSIDIAN.md)
