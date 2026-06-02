# Bob context assembly, hybrid retrieval, and eval regression

Three upgrades (no vector DB / no MCP): smarter **context for agents**, **staleness checks**, and **scenario regression** on REPORT artifacts.

## 1. Hybrid retrieval (replaces plain keyword slice)

**What:** Ranks platform graph APIs, processors, stubs, API catalog YAML, and session tickets by lexical overlap with your query + ticket `impacted` fields. Top API hits **expand** to linked processor nodes (one graph hop).

**Commands:**

```bash
bob query-graph getLOCOffers loanOffers
bob query-graph --ticket adhoc-loc-dummy-jumbo-eligibility
```

**Output:** `bob-the-builder/local/agent/kg-context-last.md`

**On validate-ticket:** Built automatically inside `CONTEXT_PACK.md`.

## 2. Context assembly (preferences + stale detection)

**What:** Before stubs/APIs, Bob writes `docs/tdd-runs/<ticket>/CONTEXT_PACK.md` with:

| Section | Content |
|---------|---------|
| Preferences | Primary `{SERVICE}_BASE` vars, `LOGS_DIR`, Redis, Kafka, workspace paths from `user.env` |
| Staleness | Orchestration newer than `sync-graph`, spec newer than graph, branch/ticket mismatch, empty catalog, missing primary base URL |
| Hybrid retrieval | Ranked hits (same as `query-graph`) |

**Commands:**

```bash
bob context --ticket <ticket-id>
```

**Agent copy:** `local/agent/context-pack-last.md`

**Disable staleness fail:** Only `error` severity (e.g. missing `CC_BASE`) fails the `context_assembly` step; warnings are listed but pass.

## 3. Eval regression on REPORT / run-summary

**What:** Snapshot scenario PASS/FAIL in `eval-baseline.json`. Later runs compare `run-summary.json` and write `EVAL_REGRESSION.md`. Regressions (was PASS, now FAIL) can fail the ticket when `run.eval.mode` is `check`.

**Commands:**

```bash
bob eval baseline <ticket-id>   # after a green run you trust
bob eval check <ticket-id>        # compare last run-summary to baseline
bob eval update <ticket-id>     # refresh baseline from current run-summary
```

**ticket-spec:**

```yaml
run:
  eval:
    mode: check              # off | check | baseline | update-on-pass
    fail_on_regression: true
    auto_baseline_on_first_pass: true
```

| mode | Behavior |
|------|----------|
| `check` (default) | Compare to baseline; fail if regressions |
| `off` | Skip |
| `baseline` | Always overwrite baseline at end of run |
| `update-on-pass` | Update baseline only when overall PASS |

## validate-ticket artifacts (per ticket)

| File | Purpose |
|------|---------|
| `CONTEXT_PACK.md` | Prefs + stale + hybrid KG |
| `EVAL_REGRESSION.md` | Baseline comparison |
| `eval-baseline.json` | Machine-readable snapshot |
| `kg-context-last.md` | Agent slice (in BOB_LOCAL) |

## Not included (by design)

- **MCP tools** — deferred; use `bob` CLI and skills
- **FAISS / embeddings** — lexical + graph expansion only; enough for API/processor topology

## See also

- [GRAPH_OBSIDIAN.md](GRAPH_OBSIDIAN.md) — visual graph in Obsidian
- [WORKSPACE_AND_HOST_PROFILE.md](WORKSPACE_AND_HOST_PROFILE.md) — host profile and setup URLs
- [README.md](README.md) — full doc index
- [TDD_SYSTEM_DEVELOPER_GUIDE.md](TDD_SYSTEM_DEVELOPER_GUIDE.md) — full validate flow
