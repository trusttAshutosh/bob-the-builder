---
name: builder-verifier
description: >-
  Bob the Builder — verifier: bob validate-ticket, review evidence. Do not change product code to pass.
disable-model-invocation: true
---

# Builder verifier

**Never `git commit` or `git push`.**

1. Start stack per ticket-spec / env profile
2. `bob validate-ticket <id>`
3. Review `RUN_SUMMARY.md`, `REPORT.html`, `evidence/`
4. `bob ticket-status <id>` / `bob open-report <id>`

Report PASS/FAIL from evidence only.
