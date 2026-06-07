# Bob the Builder — what to improve next

**Living backlog.** Update this file after audits, dogfooding, or team feedback — not only in chat or PR comments.

| | |
|---|---|
| **Read** | Before picking up Bob product work |
| **Update** | When something ships → move it to **Done** with date; when you find a gap → add under **Now** / **Next** / **Later** |
| **Verify** | You don't — say **commit** or **push** in Cursor; agent runs `bob remind --fix`. Bob auto-refreshes stale `docs/NEXT.md` after most commands. |
| **CI** | Blocks only if a **feature was removed** — not stamp drift |
| **CLI** | `bob next` · `bob verify-product` |

<!-- PRODUCT-VERIFY:COMMIT=7aa7a37 -->
<!-- PRODUCT-VERIFY:CHECKED=2026-06-08 -->

<!-- SCORECARD:START -->
## Current scorecard

> **Manual grades** — update the table when reality changes. **Feature integrity** is auto-checked every CI push.

| Dimension | Grade | Notes |
|-----------|-------|-------|
| Product vs host separation | A | Engine in `bob-the-builder/` only |
| End-to-end TDD loop | A- | Ticket spec → validate → evidence |
| Reusability / generic story | B+ | Empty `assets/`; CC in `examples/`; engine defaults still Novopay-shaped |
| Repo cleanliness | A | Published on GitHub; `origin` on `main` |
| Docs & operability | A | Guides, cheatsheet, clone URL in README |
| Team handoff | A- | KT doc + `bob onboard` bootstrap |
| **Overall** | **Architecture PASS · Product A- · shipped for team clone** | |

*Last feature check: 2026-06-08 · commit `7aa7a37` · 20/20 features intact · auto-refreshed after commit via post-commit hook*
<!-- SCORECARD:END -->

<!-- LAST_COMMIT:START -->
**Commit:** `7aa7a37` — feat: doc invariants, contract governance, and two-backlog clarity
**Date:** 2026-06-08

### Files changed
- `.cursor/rules/bob-doc-contract.mdc`
- `.cursor/rules/bob-zero-cognitive-load.mdc`
- `.github/workflows/product-verify.yml`
- `README.md`
- `docs/ARCHITECTURE_REVIEW.md`
- `docs/BOB_CHEATSHEET.md`
- `docs/CONTRACT_GOVERNANCE.md`
- `docs/DATA_LAYOUT.md`
- `docs/KT_CURSOR_AND_BOB.md`
- `docs/NEXT.md`
- `docs/ONBOARDING_DEVELOPER.md`
- `docs/README.md`
- `docs/TDD_SYSTEM_DEVELOPER_GUIDE.md`
- `docs/contract-approvals/index.yaml`
- `docs/contract-governance.yaml`
- `docs/doc-invariants.yaml`
- `docs/product-features.yaml`
- `runner/ci/verify-contract-governance.py`
- `runner/ci/verify-docs.py`
- `runner/hooks/pre-commit`
- `runner/lib/builder_cli.py`
- `runner/lib/contract_governance.py`
- `runner/lib/git_hooks.py`
- `runner/tests/test_contract_governance.py`
- `runner/tests/test_next_backlog.py`
- `runner/tests/test_verify_docs.py`
- `skills/README.md`
- `skills/builder-analyst/SKILL.md`
- `skills/builder-implementer/SKILL.md`
- `skills/builder-one-shot/SKILL.md`
- `skills/builder-verifier/SKILL.md`

### Features touched in this commit
- Core CLI entry (`cli-core`) — files touched
- Workspace setup & install (`workspace-setup`) — files touched
- Improvement backlog & reminders (`improvement-backlog`) — files touched
- Cursor builder skills (`agent-skills`) — files touched
- Feature integrity verifier (`product-verify`) — files touched

### Regression check
- **20/20 registered features still intact** after this commit (see below).
- Removing a feature requires updating `docs/product-features.yaml` and scorecard notes.
<!-- LAST_COMMIT:END -->

<!-- FEATURES_INTACT:START -->
| Feature | ID | Status |
|---------|-----|--------|
| Core CLI entry | `cli-core` | intact |
| Workspace setup & install | `workspace-setup` | intact |
| Ticket init, validate, status, reports | `ticket-lifecycle` | intact |
| Knowledge graph (platform + session) | `knowledge-graph` | intact |
| API catalog discovery | `api-discovery` | intact |
| Gradle bootRun + dynamic peer discovery | `service-boot` | intact |
| Stub registry & WireMock runtime | `stub-wiremock` | intact |
| Git branch policy (default none) | `git-branch-policy` | intact |
| Empty live BOB_HOME catalogs | `assets-empty-live` | intact |
| CC reference pack (examples only) | `examples-novopay-cc` | intact |
| Sample validate-ticket output bundle | `sample-validate-output` | intact |
| Improvement backlog & reminders | `improvement-backlog` | intact |
| Host deploy/tdd template | `host-deploy-template` | intact |
| Cursor builder skills | `agent-skills` | intact |
| PATH shim (bob on PATH) | `path-shim` | intact |
| Stale workspace cleanup | `workspace-cleanup` | intact |
| Feature integrity verifier | `product-verify` | intact |
| Evidence bundle + verify docs (DB, logs, Kafka, Redis) | `evidence-and-verify` | intact |
| Redis verify + evidence capture | `redis-verify` | intact |
| MCP-ready tool bridge (local default) | `mcp-tool-bridge` | intact |

**Total:** 20 intact, 0 missing.

Source: [`docs/product-features.yaml`](product-features.yaml) · Verifier: `runner/ci/verify-product.py`
<!-- FEATURES_INTACT:END -->

---

## Now (P0 — blocks “works for any team”)

_None open._

## Next (P1 — reusability / less CC bias)

- [ ] **Header profiles** — today single profile `dsa-agent-app`; add neutral template + example under `assets/examples/`
- [ ] **Second reference pack** — e.g. `assets/examples/novopay-payments/` when a second service dogfoods Bob; contribution flow in [CONTRIBUTING_REFERENCE_PACKS.md](CONTRIBUTING_REFERENCE_PACKS.md)

## Later (P2 — polish)

- [ ] **Windows validate-ticket** — document bash requirement; expand Python fallback parity with `run-tdd.sh`
- [ ] **Orchestration-less hosts** — discovery today requires `deploy/application/orchestration/`; support OpenAPI-only or Gradle route scan as alternative

---

## Done

| Date | Item |
|------|------|
| 2025-05-23 | **Assets split** — live `assets/` seeded empty from `runner/_seed/`; CC snapshot under `assets/examples/novopay-cc/` (52 APIs + LOC stubs) |
| 2025-05-23 | **Host detection / PATH** — `BOB_HOST_REPO`, `prompt-env.sh`, warn on stale `.local` fallback |
| 2025-05-23 | **CLI UX** — `bob help`, post-command next-step hints, `bob bobhelp` aliases |
| 2025-05-23 | **Host deploy template** — `templates/host-deploy-tdd/` for `deploy/tdd/` copy-paste |
| 2025-05-23 | **Doc scrub + CI** — neutral naming in guides; `.github/workflows/doc-lint.yml` |
| 2025-05-23 | **Dead code cleanup** — removed `kg_engine.py`, legacy `runner/tdd.sh`, duplicate `runner/assertion-catalog/` |
| 2025-05-23 | **Git branch policy** — `git.branch_policy: none \| novopay-feature`; default `none`; checkout only when explicitly enabled |
| 2025-05-23 | **Central backlog** — this file (`docs/NEXT.md`) + `bob next` |
| 2026-05-23 | **Scorecard + feature registry** — `product-features.yaml`, `bob verify-product`, CI `product-verify.yml`; auto sections in this doc |
| 2026-06-07 | **CC host glue** — `novopay-platform-creditcard-management/deploy/tdd/` synced from Bob template; README; no embedded TDD runner |
| 2026-06-07 | **Fresh install verify** — `bob verify-fresh-install` + CI; empty catalog after install, discover from non-CC fixture host ([FRESH_INSTALL_VERIFY.md](FRESH_INSTALL_VERIFY.md)) |
| 2026-06-07 | **CI smoke** — `.github/workflows/bob-smoke.yml` runs `bob install` + `bob discover-apis` on `runner/tests/fixtures/ci-host/` |
| 2026-06-07 | **`bob next --edit`** — open `docs/NEXT.md` in `$VISUAL` / `$EDITOR` (`notepad` on Windows) |
| 2026-06-02 | **Host profile + doc index** — `host_profile.py`, `bob host`, deploy/tdd setup URLs, [docs/README.md](README.md); cheatsheet + guide updates |
| 2026-06-02 | **Setup wizard env names** — `bob setup` prompts each `{SERVICE}_BASE` from deploy/tdd via `service_base_prompts()` |
| 2026-06-02 | **Host profile layer** — `runner/lib/host_profile.py`, `runner/config/bob-defaults.yaml`, `bob host`, [WORKSPACE_AND_HOST_PROFILE.md](WORKSPACE_AND_HOST_PROFILE.md) |
| 2026-06-02 | **Neutral ticket-spec schema** — `HOST_REPO_FOLDER` placeholder; CC values documented as examples |
| 2026-06-02 | **Generic discover-apis skeleton** — `host_profile.discover_api_catalog_fields()` from host repo + deploy/tdd |
| 2026-06-06 | **`bob onboard`** — one-command dev bootstrap: setup + install + squad Cursor kit; see [ONBOARDING_DEVELOPER.md](ONBOARDING_DEVELOPER.md) |
| 2026-06-06 | **`bob meta-review`** — monthly usage audit (pass rates, boot failures, rule/skill drift); suggestions only |
| 2026-06-06 | **KT doc for teammates** — [KT_CURSOR_AND_BOB.md](KT_CURSOR_AND_BOB.md) |
| 2026-06-08 | **Publish product repo** — GitHub remote live; canonical `git clone` URL in [README.md](../README.md) |
| 2026-06-08 | **Agent skill scoping** — `builder-analyst` + [skills/README.md](../skills/README.md): host ticket bundle vs Bob `NEXT.md` (product backlog only) |
| 2026-06-08 | **Two-backlog doc pass** — index/cheatsheet/KT/onboarding/TDD guide, builder skills, `bob next` product-only path, META_REVIEW stale banner |
| 2026-06-08 | **Doc invariants** — `docs/doc-invariants.yaml`, `bob verify-docs`, `bob verify-all`, CI + `.cursor/rules/bob-doc-contract.mdc` |
| 2026-06-08 | **Contract governance** — weakening YAML requires `bob contract-diff` + human `APPROVE` + `docs/contract-approvals/`; pre-commit + CI |

---

## Adding items (template)

```markdown
- [ ] **Short title** — one sentence: problem, who it affects, suggested direction
```

Keep **Now** to ≤5 items so the list stays actionable.
