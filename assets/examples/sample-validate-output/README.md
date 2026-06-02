# Sample validate-ticket output

This folder is **generated** by `bob refresh-samples` (also runs on `bob verify-product --update` and post-commit).
It shows what Bob produces after a fictional requirement — without needing your machine's services running.

## Requirement → artifacts

| You write | Bob generates (this folder) |
|-----------|---------------------------|
| [REQUIREMENT.md](./REQUIREMENT.md) user story | [ticket-spec.yaml](./ticket-spec.yaml), [TEST_PLAN.md](./TEST_PLAN.md) |
| `bob init-ticket` / analyst fills spec | Same + scenarios, stubs, `run.*` flags |
| `bob validate-ticket <id>` on a **host** repo | [REPORT.md](./REPORT.md), [REPORT.html](./REPORT.html), [run-summary.json](./run-summary.json) |
| (same run) | [CONTEXT_PACK.md](./CONTEXT_PACK.md), [EVAL_REGRESSION.md](./EVAL_REGRESSION.md), [KAFKA_VERIFY.md](./KAFKA_VERIFY.md) |
| (same run) | [DB_VERIFY_QUERIES.sql](./DB_VERIFY_QUERIES.sql), [LOG_VERIFY_COMMANDS.md](./LOG_VERIFY_COMMANDS.md), [evidence/](./evidence/) |

## Regenerate

```bash
cd bob-the-builder
python bob.py refresh-samples
```

_Last generated: 2026-06-03T02:19:22 · Bob 1.1.0 · commit `5dc390a`_

See [docs/README.md](../../docs/README.md) for full documentation.
