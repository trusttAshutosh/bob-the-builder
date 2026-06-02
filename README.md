# Bob the Builder

Ticket-driven local TDD for backend services: ticket specs, API discovery, validation, evidence, and Cursor agent skills.

**This is the only repository for Bob.** Service repos (e.g. credit-card-management) do not ship the engine — they only hold ticket folders and host-specific deploy config.

## Layout

```text
bob-the-builder/
  bob.py              # CLI entry
  runner/             # engine (Python + shell)
  assets/             # shared catalogs (api, stubs, platform graph) — starts empty
  assets/examples/    # reference packs only (e.g. novopay-cc)
  local/              # gitignored — user.env, agent session, WireMock
  skills/             # Cursor builder-* skills (copy or symlink into ~/.cursor)
  docs/               # developer guide, cheatsheet
```

## One-time setup

1. Clone this repo next to your service git clones:

   ```text
   your-workspace/
     bob-the-builder/          # this repo
     novopay-platform-*/       # service repos
   ```

2. From `bob-the-builder/`:

   ```bash
   python bob.py setup
   python bob.py install
   ```

   `setup` writes `local/user.env` with `BUILDER_WORKSPACE_ROOT` and service URLs from host `deploy/tdd` when present (`CC_BASE`, `MD_BASE`, …).  
   `install` seeds `assets/` and installs a **post-commit hook** that auto-refreshes `docs/NEXT.md` after each git commit. Optional: `bob install --launchers` writes `../bob.py` shortcuts in the workspace parent.

3. Optional: copy `skills/builder-*` into your Cursor skills folder or open this repo in Cursor.

4. **Host service glue** (optional but recommended): copy [`templates/host-deploy-tdd/`](templates/host-deploy-tdd/README.md) → `your-service/deploy/tdd/`. Bob can also **discover and boot peer services without this** — see [Service boot](#service-boot-dynamic-peers) below.

## Daily use (any service repo)

The **first** Bob command adds `local/bin` to your user PATH (once per machine). After that, open a new terminal and use `bob` from anywhere.

```bash
cd novopay-platform-creditcard-management
bob init-ticket MY-123 "Short title"
bob discover-apis
bob validate-ticket MY-123
```

Until then: `python bob.py <command>` from `bob-the-builder/`.

Tickets and evidence live in the **host** repo: `docs/tdd-runs/<ticket-id>/`.

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

- [docs/TDD_SYSTEM_DEVELOPER_GUIDE.md](docs/TDD_SYSTEM_DEVELOPER_GUIDE.md) — main guide
- [docs/BOB_CHEATSHEET.md](docs/BOB_CHEATSHEET.md) — commands
- [docs/WORKSPACE_AND_HOST_PROFILE.md](docs/WORKSPACE_AND_HOST_PROFILE.md) — multi-repo workspace + CC defaults
- [docs/ADOPTING_BOB_FOR_ANOTHER_SERVICE.md](docs/ADOPTING_BOB_FOR_ANOTHER_SERVICE.md) — other Novopay services
- [docs/BOB_CONTEXT_AND_EVAL.md](docs/BOB_CONTEXT_AND_EVAL.md) — context pack + eval regression
- [docs/KAFKA_FOR_BOB.md](docs/KAFKA_FOR_BOB.md) — Kafka discover / verify
- [docs/GRAPH_OBSIDIAN.md](docs/GRAPH_OBSIDIAN.md) — Obsidian graph export
- [docs/DATA_LAYOUT.md](docs/DATA_LAYOUT.md) — paths; **Bob never commits or pushes**
- [docs/NEXT.md](docs/NEXT.md) — backlog + scorecard (`bob next`)
- [runner/ARCHITECTURE.md](runner/ARCHITECTURE.md) — runner internals
