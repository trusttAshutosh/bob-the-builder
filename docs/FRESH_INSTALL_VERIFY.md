# Fresh install verification

Proves the **empty-catalog model**: a clean `bob install` seeds empty `assets/api-catalog/`; `bob discover-apis` from a **non-CC** host repo fills skeletons from orchestration XML + host `deploy/tdd/`.

Bob never commits or pushes - this doc is for humans and CI.

## What gets checked

| Step | Expectation |
|------|-------------|
| Temp `BOB_HOME` after `bob install` | `api-catalog/apis/` has **zero** YAML files; `index.yaml` has empty `apis:` map |
| `bob discover-apis` from fixture host | Creates `smokeGetHealth` + `smokeSubmitOrder` skeletons |
| Non-CC host profile | Host folder `novopay-platform-payments-fixture` -> catalog `service: payments-fixture` |
| Host deploy/tdd override | `http.base_env: PAYMENTS_BASE` (not `CC_BASE`) |

Fixture tree: [`runner/tests/fixtures/ci-host/`](../runner/tests/fixtures/ci-host/README.md).

## Run locally

From `bob-the-builder/`:

```bash
pip install pyyaml
python runner/ci/verify-fresh-install.py
```

Or via CLI:

```bash
bob verify-fresh-install
```

Quiet (exit code only):

```bash
bob verify-fresh-install --quiet
```

Unit tests:

```bash
PYTHONPATH=runner/lib python -m pytest runner/tests/test_fresh_install.py -v
```

## CI

[`.github/workflows/bob-smoke.yml`](../.github/workflows/bob-smoke.yml) runs the same script on every push/PR to `main`/`master`.

Uses `BOB_IGNORE_PREFS=1` so machine `local/user.env` does not override the isolated temp workspace.

## Manual fresh-clone walkthrough (optional)

On a machine with no prior Bob `assets/` usage:

1. Clone `bob-the-builder` only (no CC repo required for this check).
2. `pip install pyyaml`
3. `python bob.py verify-fresh-install` - should PASS.

For real dogfooding on a second service:

1. Clone service repo beside `bob-the-builder` under one workspace parent.
2. `bob setup` / `bob onboard` once.
3. Copy [`templates/host-deploy-tdd/`](../templates/host-deploy-tdd/README.md) into the service `deploy/tdd/`.
4. Confirm empty live catalog: `ls assets/api-catalog/apis/` (no YAML until discover).
5. From the service repo: `bob discover-apis`
6. Optional: one `bob validate-ticket` on a real ticket.

Live catalogs under `assets/api-catalog/` are **your** choice to commit; reference packs under `assets/examples/` are optional curated snapshots (see [ADOPTING_BOB_FOR_ANOTHER_SERVICE.md](ADOPTING_BOB_FOR_ANOTHER_SERVICE.md)).

## Related

- [DATA_LAYOUT.md](DATA_LAYOUT.md) - where Bob writes files
- [ADOPTING_BOB_FOR_ANOTHER_SERVICE.md](ADOPTING_BOB_FOR_ANOTHER_SERVICE.md) - onboarding another Novopay service
