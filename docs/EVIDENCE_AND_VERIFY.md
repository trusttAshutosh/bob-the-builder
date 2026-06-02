# Evidence and verification (validate-ticket)

Every `bob validate-ticket` run can produce **human verification docs** (copy-paste commands) and **machine evidence** (files under `evidence/`). This matches how DB and logs already work; **Kafka** and **Redis** follow the same pattern.

## Quick map

| Kind | Verification doc (commands) | Evidence folder | When Bob runs |
|------|---------------------------|-----------------|---------------|
| **DB** | `DB_VERIFY_QUERIES.sql` | `evidence/db/` | E2E scenarios with `db.expect` or `transaction_audit` in `evidence_required` |
| **Logs** | `LOG_VERIFY_COMMANDS.md` | `evidence/logs/` (+ root `log-search.txt`) | E2E/integration scenarios; search if `LOGS_DIR` set |
| **Kafka** | `KAFKA_VERIFY.md` | `evidence/kafka/` | `run.kafka.mode` auto/on or `kafka_scenarios`; see [KAFKA_FOR_BOB.md](KAFKA_FOR_BOB.md) |
| **Redis** | `REDIS_VERIFY.md` | `evidence/redis/` | `run.redis.mode` auto/on, `evidence_required: redis`, or `masterdata[]`/stubs; see [REDIS_FOR_BOB.md](REDIS_FOR_BOB.md) |
| **API** | (in `REPORT.md`) | `evidence/api/` | Gateway steps executed |
| **Unit** | (in `REPORT.md`) | `evidence/unit/` | `verification_level: unit` |

## Host ticket folder (typical)

```text
docs/tdd-runs/<ticket-id>/
  ticket-spec.yaml
  TEST_PLAN.md
  REPORT.md              # single human report (decision trace, scenarios)
  REPORT.html
  run-summary.json
  CONTEXT_PACK.md
  EVAL_REGRESSION.md
  eval-baseline.json
  DB_VERIFY_QUERIES.sql
  LOG_VERIFY_COMMANDS.md
  KAFKA_VERIFY.md        # when Kafka in scope
  REDIS_VERIFY.md        # when Redis in scope
  kafka-discovered.json
  execution-summary.txt
  log-search.txt         # when LOGS_DIR set
  evidence/
    api/
    db/
    logs/
    kafka/               # JSONL/JSON captures
    redis/               # key snapshots (capture-*.json)
    unit/
  postman/               # optional export
```

Legacy: `RUN_SUMMARY.md` is **not** written (removed); use `REPORT.md` + `run-summary.json`.

## ticket-spec

```yaml
evidence_required:
  - transaction_audit   # E2E + DB asserts required (contract)
  - api_response
  - logs
  - kafka               # request KAFKA_VERIFY + kafka evidence when in scope
  - redis               # request REDIS_VERIFY + redis evidence when in scope

run:
  kafka:
    mode: auto           # auto | on | off
  redis:
    mode: auto           # auto | on | off

kafka_scenarios: []     # optional produce/consume/assert
redis_scenarios: []     # optional pattern min_keys checks
```

## validate-ticket steps (run_flow)

| Step | Output |
|------|--------|
| `db` / scenarios | `DB_VERIFY_QUERIES.sql`, `evidence/db/<scenario>.txt` |
| `kafka_*` | `kafka-discovered.json`, `KAFKA_VERIFY.md`, `evidence/kafka/*` |
| `redis_capture` | `evidence/redis/capture-*.json`, `keys-index.txt` |
| `redis_verify_doc` | `REDIS_VERIFY.md` |
| `log_verify` | `LOG_VERIFY_COMMANDS.md`, optional `log-search.txt` |
| `evidence` | Copies API responses, log search into `evidence/` |

`REPORT.md` links all verify docs and evidence paths in **Manual verification** and **Related artifacts**.

## Sample bundle

Committed example (no live services): [../assets/examples/sample-validate-output/README.md](../assets/examples/sample-validate-output/README.md) — regenerate with `bob refresh-samples`.

## See also

- [DATA_LAYOUT.md](DATA_LAYOUT.md) — git policy and paths
- [KAFKA_FOR_BOB.md](KAFKA_FOR_BOB.md)
- [REDIS_FOR_BOB.md](REDIS_FOR_BOB.md)
- [templates/host-deploy-tdd/deploy/tdd/INFRA_FOR_BOB.md](../templates/host-deploy-tdd/deploy/tdd/INFRA_FOR_BOB.md) — platform infra map
