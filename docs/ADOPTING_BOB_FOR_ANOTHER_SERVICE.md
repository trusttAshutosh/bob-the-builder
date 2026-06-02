# Adopting Bob the Builder for another Novopay service

Bob is **one shared engine** (`bob-the-builder/`) used across Novopay backend repos. It is **not** a separate product per service. Credit-card management is where Bob was **dogfooded first**, so some defaults and examples look CC-specific — the architecture is already **host-repo driven**.

## Is Bob only for credit-card?

| Layer | CC-specific? | Reality |
|-------|----------------|---------|
| **Engine** (`runner/`, `bob.py`) | No | Same CLI for any Gradle Spring service in the workspace |
| **Live catalogs** (`assets/api-catalog`, `platform-graph`) | No | Built from **whichever repo** `BOB_HOST_REPO` points at when you run `discover-apis` / `sync-graph` |
| **Tickets + evidence** | Per service | Live in **host** repo: `docs/tdd-runs/<id>/` |
| **Templates** | Example profile | `templates/host-deploy-tdd/` uses DSA/CC as **sample** (`env-local-dsa.yaml`) — you duplicate and rename |
| **Reference pack** | CC only | `assets/examples/novopay-cc/` — optional copy source, **never loaded automatically** |
| **Product defaults** | CC-shaped fallbacks | `runner/config/bob-defaults.yaml` when host `deploy/tdd` omits a field — override per service in `deploy/tdd` |

**Working today on another repo:** point Bob at that repo, copy `deploy/tdd`, run discover + validate. Many teams already can use `bob need-service`, `ensure-peers`, and `validate-ticket` without forking Bob.

---

## Is CC coupling good?

**Good for Novopay CC team:**

- Rich `examples/novopay-cc` (APIs, HDFC stubs, assertions)
- Skills and docs assume LOC/HDFC/WireMock/masterdata patterns
- Fast path: no extra setup

**Limitation for other services:**

- Empty catalog until they run `discover-apis` from **their** host repo
- Ticket-spec templates and DB asserts may mention `transaction_audit` / DSA schemas unless they override
- Postman export defaults assume gateway path `/api/v2/credit_card_management` unless configured

**Recommendation:** Keep **one** `bob-the-builder` repo for the org. Make the engine **neutral** over time (config in host `deploy/tdd/`, not in Python). Keep **CC examples** as `assets/examples/novopay-cc/`, not as the only path.

---

## Will making Bob generic hurt CC effectiveness?

**No**, if neutrality is done via **host config**, not by removing CC features.

| Approach | CC impact | Other services |
|----------|-----------|----------------|
| Host `deploy/tdd/env-*.yaml` defines primary service, ports, DB schemas | CC keeps `env-local-dsa.yaml` | Each service has its own profile |
| `ticket-spec` per ticket defines APIs, stubs, `audit_db` | Unchanged for CC tickets | Their tables and APIs |
| `assets/examples/novopay-cc` stays as reference | Copy/stub patterns preserved | They add `examples/novopay-payments` later if useful |
| Remove CC hardcodes from Python (NEXT.md items) | Same behavior via config | Cleaner onboarding |

Generic Bob **increases** effectiveness org-wide; CC stays as strong as today when `BOB_HOST_REPO` is the CC repo and CC `deploy/tdd` is present.

---

## Do not fork Bob per team

| Approach | Verdict |
|----------|---------|
| **Share `bob-the-builder`**, each service owns `deploy/tdd` + `docs/tdd-runs/` | Preferred |
| **Fork Bob** and maintain two engines | Avoid — drift, double fixes |
| **Copy only skills + a shell script** | Too weak — you lose graph, eval, Kafka discovery, Obsidian export |

---

## Easiest adoption path (checklist)

### Workspace root (`BUILDER_WORKSPACE_ROOT`)

`bob setup` asks for the **Novopay folder on your machine** — the parent that contains `bob-the-builder` and your service clones. That path is `BUILDER_WORKSPACE_ROOT`. Bob lists all git repos there for peer discovery (`bob discover-services`, `ensure-peers`).

**CC stays the default** when you do not customize anything: `runner/config/bob-defaults.yaml` and `env_profile: local-dsa` match the credit-card DSA profile. Your effectiveness on CC tickets does not depend on other teams adopting Bob.

Run `bob host` to confirm `BOB_HOST_REPO` and which `deploy/tdd` profile is loaded.

Details: [WORKSPACE_AND_HOST_PROFILE.md](WORKSPACE_AND_HOST_PROFILE.md).

## Prerequisites

- Git clone `bob-the-builder` next to service repos under one parent folder
- JDK, Gradle, Docker (optional Kafka), local MySQL if tickets need DB asserts
- Cursor (optional) for `skills/builder-*`

### Steps

1. **Workspace layout**

   ```text
   your-workspace/
     bob-the-builder/
     novopay-platform-your-service/
     novopay-platform-masterdata-management/   # if needed
   ```

2. **Bob setup** (once per machine)

   ```bash
   cd bob-the-builder
   python bob.py setup
   python bob.py install
   ```

   Set `BUILDER_WORKSPACE_ROOT` to `your-workspace/`.

3. **Host glue in your service repo**

   ```bash
   cd ../novopay-platform-your-service
   cp -r ../bob-the-builder/templates/host-deploy-tdd/deploy/tdd ./deploy/
   ```

   Edit `deploy/tdd/env-local-<tenant>.yaml`:

   - `primary_service: your_service_key` (e.g. `payments_management`)
   - `services.*.default_base` — port and context path from `application.properties`
   - `mysql.schemas` — schemas for DB asserts

4. **Point Bob at your repo**

   In `bob-the-builder/local/user.env`:

   ```properties
   BOB_HOST_REPO=C:\path\to\novopay-platform-your-service
   YOUR_BASE=http://localhost:8xxx/your-context
   ```

   Or `cd` into your service repo before `bob` commands (Bob infers host from cwd).

5. **Build live catalogs from your code**

   ```bash
   bob discover-apis
   bob sync-graph
   ```

   This fills `bob-the-builder/assets/api-catalog/` and `platform-graph/` from **your** orchestration XML and processors — not CC.

6. **First ticket**

   ```bash
   cd novopay-platform-your-service
   bob init-ticket adhoc-my-feature "Short title"
   ```

   Edit `docs/tdd-runs/adhoc-my-feature/ticket-spec.yaml`:

   - `impacted.gateway_apis` — your APIs
   - `impacted.repos` — your repo (+ lib if shared)
   - `stubs` — WireMock refs under `assets/stub-registry/` (create fixtures per bank/partner pattern)
   - `run.audit_db` / `scenarios[].db` — your tables, not `transaction_audit` unless you use it
   - `env_profile: local-<your-profile>`

7. **Validate**

   ```bash
   bob validate-ticket adhoc-my-feature
   ```

8. **Optional: Cursor skills**

   Copy `bob-the-builder/skills/builder-*` into team Cursor skills, or open the monorepo with Bob rules. Skills are **workflow** (analyst / implementer / verifier), not CC-only code.

9. **Optional: reference CC pack**

   Only to learn **shapes** (stub YAML, ticket-spec scenarios):

   `assets/examples/novopay-cc/` — do not copy blindly; APIs and HDFC stubs are CC-specific.

---

## Cursor prompt (bootstrap a new service profile)

Paste into Cursor with your service repo open and `bob-the-builder` in the workspace:

```text
We adopt Bob the Builder from ../bob-the-builder (shared engine). This repo is the HOST.

Tasks:
1. Copy templates/host-deploy-tdd/deploy/tdd into ./deploy/tdd if missing.
2. Create deploy/tdd/env-local-<tenant>.yaml for this service:
   - primary_service and services.* from application.properties (port, context-path)
   - mysql.schemas from our Flyway/schema names
3. Run (or document): bob discover-apis, bob sync-graph with BOB_HOST_REPO=this repo.
4. Create docs/tdd-runs/adhoc-<feature>/ticket-spec.yaml for: <describe feature>
   - impacted.gateway_apis from deploy/application/orchestration
   - stubs only for external HTTP we must mock
   - db asserts on our real tables (not CC transaction_audit unless we use it)
5. Do not fork bob-the-builder; only host-specific files live here.

Follow bob-the-builder/docs/TDD_SYSTEM_DEVELOPER_GUIDE.md and ADOPTING_BOB_FOR_ANOTHER_SERVICE.md.
```

Adjust paths and feature description.

---

## What you must customize per service

| Item | CC example | Your service |
|------|------------|--------------|
| Orchestration scan | `deploy/application/orchestration/*.xml` | Same layout if Novopay standard |
| Processor scan | `*Processor.java` | Same |
| Primary HTTP base | `CC_BASE` / 8016 | Your env var in `user.env` + `deploy/tdd` |
| DB asserts | `transaction_audit`, `dsa_credit_card_mgmt` | Your entities / schemas in ticket-spec |
| WireMock stubs | HDFC bank-operations | Your partner mocks |
| Postman | `postman-url-defaults.yaml` + ticket `run.postman` | Your gateway path segment |
| Kafka | `MessageBroker.xml` if present | `run.kafka.mode: auto` discovers from your code |
| Git branch policy | `novopay-feature` / `ddp-fea-*` | Your team policy in ticket-spec |

---

## Neutrality (engine — mostly landed)

Tracked in [NEXT.md](NEXT.md). Already in place:

- `runner/lib/host_profile.py` + `runner/config/bob-defaults.yaml` (CC/DSA defaults when host profile is missing)
- `bob host`, [WORKSPACE_AND_HOST_PROFILE.md](WORKSPACE_AND_HOST_PROFILE.md)
- Neutral `ticket-spec.schema.yaml` with `HOST_REPO_FOLDER` placeholder
- `discover-apis` / Postman / audit helpers read host `deploy/tdd` first
- `bob setup` prompts each `{SERVICE}_BASE` from deploy/tdd

CC team: keep `env_profile: local-dsa` and `deploy/tdd/env-local-dsa.yaml` — behavior unchanged.

---

## FAQ

**Q: Can two services share one `assets/api-catalog`?**  
Only one **host** is active per run (`BOB_HOST_REPO`). Re-run `discover-apis` when switching host, or use separate workspaces.

**Q: Where do tickets live?**  
Always in the **host service repo**: `docs/tdd-runs/`.

**Q: Is Obsidian / eval / Kafka CC-only?**  
No. They use discovered graph, ticket-spec, and code scan — any repo with orchestration/processors/Kafka.

**Q: Minimum viable adoption?**  
`bob setup`, copy `deploy/tdd`, one `ticket-spec`, `validate-ticket` with `run.auto_boot_services: true` and API steps — even without full stub registry if tests are unit-only (not recommended for integration tickets).

---

## Related docs

- [README.md](README.md) — documentation index
- [WORKSPACE_AND_HOST_PROFILE.md](WORKSPACE_AND_HOST_PROFILE.md)
- [TDD_SYSTEM_DEVELOPER_GUIDE.md](TDD_SYSTEM_DEVELOPER_GUIDE.md)
- [DATA_LAYOUT.md](DATA_LAYOUT.md)
- [BOB_CONTEXT_AND_EVAL.md](BOB_CONTEXT_AND_EVAL.md)
- [KAFKA_FOR_BOB.md](KAFKA_FOR_BOB.md)
- [GRAPH_OBSIDIAN.md](GRAPH_OBSIDIAN.md)
- [templates/host-deploy-tdd/README.md](../templates/host-deploy-tdd/README.md)
