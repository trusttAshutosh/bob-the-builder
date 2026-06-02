# Kafka verification (Bob — discovered from impacted code)

Ticket: `sample-gateway-health-check`
Bootstrap: `localhost:9092` | UI: http://localhost:8090
Mode: `auto`

## Discovered bindings

| Role | Resolved topic | Source |
|------|----------------|--------|
| producer | `dsa_dev_sample_events` | `sample_outputs.py (illustrative)` |

## Start / stop

```bash
bob kafka up
bob kafka discover --ticket sample-validate-output
bob kafka setup --ticket sample-validate-output
bob kafka down
```

## Docker

```bash
docker compose -f runner/kafka/docker-compose.yml up -d
```

## Consume (per discovered topic)

### `dsa_dev_sample_events`

```bash
bob kafka consume dsa_dev_sample_events --max 20 --timeout 15
```

## CC / service bootRun

Bob sets `BOB_KAFKA_BOOTSTRAP` and passes:

```text
--message.broker.bootstrap.servers=localhost:9092
```

Artifact: [kafka-discovered.json](./kafka-discovered.json)

## Auto-fix (last run)

- Sample: would run `bob kafka up` when Docker is available

