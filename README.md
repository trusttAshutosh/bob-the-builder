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

   `setup` writes `local/user.env` with `BUILDER_WORKSPACE_ROOT`.  
   `install` seeds `assets/` and creates `local/` only inside this repo. Optional: `bob install --launchers` writes `../bob.py` shortcuts in the workspace parent.

3. Optional: copy `skills/builder-*` into your Cursor skills folder or open this repo in Cursor.

4. **Host service glue** (once per service repo): copy [`templates/host-deploy-tdd/`](templates/host-deploy-tdd/README.md) → `your-service/deploy/tdd/`.

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

## Environment

| Variable | Meaning |
|----------|---------|
| `BUILDER_WORKSPACE_ROOT` | Parent folder containing service clones + this repo |
| `BOB_HOME` | Override for `assets/` (default: `./assets`) |
| `BOB_LOCAL` | Override for `local/` |
| `BOB_HOST_REPO` | Force active service repo (else inferred from `cwd`) |

## Docs

- [docs/NEXT.md](docs/NEXT.md) — **living improvement backlog + scorecard** (`bob next`, `bob verify-product --update`)
- [docs/DATA_LAYOUT.md](docs/DATA_LAYOUT.md) — where files go; **Bob never commits or pushes**
- [docs/TDD_SYSTEM_DEVELOPER_GUIDE.md](docs/TDD_SYSTEM_DEVELOPER_GUIDE.md)
- [docs/BOB_CHEATSHEET.md](docs/BOB_CHEATSHEET.md)
- [runner/ARCHITECTURE.md](runner/ARCHITECTURE.md)
