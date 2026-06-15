---
name: builder-verifier
description: >-
  Bob the Builder — verifier: bob validate-ticket, review evidence. Do not change product code to pass.
disable-model-invocation: true
---

# Builder verifier

**Never `git commit` or `git push`.**

**Default proof = E2E only.** When the user asks to validate, test, or prove a ticket, run Bob end-to-end proof — do **not** substitute `gradle test`, Mockito unit tests, or `cc-backend-test-generation` unless they explicitly ask for unit tests.

1. `bob host` if unsure which repo/profile is active
2. `bob validate-ticket <id>` (boots services, WireMock, E2E API+DB scenarios, context pack, eval check, Kafka/Redis verify when configured)
3. Review `REPORT.md`, `REPORT.html`, `GATE_SUMMARY.md`, `CONTEXT_PACK.md`, `evidence/` (`api/`, `db/`, `logs/`, `kafka/`, `redis/`); `EVAL_REGRESSION.md`, `KAFKA_VERIFY.md`, `REDIS_VERIFY.md`, `DB_VERIFY_QUERIES.sql`, `LOG_VERIFY_COMMANDS.md` when present
4. `bob ticket-status <id>` / `bob open-report <id>`; `bob eval check <id>` after intentional REPORT changes

Report PASS/FAIL from E2E evidence only. Opt into Gradle unit proof with `run.unit_tests: true` in `ticket-spec.yaml` when the user requests it.
