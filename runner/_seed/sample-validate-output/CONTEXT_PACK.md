# Bob context pack

Ticket: `sample-gateway-health-check`
Generated: 2026-06-01 12:00:00

## Your Bob preferences (illustrative)

Sample bundle uses **placeholder** paths — real runs read `bob setup` / `user.env` on your machine.

| Key | Example (not machine-specific) |
|-----|--------------------------------|
| BOB_HOME | `<bob-repo>/assets` |
| BOB_LOCAL | `<bob-repo>/local` |
| BUILDER_WORKSPACE_ROOT | `<parent>/novopay` |
| CC_BASE | `http://localhost:8016/cc-mgmt` |
| MD_BASE | `http://localhost:8015/masterdata` |
| LOGS_DIR | `<workspace>/SERVER_LOGS` |

## Staleness checks (illustrative)

- **WARN** `spec_newer_than_graph`: ticket-spec.yaml is newer than platform-graph.yaml.
  - Fix: `bob sync-graph`
- **WARN** `catalog_empty`: API catalog empty but ticket lists gateway_apis (common on CI).
  - Fix: `bob discover-apis` on a host with services cloned

## Postman defaults (ticket-spec)

- local gateway: `http://localhost:8080/api-gateway`
- QA gateway: ``

## Hybrid retrieval (illustrative excerpt)

**Query terms:** sample, gateway, health, check, inquireCardEligibility
**Platform graph:** novopay-platform-creditcard-management (pinned sample)
**Hits:** 3 (truncated for committed bundle — full runs vary by catalog/graph)

### Api

- **inquireCardEligibility** (score 2.45) — path=/api/v1/inquireCardEligibility beans=2
- **manageLOCTransactionAudit** (score 1.51) — path=/api/v1/manageLOCTransactionAudit beans=3

### Processor

- **inquireCardEligibilityProcessor** (score 2.08) <- inquireCardEligibility
- **manageLOCTransactionAuditProcessor** (score 1.29) <- manageLOCTransactionAudit
