# Bob the Builder — what to improve next

**Living backlog.** Update this file after audits, dogfooding, or team feedback — not only in chat or PR comments.

| | |
|---|---|
| **Read** | Before picking up Bob product work |
| **Update** | When something ships → move it to **Done** with date; when you find a gap → add under **Now** / **Next** / **Later** |
| **Verify** | You don't — say **commit** or **push** in Cursor; agent runs `bob remind --fix`. Bob auto-refreshes stale `docs/NEXT.md` after most commands. |
| **CI** | Blocks only if a **feature was removed** — not stamp drift |
| **CLI** | `bob next` · `bob verify-product` |

<!-- PRODUCT-VERIFY:COMMIT=8d17df1 -->
<!-- PRODUCT-VERIFY:CHECKED=2026-06-03 -->

<!-- SCORECARD:START -->
## Current scorecard

> **Manual grades** — update the table when reality changes. **Feature integrity** is auto-checked every CI push.

| Dimension | Grade | Notes |
|-----------|-------|-------|
| Product vs host separation | A | Engine in `bob-the-builder/` only |
| End-to-end TDD loop | A- | Ticket spec → validate → evidence |
| Reusability / generic story | B+ | Empty `assets/`; CC in `examples/`; engine defaults still Novopay-shaped |
| Repo cleanliness | A- | Dead code removed; staged for first publish |
| Docs & operability | A- | Guides, cheatsheet, `bob next`, this scorecard |
| Team handoff | B+ | First commit + remote remaining (P0) |
| **Overall** | **Architecture PASS · Product B+ · one commit from ship** | |

*Last feature check: 2026-06-03 · commit `8d17df1` · 18/18 features intact · auto-refreshed after commit via post-commit hook*
<!-- SCORECARD:END -->

<!-- LAST_COMMIT:START -->
**Commit:** `8d17df1` — feat: add MCP-ready tool bridge with local-first default
**Date:** 2026-06-03

### Files changed
- `docs/BOB_CONTEXT_AND_EVAL.md`
- `docs/MCP_TOOL_BRIDGE.md`
- `docs/README.md`
- `docs/product-features.yaml`
- `runner/config/mcp-servers.yaml`
- `runner/config/tool-bridge.yaml`
- `runner/lib/builder_cli.py`
- `runner/lib/context_assembly.py`
- `runner/lib/mysql_runner.py`
- `runner/lib/run_summary.py`
- `runner/lib/tool_bridge/__init__.py`
- `runner/lib/tool_bridge/local_handlers.py`
- `runner/lib/tool_bridge/mcp_client.py`
- `runner/lib/tool_bridge/registry.py`
- `runner/lib/tool_bridge/router.py`
- `runner/lib/tool_bridge/types.py`
- `runner/mcp/bob_tools_server.py`

### Features touched in this commit
- Core CLI entry (`cli-core`) — files touched
- Ticket init, validate, status, reports (`ticket-lifecycle`) — files touched
- Feature integrity verifier (`product-verify`) — files touched
- MCP-ready tool bridge (local default) (`mcp-tool-bridge`) — files touched

### Regression check
- **18/18 registered features still intact** after this commit (see below).
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
| MCP-ready tool bridge (local default) | `mcp-tool-bridge` | intact |

**Total:** 18 intact, 0 missing.

Source: [`docs/product-features.yaml`](product-features.yaml) · Verifier: `runner/ci/verify-product.py`
<!-- FEATURES_INTACT:END -->

---

## Now (P0 — blocks “works for any team”)

- [ ] **Publish product repo** — initial commit + GitHub remote; document clone URL in README
- [ ] **Host glue template in CC (optional)** — if CC team uses Bob again: copy `templates/host-deploy-tdd/` → `deploy/tdd/` without shipping `tools/tdd-runner/` in the service repo
- [ ] **Verify fresh install story** — `bob install` on a clean clone → empty `assets/api-catalog`, discover from a non-CC host repo works end-to-end

## Next (P1 — reusability / less CC bias)

- [x] **Neutral ticket-spec schema** — `HOST_REPO_FOLDER` placeholder; CC values documented as examples (2026-06-02)
- [x] **Generic discover-apis skeleton** — `host_profile.discover_api_catalog_fields()` from host repo + deploy/tdd (2026-06-02)
- [x] **Host profile layer** — `runner/lib/host_profile.py`, `runner/config/bob-defaults.yaml`, `bob host`, `docs/WORKSPACE_AND_HOST_PROFILE.md` (2026-06-02)
- [x] **Setup wizard env names** — `bob setup` prompts each `{SERVICE}_BASE` from deploy/tdd via `service_base_prompts()` (2026-06-02)
- [ ] **Header profiles** — today single profile `dsa-agent-app`; add neutral template + example under `assets/examples/`
- [ ] **Second reference pack** — e.g. `assets/examples/novopay-payments/` when a second service dogfoods Bob (proves the empty-catalog model)

## Later (P2 — polish)

- [ ] **Windows validate-ticket** — document bash requirement; expand Python fallback parity with `run-tdd.sh`
- [ ] **Orchestration-less hosts** — discovery today requires `deploy/application/orchestration/`; support OpenAPI-only or Gradle route scan as alternative
- [ ] **CI beyond doc-lint** — smoke `bob install` + `bob discover-apis` against a fixture host in GitHub Actions
- [ ] **`bob next --edit`** — open this file in `$EDITOR` (optional convenience)
- [ ] **Agent skill pointer** — builder-analyst skill should cite `docs/NEXT.md` when scoping work

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
| 2026-06-02 | **Host profile + doc index** — `host_profile.py`, `bob host`, deploy/tdd setup URLs, [docs/README.md](README.md); cheatsheet + guide updates |

---

## Adding items (template)

```markdown
- [ ] **Short title** — one sentence: problem, who it affects, suggested direction
```

Keep **Now** to ≤5 items so the list stays actionable.
