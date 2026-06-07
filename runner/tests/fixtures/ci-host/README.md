# CI / fresh-install fixture host

Minimal Novopay-shaped **non-CC** host tree for:

- `runner/ci/verify-fresh-install.py`
- `.github/workflows/bob-smoke.yml`

Not a runnable service - orchestration XML + `deploy/tdd/` only.

| Property | Value |
|----------|--------|
| Simulated clone name | `novopay-platform-payments-fixture` |
| Catalog `service` slug | `payments-fixture` |
| Base env var | `PAYMENTS_BASE` |
| APIs in XML | `smokeGetHealth`, `smokeSubmitOrder` |

Run locally:

```bash
python runner/ci/verify-fresh-install.py
# or: bob verify-fresh-install
```
