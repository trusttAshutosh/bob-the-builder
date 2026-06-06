# Onboarding template bundle

Used by `bob onboard` to seed Cursor user files, workspace scaffolding, and the squad Cursor kit.

| Path | Deploy target |
|------|----------------|
| `cursor/novopay-orchestrator.mdc` | `~/.cursor/rules/novopay-orchestrator.mdc` |
| `cursor/hooks.json` | merged into `~/.cursor/hooks.json` (legacy hygiene hooks removed) |
| `cursor/hooks/bob-hook-runner.sh` | `~/.cursor/hooks/bob-hook-runner.sh` (single silent runner) |
| (generated) | `~/.cursor/hooks/.bob-py` (path to `bob.py` on this machine) |
| `novopay/AGENTS.md.stub` | `{WORKSPACE_ROOT}/AGENTS.md` (if missing or `--force`) |
| (generated) | `{WORKSPACE_ROOT}/novopay.code-workspace` |
| `novopay/.cursor/skills/` | `{WORKSPACE_ROOT}/.cursor/skills/` |
| `novopay/.cursor/rules/` | `{WORKSPACE_ROOT}/.cursor/rules/` (includes `memory-budgeting.mdc`) |
| `novopay/.cursor/hooks/` | `{WORKSPACE_ROOT}/.cursor/hooks/` |
| `novopay/.cursor/hooks.json` | `{WORKSPACE_ROOT}/.cursor/hooks.json` |
| `host-cc/.cursor/rules/` | `{WORKSPACE_ROOT}/novopay-platform-creditcard-management/.cursor/rules/` |
| `host-cc/.cursor/hooks/` | `{WORKSPACE_ROOT}/novopay-platform-creditcard-management/.cursor/hooks/` |
| `host-cc/.cursor/hooks.json` | `{WORKSPACE_ROOT}/novopay-platform-creditcard-management/.cursor/hooks.json` |
| (generated) | CC `.cursor/skills` junction -> workspace `.cursor/skills` |

Placeholders substituted at deploy time:

- `{{WORKSPACE_ROOT}}` - absolute workspace path
- `{{WORKSPACE_NAME}}` - last segment of workspace path

Skills in this bundle (canonical squad kit):

| Skill | Purpose |
|-------|---------|
| `ticket-breakdown-planning` | Jira-ready ticket breakdown and estimation |
| `cc-backend-test-generation` | CC backend unit and journey tests |
| `generate-test-plan-change-flow-based` | QA test plans with API + DB matrices |

Bob builder skills (`builder-analyst`, `builder-implementer`, `builder-verifier`, `builder-one-shot`) live in `bob-the-builder/skills/` and are picked up when that repo is in the multi-root workspace.

Cursor marketplace plugins cannot be installed headlessly. `bob onboard` prints a prominent
notice, writes `.cursor/CURSOR_PLUGINS.md` in the workspace, and documents mappings in
`docs/CURSOR_PLUGINS.md`. Re-show anytime: `bob plugins`.

Update this bundle when squad rules or skills change, then teammates run `bob onboard --force`.
