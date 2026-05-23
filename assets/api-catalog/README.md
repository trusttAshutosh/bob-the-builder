# CC API catalog (shared sanity collection)

Reusable gateway API definitions discovered from the codebase. **Grows over time** — one YAML per API.

## Layout

```
api-catalog/
  index.yaml          # registry of api_id → file
  apis/<api_id>.yaml  # path, envelope, defaults, template ref
```

## Add an API (agent / developer)

1. **Auto-discover** missing APIs from orchestration XML:

```bash
bob discover-apis
```

2. **Review / complete** generated skeleton under `apis/<name>.yaml` (defaults, `bank_calls`, sample values).

3. **Register** is automatic via `index.yaml` refresh.

## Per-ticket overrides

In `docs/tdd-runs/<ticket>/ticket-spec.yaml` — do **not** duplicate full API defs; reference `api_id` and override only what the use case needs:

```yaml
steps:
  - api_id: getLOCOffers
    vars: { CRN: "{CRN}", MOBILE: "9999999999" }
    overrides:
      headers: { stan: "{STAN}" }
      request: { aan: "0000000000000000001" }
```

URLs come from catalog (`CC_BASE` + path). Headers use catalog defaults unless `overrides.headers`.

## If API is missing

`discover-apis` creates a skeleton from host `deploy/application/templates/request/product/<api>_requestTemplate.json` when present. Agent fills `request_defaults` after reading processors / orchestration.
