---
name: builder-verifier
description: >-
  Bob the Builder — verifier: bob validate-ticket, review evidence. Do not change product code to pass.
disable-model-invocation: true
---

# Builder verifier

**Never `git commit` or `git push`.**

1. `bob host` if unsure which repo/profile is active
2. `bob validate-ticket <id>` (boots services, WireMock, context pack, eval check, Kafka auto when configured)
3. Review `RUN_SUMMARY.md`, `REPORT.html`, `CONTEXT_PACK.md`, `evidence/`; `EVAL_REGRESSION.md` / `KAFKA_VERIFY.md` if present
4. `bob ticket-status <id>` / `bob open-report <id>`; `bob eval check <id>` after intentional REPORT changes

Report PASS/FAIL from evidence only.
