# Redis for Bob (config cache evidence)

Bob treats **Redis** like **logs** and **DB**: each `validate-ticket` run can emit **commands** (`REDIS_VERIFY.md`), **captured snapshots** (`evidence/redis/`), and optional **scenario checks** (`redis_scenarios`).

For the full evidence model (all verify types), see [EVIDENCE_AND_VERIFY.md](EVIDENCE_AND_VERIFY.md).

## When Redis runs

| Trigger | Behavior |
|---------|----------|
| `evidence_required` includes `redis` | Always write `REDIS_VERIFY.md` + capture |
| `run.redis.mode: on` | Same |
| `run.redis.mode: auto` (default) | When `masterdata[]`, `stubs[]`, or `impacted.bank_operations` (CC WireMock path) |
| `run.redis.mode: off` | Skip Redis verify/capture |

## ticket-spec

```yaml
evidence_required:
  - transaction_audit
  - api_response
  - logs
  - kafka
  - redis

run:
  redis:
    mode: auto
    # host: 127.0.0.1
    # port: 6379
    # db: 2
    scan_pattern: dev_dsa_config_CREDIT-CARD-MANAGEMENT_*
    capture_keys: []   # optional explicit keys
    max_keys: 50

redis_scenarios:
  - id: R1
    name: NovopayConfig keys present after prime
    pattern: dev_dsa_config_CREDIT-CARD-MANAGEMENT_*
    min_keys: 1
```

## Environment (`bob setup` / `user.env`)

```text
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
TENANT=dsa
```

Tenant DB index is resolved from `platform_master.tenant_master.redis_db_index` (DSA is usually `2`).

## validate-ticket steps

1. **redis_config_prime** (when `masterdata[]` + WireMock) — JDK-serialized SET via `redis-cli`
2. **redis_capture** — snapshot keys to `evidence/redis/capture-<timestamp>.json`
3. **redis_scenarios** — optional min-key checks on patterns
4. **redis_verify_doc** — writes `REDIS_VERIFY.md` with copy-paste `redis-cli` commands

## Evidence layout

```text
docs/tdd-runs/<ticket-id>/
  REDIS_VERIFY.md
  evidence/redis/
    capture-20260601T120000Z.json
    keys-index.txt
```

## Parity with other proof types

| Kind | Commands doc | Evidence folder |
|------|----------------|-----------------|
| DB | `DB_VERIFY_QUERIES.sql` | `evidence/db/` |
| Logs | `LOG_VERIFY_COMMANDS.md` | `evidence/logs/` |
| Kafka | `KAFKA_VERIFY.md` | `evidence/kafka/` |
| Redis | `REDIS_VERIFY.md` | `evidence/redis/` |

See also [KAFKA_FOR_BOB.md](KAFKA_FOR_BOB.md) and [DATA_LAYOUT.md](DATA_LAYOUT.md).
