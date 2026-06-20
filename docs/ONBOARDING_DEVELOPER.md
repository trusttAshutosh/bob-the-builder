# Developer onboarding (Cursor + Bob)

Goal: clone Novopay layout → working `bob validate-ticket` with **one command**.

## Teammate quick start

```bash
# 1. Clone under one parent (e.g. Desktop/novopay):
#    bob-the-builder, novopay-platform-creditcard-management, novopay-platform-lib, ...

cd bob-the-builder
python bob.py onboard
```

Answer the setup prompts once (workspace root, MySQL). Bob then installs itself, deploys the squad Cursor kit, and writes **`{workspace}/AGENTS.md`** at the centralized root you chose.

Install Cursor plugins manually when the banner appears (`bob plugins`).

You do **not** need separate `bob setup` + `bob install` on first run - `onboard` runs both.

---

## Today (manual, ~30-60 min) - legacy only

1. **Clone repos** under one parent (e.g. `Desktop/novopay`):
   - `bob-the-builder`
   - `novopay-platform-creditcard-management` (or your host service)
   - `novopay-platform-lib` (if host uses composite build)
2. **Cursor**
   - Install recommended plugins (Superpowers, Team Kit, Continual Learning)
   - Copy squad template: `novopay-orchestrator.mdc` → `~/.cursor/rules/`
   - Open `novopay.code-workspace` (in novopay parent) or `Desktop/novopay`
3. **Bob**
   ```bash
   cd bob-the-builder
   python bob.py setup
   python bob.py install
   python bob.py install --launchers   # optional workspace bob.py shortcut
   ```
4. **Smoke**
   ```bash
   python bob.py validate-ticket sample-gateway-health-check
   # or a real ticket id under host docs/tdd-runs/
   ```
5. **Read** [BOB_GUIDE.md](BOB_GUIDE.md) (team KT - one doc)

---

## `bob onboard` (one approve)

Single command after clone:

```bash
cd bob-the-builder
python bob.py onboard [--dry-run] [--yes] [--smoke]
```

**Flags:**

| Flag | Effect |
|------|--------|
| `--dry-run` | Print prerequisite check + planned file actions only |
| `--yes` / `-y` | Skip the final "apply changes?" prompt |
| `--skip-setup` | Use existing `user.env` prefs |
| `--reconfigure` | Force interactive `bob setup` |
| `--force` / `-f` | Overwrite existing Cursor rule / AGENTS.md / workspace file |
| `--no-launchers` | Skip workspace `bob.py` shortcut |
| `--skip-cursor-open` | Do not run `cursor novopay.code-workspace` |
| `--skip-plugins` | Skip integrated `bob plugins` step (verify + install guide) |
| `--skip-plugin-pause` | Do not wait for Enter after plugin install prompt |
| `--smoke` | Run `validate-ticket sample-gateway-health-check` after bootstrap |
| `--skip-smoke` | Skip smoke prompt |

**Steps (automated where safe):**

| Step | Action | Needs human approve? |
|------|--------|----------------------|
| 1 | Verify JDK, Python, Git, MySQL client | No |
| 2 | Run `bob setup` with detected workspace root | Yes (confirm path + DB password) |
| 3 | Run `bob install` + hooks | No |
| 4 | Copy template files from `templates/onboarding/` | Yes (unless `--yes`) |
| 5 | Cursor: write `~/.cursor/rules/novopay-orchestrator.mdc` | Yes (unless `--yes` / `--force`) |
| 6 | Cursor: deploy workspace kit (skills, rules, hooks) under `{workspace}/.cursor/` | Yes (unless `--yes`; skip existing files unless `--force`) |
| 7 | Cursor: deploy CC overlay + skills junction (when CC repo cloned) | Yes (unless `--yes`; junction needs `--force` if real dir exists) |
| 8 | Cursor plugins: integrated `bob plugins` (status + install guide; opens Cursor first) | Manual marketplace clicks; optional Enter pause |
| 9 | Write `novopay.code-workspace` to workspace root if missing | No |
| 10 | Smoke `validate-ticket` on sample ticket | Yes (unless `--smoke` or prompt declined) |

**Cannot fully automate (IDE limits):**

- Installing Cursor plugins (user clicks in marketplace) - Bob prints a banner and writes [CURSOR_PLUGINS.md](CURSOR_PLUGINS.md); re-show with `bob plugins`
- Opening workspace in Cursor (`bob onboard` tries `cursor novopay.code-workspace` when available)

**Template bundle:** `bob-the-builder/templates/onboarding/` (see `README.onboarding.md`). Includes workspace skills, rules, CC overlay, and junction setup. Refresh a machine with `bob onboard --force` after squad kit updates.

---

## Continuous usage evaluation

Meta loop (squad-level, not per-developer):

| Cadence | Job | Output |
|---------|-----|--------|
| Weekly | `workflow-from-chats` + **Bob product** [`NEXT.md`](NEXT.md) review (squad maintainers — not per-ticket scope) | `AGENTS.md` updates, hygiene PR |
| Session start | `bob chat-hygiene --auto --hook session` | Archive stale/overflow chats (never delete) |
| Weekly stop | `bob chat-hygiene --hook stop --learn` | Learn reminder + archive nudge |
| Monthly stop hook | `bob meta-review --hook stop` (auto when 30d due) | [META_REVIEW.md](META_REVIEW.md) + [CONTEXT_USAGE_AUDIT.md](CONTEXT_USAGE_AUDIT.md) - human approves changes |
| Monthly manual | `bob meta-review` | Same reports on demand |
| Per release | `bob verify-all` + scorecard | [NEXT.md](NEXT.md) **product** grades; [doc-invariants.yaml](doc-invariants.yaml) via `verify-docs` |

### `bob meta-review`

```bash
python bob.py meta-review              # write docs/META_REVIEW.md + CONTEXT_USAGE_AUDIT.md
python bob.py meta-review --dry-run    # preview only
python bob.py meta-review --days 14    # chat keyword window
python bob.py meta-review --hook stop  # stop hook: auto-run when 30d since last run
python bob.py meta-review --hook stop --interval-days 30  # override cadence (testing)
```

**Scans (local only):**

- Bob: ticket pass rates, boot/health failure patterns, open NEXT.md items
- Cursor: orchestrator rule drift vs onboarding template, hooks, duplicate skills
- Plugins: weak cache-dir signals + `bob plugins` pointer
- Chats: parent transcript keyword counts (no message content stored)
- Context: `contextUsagePercent` per chat from Cursor `state.vscdb` + transcript inventory -> [CONTEXT_USAGE_AUDIT.md](CONTEXT_USAGE_AUDIT.md)
- MCP/plugins: local `~/.cursor` scan -> [MCP_AUDIT.md](MCP_AUDIT.md)

Emits **suggestions only**; human approves changes to rules/skills/Bob. Re-run monthly; apply changes manually or `bob onboard --force` for orchestrator rule sync only.

### `bob context-audit`

```bash
python bob.py context-audit              # write docs/CONTEXT_USAGE_AUDIT.md
python bob.py context-audit --dry-run    # preview only
```

Reads Cursor `composer.composerHeaders` for last-known `contextUsagePercent` on active, archived, and deleted-header chats; cross-checks `.cursor/projects/*/agent-transcripts`. Per-category Context panel breakdown (System prompt, Tools, Rules) is runtime-only and not stored historically.

### `bob mcp-audit` / `bob prune-overhead`

```bash
python bob.py mcp-audit                  # audit this machine -> docs/MCP_AUDIT.md
python bob.py mcp-audit --json           # machine-readable summary
python bob.py prune-overhead --apply     # apply Bob squad keep/disable policy
```

Bob does **not** run MCP servers or replace Cursor. It reads local `~/.cursor` state on **any** machine where Bob is installed, prints keep/disable recommendations for Novopay backend work, and optionally applies them. Reload Cursor after `prune-overhead --apply`.

Cursor lifecycle hooks use one silent runner: `~/.cursor/hooks/bob-hook-runner.py` (invoked via `pythonw` on Windows so no console flashes; logic in `bob cursor-hook`). Re-install via `bob onboard`.

### `bob chat-hygiene`

```bash
python bob.py chat-hygiene --dry-run     # preview archive targets
python bob.py chat-hygiene --auto        # archive stale (7d+) + cap overflow (max 8 active)
python bob.py chat-hygiene --max-active 6 --stale-days 7
```

Never deletes chats - sets `isArchived: true` in Cursor `state.vscdb` only. If Cursor is running, it may overwrite DB writes; quit Cursor for manual bulk archive, or use the sessionStart hook on next launch.

---

## Onboarding checklist (printable)

- [ ] Repos cloned under one workspace root
- [ ] `bob setup` completed
- [ ] `bob install` completed
- [ ] Sample or real `validate-ticket` PASS once
- [ ] Cursor workspace opened (`novopay.code-workspace`)
- [ ] `novopay-orchestrator.mdc` in user rules
- [ ] Read BOB_GUIDE + GATE_SUMMARY on one real ticket
- [ ] Know: archive chats, don't delete unless noise
