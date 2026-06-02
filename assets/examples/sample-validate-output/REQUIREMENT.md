# Sample requirement (fictional)

**As a** platform developer  
**I want** a gateway API that records an audit row when a customer checks product eligibility  
**So that** we can prove the flow locally before raising a PR.

## Acceptance criteria

- Happy path returns success and writes `txn_status=SUCCESS` for the scenario CRN.
- Downstream audit fields match the assertion preset in the ticket spec.
- Optional: Kafka publish is documented when the flow includes async messaging.

Bob turns this text into `ticket-spec.yaml`, `TEST_PLAN.md`, and the artifacts under this folder when you run `bob validate-ticket` on a real host repo.
