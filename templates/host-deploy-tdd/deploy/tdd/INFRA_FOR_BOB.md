# Novopay platform - moving parts for Bob TDD

Bob `validate-ticket` automates what it can locally. Use this map to know what to run or mimic.

## What Bob drives today

| Component | Bob behavior | Your setup |
|-----------|--------------|------------|
| **Spring services** | Boots CC, masterdata (from `deploy/tdd/env-*.yaml`); health UP/DOWN | `bob setup` → `CC_BASE`, `MD_BASE`; services on 8016/8015 |
| **MySQL** | Seed SQL, API DB asserts, `DB_VERIFY_QUERIES.sql` | `MYSQL_*` in `bob-the-builder/local/user.env` |
| **WireMock** | HDFC bank stubs (card summary, product eligibility) | Port from `run.wiremock_port` (default 9090) |
| **Redis (config cache)** | Primes `dev_<tenant>_config_*` keys so CC reads WireMock URLs | Local Redis on 6379; tenant DB index from `platform_master.tenant_master` (dsa=2) |
| **Log files** | Writes `LOG_VERIFY_COMMANDS.md`; runs `search-logs.sh` if `LOGS_DIR` set | `bob setup` → `LOGS_DIR` = e.g. `/apps/applogs/dsa` on QA jump host |
| **Kafka** | `bob kafka up` or `run.kafka.enabled` on validate-ticket | Docker; UI :8090, broker :9092 |
| **Elasticsearch** | Not started (draft app / ES-backed reads) | Optional index or skip ES scenarios |
| **api-gateway / actor** | Not booted by default; Postman prerequisites may call gateway | Local gateway 8080 or QA `ddp-qa.novopay.in` |

## Not only five boxes

Besides **services, DB, logs, Kafka, Redis**, Novopay stacks often include:

- **api-gateway** - external entry (`/api-gateway/api/novopay/v1/...`)
- **WireMock** - bank/HDFC partner mimic (Bob uses this heavily for LOC/CC)
- **Masterdata DB + Redis cache** - HDFC URL keys, tenant config
- **Platform MySQL** - `platform_master` (service endpoints, tenant redis index)
- **Consents / notifications** - sometimes auto-discovered for boot; often optional
- **DMS** - document upload/download (gateway document APIs)
- **Elasticsearch** - draft application and search-heavy flows
- **Batch / schedulers** - not in Bob E2E loop
- **External HDFC UAT** - only when Redis/masterdata not pointed at WireMock

For **LOC dummy-jumbo** tickets, the critical path is: **CC + masterdata + MySQL + WireMock + Redis config prime**.

## Redis (config cache)

CC reads HDFC URLs from Redis after masterdata load.

1. Run **Redis** locally (`redis-server`, default port 6379).
2. Bob runs `redis-cli` to SET serialized config keys (see validate-ticket step `Prime CC Redis`).
3. Ensure `platform_master.tenant_master` has `redis_db_index` for tenant `dsa` (usually `2`).

Optional in `local/user.env`:

```properties
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
```

## Kafka (bulk / async)

Used for bulk lead upload (`bulk-upload-leads-{tenant}_{env}`), consent, some report pipelines.

**Bob (local):**

```bash
bob kafka up          # Docker: broker :9092, UI http://localhost:8090
bob kafka topics
bob kafka consume bulk-upload-leads-dsa_dev --max 20
bob kafka produce bulk-upload-leads-dsa_dev bulk-lead-min.json
```

**ticket-spec:**

```yaml
run:
  kafka:
    enabled: true
kafka_scenarios: []   # produce/consume/assert — see bob-the-builder/docs/KAFKA_FOR_BOB.md
```

On `validate-ticket` with `run.kafka.mode: auto`, Bob scans **only impacted/changed** produce/consume code (not the whole repo), writes `KAFKA_VERIFY.md` and `kafka-discovered.json`, and auto-fixes Docker/topics/bootstrap when needed.

**Without Docker:** use unit tests (mock producer) or QA log grep via `LOG_VERIFY_COMMANDS.md`.

## Logs

Set once:

```bash
bob setup
# LOGS_DIR=C:\path\to\logs   or   /apps/applogs/dsa
```

Each validate-ticket writes:

- `LOG_VERIFY_COMMANDS.md` - grep/rg commands per scenario and CRN
- `log-search.txt` - actual matches when `LOGS_DIR` is reachable from your machine

## Single report artifact

Every run produces **one** markdown report: `docs/tdd-runs/<ticket>/REPORT.md` (plus `TEST_PLAN.md`, SQL/log helper files). `RUN_SUMMARY.md` is not used.
