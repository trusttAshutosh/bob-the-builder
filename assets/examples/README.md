# Example asset packs

Reference catalogs only — **Bob does not load these automatically.**

| Pack | Use when |
|------|----------|
| [`sample-validate-output/`](sample-validate-output/README.md) | **What Bob generates** after a requirement (`REPORT.md`, DB/log/Kafka/Redis verify docs, `evidence/*`) — auto-refreshed with the engine |
| [`novopay-cc/`](novopay-cc/README.md) | Novopay credit-card / LOC tickets; copy stubs or compare API YAML shape |

Live catalogs: `../api-catalog/`, `../stub-registry/`, … (populated by `discover-apis` / your team).

## Adding a pack for your service (optional)

After your team has used Bob on a real ticket, you **may** share a curated snapshot here (e.g. `novopay-payments/`). This is not required for Bob to work.

1. Curate sanitized files under `assets/examples/<your-pack>/` (not a blind copy of all live `assets/`).
2. Open a **new branch** on `bob-the-builder`, e.g. `examples/novopay-payments-initial`.
3. Commit, push, open a PR — **you** run git; Bob never commits or pushes.

Full branch naming, PR template, fork flow, and reviewer checklist: [`docs/CONTRIBUTING_REFERENCE_PACKS.md`](../../docs/CONTRIBUTING_REFERENCE_PACKS.md).

No write access to upstream? **Fork + PR** — you cannot push to `bob-the-builder` without collaborator access.
