# Novopay skills (canonical)

**Single source of truth** for Novopay agent skills. All copies should point here.

| Skill | Use when |
|-------|----------|
| `ticket-breakdown-planning` | Jira-ready ticket breakdown, estimation, epic vs story judgment |
| `cc-backend-test-generation` | Unit/journey tests for CC backend changes |
| `generate-test-plan-change-flow-based` | QA test plans with API + DB verification matrices |

## Layout

- **Canonical path:** `Desktop/novopay/.cursor/skills/`
- **CC repo:** `novopay-platform-creditcard-management/.cursor/skills` is a **junction** to this folder (same files on disk).

When adding or editing a skill, change files **only here**. Do not maintain a second copy in service repos.
