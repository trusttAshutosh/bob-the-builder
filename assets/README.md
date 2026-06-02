# Bob the Builder — shared assets (`BOB_HOME`)

Live catalogs for **your** workspace. Grows when you run:

- `bob discover-apis` → `api-catalog/`
- `bob sync-graph` → `platform-graph/platform-graph.yaml`

Do **not** treat this tree as credit-card-only. Fresh installs start **empty** (see `runner/_seed/`).

## Layout

| Path | Purpose |
|------|---------|
| `api-catalog/` | Gateway API defs for the active host repo |
| `stub-registry/` | Reusable WireMock fixtures |
| `platform-graph/` | Processor/API knowledge graph |
| `assertion-catalog/` | Optional DB/log assertion presets |
| `examples/` | **Reference only** — not used by Bob automatically |

## Novopay CC reference

See [`examples/novopay-cc/README.md`](examples/novopay-cc/README.md) for a full CC/LOC catalog you can copy selectively — never required for other services.

Docs: [`../docs/README.md`](../docs/README.md).
