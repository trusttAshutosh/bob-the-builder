# Workspace layout and host profile

Bob is **one engine** (`bob-the-builder/`) used against **any Novopay Gradle repo** under your workspace folder. Credit-card management remains the **product default** when host config is missing.

## Two roots (what `bob setup` asks for)

| Variable | Meaning |
|----------|---------|
| `BUILDER_WORKSPACE_ROOT` | Parent folder with your Novopay git clones (what Bob calls the workspace) |
| `BOB_HOST_REPO` | Active service repo for this session (tickets, orchestration, `deploy/tdd`) |

Typical layout:

```text
BUILDER_WORKSPACE_ROOT/          # e.g. .../Desktop/novopay
  bob-the-builder/
  novopay-platform-creditcard-management/   # often BOB_HOST_REPO
  novopay-platform-masterdata-management/
  novopay-platform-<other-service>/
```

Bob picks the host repo from:

1. `BOB_HOST_REPO` if set
2. Current git root (if it is a Gradle project or has `deploy/tdd/`)
3. Nearest git repo under the workspace when cwd is inside a clone
4. `BOB_LAST_HOST_REPO` fallback

Run `bob host` anytime to see the resolved host, workspace repos, and `deploy/tdd` profile file.

## Where CC defaults live (your path unchanged)

| Layer | CC behavior |
|-------|-------------|
| `runner/config/bob-defaults.yaml` | `local-dsa`, `CC_BASE`, `8016/cc-mgmt`, `dsa_credit_card_mgmt` |
| Host `deploy/tdd/env-local-dsa.yaml` | Full DSA profile (copy from `templates/host-deploy-tdd/`) |
| `assets/examples/novopay-cc/` | Reference APIs/stubs only — not auto-loaded |

When `env_profile: local-dsa` and host `deploy/tdd/env-local-dsa.yaml` exist, behavior matches pre-neutral Bob.

When a host has **no** `deploy/tdd` file, Bob **synthesizes** a profile from `application.properties` (port/context) plus `bob-defaults.yaml` for audit shape.

## Another service in the same workspace

1. `export BOB_HOST_REPO=.../novopay-platform-your-service` (or `cd` into that repo)
2. Copy `templates/host-deploy-tdd/deploy/tdd/` into the host repo; edit `env-local-generic.yaml` (rename suffix to match `env_profile` in tickets)
3. `bob discover-apis` and `bob sync-graph` from that host
4. `bob init-ticket ...` — `impacted.repos` is filled with the current host folder name

Postman gateway paths and API catalog `base_env` come from the host profile (`primary_service`, `gateway_v2_segment`), not from Python hardcodes.

## Neutrality vs effectiveness

- **Generic:** discovery, graph, Kafka, eval, and catalogs follow `BOB_HOST_REPO`.
- **CC default:** `bob setup` reads `deploy/tdd/env-*.yaml` and prompts labeled URLs (`CC_BASE`, `MD_BASE`, …). Product fallbacks stay in `bob-defaults.yaml` when a field is missing.

See also [ADOPTING_BOB_FOR_ANOTHER_SERVICE.md](ADOPTING_BOB_FOR_ANOTHER_SERVICE.md) · [README.md](README.md) (full doc index).
