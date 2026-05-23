# Cursor agent skills

Copy or symlink these into your Cursor skills folder, or open `bob-the-builder` as a workspace root in Cursor.

| Skill | Role |
|-------|------|
| `builder-analyst` | ticket-spec, TEST_PLAN, `discover-apis` — no validate, no commit |
| `builder-implementer` | code + unit tests — no validate, no commit unless user asks |
| `builder-verifier` | `validate-ticket`, evidence review — no product code changes |
| `builder-one-shot` | full flow orchestration |

**User habit:** none — agent runs `python bob.py remind --fix` before commit/push in this repo.

Guide: [`docs/TDD_SYSTEM_DEVELOPER_GUIDE.md`](../docs/TDD_SYSTEM_DEVELOPER_GUIDE.md)
