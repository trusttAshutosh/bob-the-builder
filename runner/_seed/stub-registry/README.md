# Stub registry (Bob home)

Reusable WireMock fixtures by bank/partner operation.

Layout:

```text
{BOB_HOME}/stub-registry/bank-operations/<operation>/<fixture>.yaml
{BOB_HOME}/stub-registry/bank-operations/<operation>/__files/*.xml
```

Reference tickets via `stubs[].ref` in `ticket-spec.yaml`. Add fixtures here when they apply across tickets.

See also: `runner/stub-registry/README.md` for fixture YAML shape.
