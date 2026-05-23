# Host repo `deploy/tdd/` template (~2 minutes)

Copy this folder into **your service git repo** (the **host** repo where you run tickets). Bob does **not** commit these files for you.

## Quick copy

From your **host service repo** root (e.g. credit-card-management):

```bash
# Bash / Git Bash (adjust BOB path if needed)
BOB=../bob-the-builder
mkdir -p deploy/tdd
cp "$BOB/templates/host-deploy-tdd/deploy/tdd/workspace-services.yaml" deploy/tdd/
cp "$BOB/templates/host-deploy-tdd/deploy/tdd/env-local.yaml" deploy/tdd/
# Optional Novopay CC example (matches default env_profile in ticket-spec schema):
# cp "$BOB/templates/host-deploy-tdd/deploy/tdd/env-local-dsa.yaml" deploy/tdd/
```

Windows (PowerShell):

```powershell
$Bob = "..\bob-the-builder"
New-Item -ItemType Directory -Force -Path deploy\tdd | Out-Null
Copy-Item "$Bob\templates\host-deploy-tdd\deploy\tdd\workspace-services.yaml" deploy\tdd\
Copy-Item "$Bob\templates\host-deploy-tdd\deploy\tdd\env-local.yaml" deploy\tdd\
```

## Edit (required)

1. **`workspace-services.yaml`** — set `repo_dir` to your clone folder name(s) under `BUILDER_WORKSPACE_ROOT`.
2. **`env-local.yaml`** (or `env-local-dsa.yaml`) — set service URLs, MySQL schema names, health paths.
3. **`docs/tdd-runs/<ticket>/ticket-spec.yaml`** — set `env_profile:` to match the env file **basename** (without `.yaml`), e.g. `local` or `local-dsa`.
4. Run **`bob setup`** once — map `CC_BASE`, `MD_BASE`, `MYSQL_*`, `LOGS_DIR` in `bob-the-builder/local/user.env`.
5. Bob can **`bootRun` services for you** in two ways:
   - **Dynamic (no config required):** `bob ensure-peers` or `bob need-service notifications` — scans host Java/properties + session registry; boots only what is down.
   - **Profile-based (optional):** `deploy/tdd/workspace-services.yaml` + env profile `services.*.boot`; auto on `validate-ticket` when `run.auto_boot_services: true` (default) and `run.auto_discover_services: true` (default).

Bank/HDFC stays on **WireMock** — never bootRun partner APIs.

## Verify

```bash
cd your-host-service-repo
bob init-ticket MY-123 "Title"
bob discover-apis
bob ensure-peers          # optional: boot discovered peers before validate
bob validate-ticket MY-123
```

## Files

| File | Purpose |
|------|---------|
| `workspace-services.yaml` | Which repos exist in the workspace + `application.properties` paths |
| `env-local.yaml` | Generic env profile (ports, health checks, audit DB) |
| `env-local-dsa.yaml` | Example Novopay CC + masterdata profile (`env_profile: local-dsa`) |

See `docs/TDD_SYSTEM_DEVELOPER_GUIDE.md` in the Bob repo for the full workflow.
