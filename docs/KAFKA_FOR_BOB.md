# Kafka for Bob (flow-aware, not bulk-specific)

Bob discovers **Kafka producers, consumers, and topics from the code you are changing** (any Novopay repo/flow), then prepares local Docker Kafka and highlights or fixes setup gaps.

For the full evidence model (verify doc + `evidence/kafka/`), see [EVIDENCE_AND_VERIFY.md](EVIDENCE_AND_VERIFY.md).

## Modes (`ticket-spec.yaml`)

```yaml
run:
  kafka:
    mode: auto   # default — start Kafka only if impacted code uses it
    # mode: on   # always start (legacy: enabled: true)
    # mode: off  # never (legacy: enabled: false)
    tenant_code: dsa
    environment: dev
    autofix: true   # default — docker up, create topics, set BOB_KAFKA_BOOTSTRAP
```

| Mode | Behavior |
|------|----------|
| `auto` | Scan `impacted` repos/seeds; skip Kafka for LOC-only tickets |
| `on` | Always run discovery + setup |
| `off` | Skip Kafka entirely |

## What gets scanned

From each ticket, Bob builds **seed files** from:

- `impacted.processor_beans` → Java processors
- `impacted.gateway_apis` → related Java classes
- `impacted.paths` / `changed_paths`
- `git diff` on the host repo

Then scans (in scope packages + MessageBroker):

| Source | Detects |
|--------|---------|
| `deploy/**/messagebroker/MessageBroker.xml` | `topicPrefix`, consumer bean, group prefix |
| Java constants `*TOPIC_PREFIX` + `resolveKafkaTopic` | `{prefix}{tenant}_{environment}` |
| `@NovopayConfig` keys `*topic*` | Config override + dynamic template |
| `pushDataToKafkaQueue("…"+tenant…)` | Notifications-style topics (lib/other services) |
| `@KafkaListener` | Static consumer topics |
| `NovopayKafkaProducer.sendMessage` | Literal or dynamic producers |
| `AbstractTypedRecordConsumer` | Consumer + payload type |

Outputs:

- `docs/tdd-runs/<ticket>/kafka-discovered.json`
- `KAFKA_VERIFY.md` (commands + links to captures)
- `evidence/kafka/` — JSONL/JSON from `kafka_scenarios` and `run.kafka.capture_after_scenarios`
- REPORT section **Manual verification** (Kafka row + evidence path)

## CLI

```bash
bob kafka discover --ticket <id>    # scan only
bob kafka setup --ticket <id>       # scan + docker up + topics + bootstrap env
bob kafka up | down | status | topics
bob kafka consume <topic> --max 20
bob kafka produce <topic> <fixture.json> [--key KEY]
bob kafka test --ticket <id>        # run kafka_scenarios from ticket-spec
```

## ticket-spec scenarios (optional)

Use discovered topics with `topic: auto` or a binding:

```yaml
kafka_scenarios:
  - id: K1
    name: Replay discovered producer topic
    topic: auto
    binding_id: producer:BatchValidateLeadsService:BULK_UPLOAD_LEADS_TOPIC_PREFIX
    produce_fixture: bulk-lead-min.json
    consume:
      min_messages: 1
    assert_json:
      - path: header.tenant_code
        must_exist: true
```

Explicit topics still work: `topic: async_notifications_dsa_dev`.

## Auto-fix

When setup fails, Bob tries to:

1. Start Docker Compose Kafka (`runner/kafka/docker-compose.yml` via `bob kafka up`)
2. Set `BOB_KAFKA_BOOTSTRAP=localhost:9092` and CC bootRun `--message.broker.bootstrap.servers=...`
3. Create missing topics from resolved templates
4. Write `deploy/tdd/bob-kafka.properties` on the host repo if missing

**Issues** (multi-broker `application.properties`, Docker down, no bindings in scope) appear in REPORT and `KAFKA_VERIFY.md`.

## Impacted repos

List all clones that participate in the flow:

```yaml
impacted:
  repos:
    - novopay-platform-creditcard-management
    - novopay-platform-lib
    - novopay-platform-notifications
```

See also [README.md](README.md) (doc index) · [WORKSPACE_AND_HOST_PROFILE.md](WORKSPACE_AND_HOST_PROFILE.md).

Bob resolves paths via `BUILDER_WORKSPACE_ROOT` / `find_repo`.

## See also

- `templates/host-deploy-tdd/deploy/tdd/INFRA_FOR_BOB.md`
- CC MessageBroker: `deploy/application/messagebroker/MessageBroker.xml`
