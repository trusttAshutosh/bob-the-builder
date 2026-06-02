# Test plan: Sample gateway health and audit proof

**Ticket:** `sample-gateway-health-check`
**Feature:** sample-gateway
**Env profile:** local-dsa

_Generated/updated by Bob `validate-ticket`. Run results live in [REPORT.md](./REPORT.md)._

## Acceptance criteria

- [ ] API returns success for the happy-path scenario
- [ ] transaction_audit row matches expected status and result codes

## Planned scenarios

| Scenario ID | Description | Level | APIs | Pre-setup | DB expected |
|-------------|-------------|-------|------|-----------|-------------|
| S1 | Happy path — eligibility inquiry | e2e | inquireCardEligibility | — | expect: txn_status=SUCCESS, txn_result_code=000 |
| S2 | Integration — processor unit scope | integration | — | — | — |

## Manual / Postman

- Import Postman collection under [postman/](./postman/) after validate-ticket.
- Run **prerequisites** before **apis-under-test** (avoids 4000028).
