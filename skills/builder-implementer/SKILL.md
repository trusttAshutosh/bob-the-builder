---
name: builder-implementer
description: >-
  Bob the Builder — implementer: code + unit tests from ticket-spec. No validate-ticket, no commit unless asked.
disable-model-invocation: true
---

# Builder implementer

1. Read `docs/tdd-runs/<id>/ticket-spec.yaml`; when resuming, also `TICKET_RESUME.md` and `GATE_SUMMARY.md` for gate status
2. Feature branch per team policy
3. Code in repos under `BUILDER_WORKSPACE_ROOT`
4. If a peer service is needed (notifications, consents, masterdata, …): `bob ensure-peers` or `bob need-service <hint>` — no `deploy/tdd` entry required
5. Unit tests per `scenarios[].gradle_tests` when `verification_level: unit`
6. If ticket-spec lists `evidence_required: kafka` or `redis`, implement against stubs/masterdata Bob primes — verifier will check `KAFKA_VERIFY.md` / `REDIS_VERIFY.md` and `evidence/kafka/` / `evidence/redis/`

**Never `git commit` or `git push`** — Bob does not use git for publishing.
