# Bob the Builder — runner

Ticket-driven local validation: `ticket-spec.yaml` → `validate-ticket` → evidence.

## Quick start

```bash
pip install pyyaml
cd bob-the-builder
python bob.py setup
python bob.py install
python bob.py init-ticket MY-123 "Title"
python bob.py discover-apis
python bob.py validate-ticket MY-123
```

Prefs: `BOB_LOCAL/user.env` (`BUILDER_WORKSPACE_ROOT`, MySQL, URLs).  
Catalogs: `BOB_HOME` (`bob-the-builder/assets/` after `bob install`).

## Commands

Run `python bob.py help`.

| Command | Purpose |
|---------|---------|
| `setup` | Workspace root + MySQL + URLs |
| `install` | Seed `assets/` + `local/` under this repo |
| `init-ticket` | New ticket folder in host repo |
| `discover-apis` | API catalog from orchestration |
| `sync-graph` | Platform graph |
| `validate-ticket` | Run + evidence |
| `ticket-status` | Last run summary |
| `open-report` | Paths to reports |
| `ensure-peers` | Dynamic peer scan + bootRun |
| `need-service` | Boot one peer by repo hint |
| `discover-services` | List peers; `--boot` to start |
| `start-services` | Boot from env profile |
| `services-status` | Health + pid |
| `stop-services` | Stop Bob-started bootRun |
| `host` | Resolved `BOB_HOST_REPO` + deploy/tdd profile |
| `context --ticket ID` | `CONTEXT_PACK.md` for agents |
| `eval baseline\|check\|update` | REPORT regression |
| `kafka …` | Discover / Docker / verify (see docs/KAFKA_FOR_BOB.md) |
| `graph sync-obsidian` | Obsidian vault export |

Docs index: [`../docs/README.md`](../docs/README.md).

## Skills

Copy or symlink from [`../skills/`](../skills/): `builder-analyst`, `builder-implementer`, `builder-verifier`, `builder-one-shot`.

Guide: [`../docs/TDD_SYSTEM_DEVELOPER_GUIDE.md`](../docs/TDD_SYSTEM_DEVELOPER_GUIDE.md)
