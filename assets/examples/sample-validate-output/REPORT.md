# Validation report: sample-gateway-health-check

- **Title:** Sample gateway health and audit proof
- **Started:** 2026-06-01T12:00:00
- **Finished:** 2026-06-01T12:00:00
- **Duration:** 42.5s
- **Overall:** **PASS** (exit 0)
- **Branch:** `main`

## Test plan

Planned scenarios and acceptance criteria: [TEST_PLAN.md](./TEST_PLAN.md)

**Acceptance criteria (from ticket-spec):**

- [ ] API returns success for the happy-path scenario
- [ ] transaction_audit row matches expected status and result codes

## Scenario results

_One row per scenario: description, expected DB outcome, actual DB row, and overall pass/fail._

| Scenario ID | Description | Level | APIs | CRN | DB expected | DB actual | DB check | Overall | Duration | Execution detail |
|-------------|-------------|-------|------|-----|-------------|-----------|----------|---------|----------|------------------|
| S1 | S1: Happy path — eligibility inquiry | e2e | inquireCardEligibility | `BOB-SAMPLE-20260601-S1` | expect: txn_status=SUCCESS, txn_result_code=000 | txn_status=SUCCESS; txn_result_code=000 | PASS | **PASS** | 1500ms | API 200; DB expect txn_status=SUCCESS |
| S2 | S2: Integration — processor unit scope | integration | — | `BOB-SAMPLE-20260601-S2` | — | — | N/A | **PASS** | — | Recorded as pass in sample bundle |

## Decision trace

_How the runner chose APIs, stubs, and environment._

- **api_catalog:** BOB_HOME/api-catalog (from discover-apis on host)
- **branch:** main
- **context_pack:** CONTEXT_PACK.md
- **crn:** BOB-SAMPLE-20260601
- **env_profile:** local-dsa
- **eval_regression_md:** EVAL_REGRESSION.md
- **kafka_verify_commands:** True
- **primary_service:** credit_card_management
- **redis_verify_commands:** REDIS_VERIFY.md
- **scenario_crns:** {'S1': 'BOB-SAMPLE-20260601-S1', 'S2': 'BOB-SAMPLE-20260601-S2'}
- **stubs_applied:** bank-operations/getCardSummary/success-200
- **wiremock_detail:** 127.0.0.1:9090 (sample — not started for doc bundle)
- **wiremock_status:** UP

## Service health

| Service | Status | Detail |
|---------|--------|--------|
| credit_card_management (primary) | UP | http://localhost:8016/cc-mgmt |
| wiremock | UP | :9090 |

_Sample bundle — illustrative only._


## Pipeline steps

| Step | Status | Duration | Detail |
|------|--------|----------|--------|
| Assemble CONTEXT_PACK | PASS | 120ms | prefs + stale + hybrid retrieval |
| WireMock runtime | PASS | 800ms | sample stub profile |
| Health credit_card_management | PASS | 200ms | http://localhost:8016/cc-mgmt (illustrative) |
| Scenario S1 | PASS | 1500ms | inquireCardEligibility — API + DB assert |
| Eval regression | PASS | 40ms | No regressions vs baseline |

## Performance

- **Total run:** 42.5s
- **Slowest steps:**
  - Scenario S1: 1500ms
  - WireMock runtime: 800ms
  - Health credit_card_management: 200ms
  - Assemble CONTEXT_PACK: 120ms
  - Eval regression: 40ms

## Execution log

```
=== Bob sample-validate-output (synthetic PASS run) ===
ticket=sample-gateway-health-check
This bundle is for documentation; run validate-ticket on your host repo for real evidence.
```

## Evidence paths


## Manual verification (optional)

| Kind | File |
|------|------|
| DB (MySQL Workbench) | [DB_VERIFY_QUERIES.sql](./DB_VERIFY_QUERIES.sql) |
| Logs (grep/rg on server) | [LOG_VERIFY_COMMANDS.md](./LOG_VERIFY_COMMANDS.md) |
| Kafka (local Docker / consume) | [KAFKA_VERIFY.md](./KAFKA_VERIFY.md) · [evidence/kafka/](./evidence/kafka/) |
| Redis (config cache / redis-cli) | [REDIS_VERIFY.md](./REDIS_VERIFY.md) · [evidence/redis/](./evidence/redis/) |
| Context (prefs + stale + KG) | [CONTEXT_PACK.md](./CONTEXT_PACK.md) |
| Eval regression | [EVAL_REGRESSION.md](./EVAL_REGRESSION.md) |

| Scenario | CRN |
|----------|-----|
| S1 | `BOB-SAMPLE-20260601-S1` |
| S2 | `BOB-SAMPLE-20260601-S2` |

## Related artifacts

_Single report file: this `REPORT.md` (no separate RUN_SUMMARY.md)._

- [TEST_PLAN.md](./TEST_PLAN.md) — planned scenarios (updated each validate-ticket)
- [DB_VERIFY_QUERIES.sql](./DB_VERIFY_QUERIES.sql) — MySQL dashboard + per-scenario SELECTs
- [LOG_VERIFY_COMMANDS.md](./LOG_VERIFY_COMMANDS.md) — copy-paste grep/rg for applogs
- [KAFKA_VERIFY.md](./KAFKA_VERIFY.md) — Kafka UI, consume/produce; captures in [evidence/kafka/](./evidence/kafka/)
- [REDIS_VERIFY.md](./REDIS_VERIFY.md) — redis-cli commands; snapshots in [evidence/redis/](./evidence/redis/)
- [CONTEXT_PACK.md](./CONTEXT_PACK.md) — prefs, staleness, hybrid KG retrieval
- [EVAL_REGRESSION.md](./EVAL_REGRESSION.md) — scenario baseline comparison
- [ticket-spec.yaml](./ticket-spec.yaml)
- [run-summary.json](./run-summary.json) — machine-readable
- [REPORT.html](./REPORT.html) — browser view
