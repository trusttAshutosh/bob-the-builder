# Onboarding template bundle

Used by `bob onboard` to seed Cursor user files and workspace scaffolding.

| Path | Deploy target |
|------|----------------|
| `cursor/novopay-orchestrator.mdc` | `~/.cursor/rules/novopay-orchestrator.mdc` |
| `cursor/hooks.json` | merged into `~/.cursor/hooks.json` (legacy hygiene hooks removed) |
| `cursor/hooks/bob-hook-runner.sh` | `~/.cursor/hooks/bob-hook-runner.sh` (single silent runner) |
| (generated) | `~/.cursor/hooks/.bob-py` (path to `bob.py` on this machine) |
| `novopay/AGENTS.md.stub` | `{WORKSPACE_ROOT}/AGENTS.md` (if missing) |
| (generated) | `{WORKSPACE_ROOT}/novopay.code-workspace` |

Placeholders substituted at deploy time:

- `{{WORKSPACE_ROOT}}` — absolute workspace path
- `{{WORKSPACE_NAME}}` — last segment of workspace path

Cursor marketplace plugins cannot be installed headlessly. `bob onboard` prints a prominent
notice, writes `.cursor/CURSOR_PLUGINS.md` in the workspace, and documents mappings in
`docs/CURSOR_PLUGINS.md`. Re-show anytime: `bob plugins`.
