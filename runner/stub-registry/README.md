# Stub registry

Reusable **bank-operation** WireMock fixtures. Tickets reference fixtures in `ticket-spec.yaml`:

```yaml
stubs:
  - ref: getCardSummary/success-200
```

Layout: `bank-operations/<operation>/<fixture-id>.yaml` plus `__files/` for response bodies.

Add new operations and fixtures per ticket needs — not tied to any single product ticket.
