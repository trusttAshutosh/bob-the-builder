# Cursor agent skills

Copy or symlink these into your Cursor skills folder, or open `bob-the-builder` as a workspace root in Cursor.

| Skill | Role |
|-------|------|
| `builder-analyst` | ticket-spec, TEST_PLAN, `discover-apis` — no validate, no commit |
| `builder-implementer` | code + unit tests — no validate, no commit unless user asks |
| `builder-verifier` | `validate-ticket`, evidence review — no product code changes |
| `builder-one-shot` | full flow orchestration |

**User habit:** none — agent runs `python bob.py remind --fix` before commit/push in this repo.

**Scoping — two backlogs:**

| Work | What to read |
|------|----------------|
| **Host ticket** (default) | `<host>/docs/tdd-runs/<id>/` — `ticket-spec.yaml`, `TEST_PLAN.md`, `CONTEXT_PACK.md`, `TICKET_RESUME.md`, `GATE_SUMMARY.md` |
| **Bob product** (engine/docs/CI in `bob-the-builder/`) | [`docs/NEXT.md`](../docs/NEXT.md) (`bob next`) |

Guides: [`docs/README.md`](../docs/README.md) (index) · [`docs/EVIDENCE_AND_VERIFY.md`](../docs/EVIDENCE_AND_VERIFY.md) · [`docs/TDD_SYSTEM_DEVELOPER_GUIDE.md`](../docs/TDD_SYSTEM_DEVELOPER_GUIDE.md)
