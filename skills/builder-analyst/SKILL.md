---
name: builder-analyst
description: >-
  Bob the Builder — analyst: query-graph, discover-apis, ticket-spec + TEST_PLAN.
  Read-only on product code. Never git commit/push. No validate-ticket.
disable-model-invocation: true
---

# Builder analyst (read-only)

**Do not implement or run validate-ticket. Never `git commit` or `git push`.**

## What to read first (scope)

| You are scoping… | Read first (host repo paths unless noted) |
|------------------|-------------------------------------------|
| **A host ticket** (CC, payments, adhoc slug) | `docs/tdd-runs/<id>/ticket-spec.yaml`, `TEST_PLAN.md`, `CONTEXT_PACK.md` if present, `TICKET_RESUME.md` when resuming, `GATE_SUMMARY.md` for gate status |
| **Bob product work** (engine in `bob-the-builder/`) | `bob-the-builder/docs/NEXT.md` (`bob next`) — product backlog only; not ticket scope |

Do **not** use Bob's `docs/NEXT.md` for host-ticket Plan/Build/Prove/Ship — it tracks Bob-the-tool improvements, not your ticket.

1. `bob host` if workspace/host is unclear
2. `bob query-graph <keywords>` or `bob context --ticket <id>` after ticket exists
3. Read `{BOB_LOCAL}/agent/kg-context-last.md`, ticket `CONTEXT_PACK.md` if present, `{BOB_HOME}/platform-graph/platform-graph.yaml`
4. `bob discover-apis` if new gateway APIs; `bob sync-graph` when orchestration/processors change
5. `bob init-ticket <id> "<title>"` — **id is any slug** (Jira optional); for informal reqs use `adhoc-<topic>` (see host repo `.cursor/skills/bob-adhoc-requirement`)
6. Fill `docs/tdd-runs/<id>/ticket-spec.yaml` + `TEST_PLAN.md` from user requirement text when no formal ticket exists (`env_profile` must match host `deploy/tdd/env-*.yaml`)
7. When the flow touches messaging or cache: set `evidence_required` (`kafka`, `redis` as needed) and `run.kafka.mode` / `run.redis.mode` — see Bob `docs/EVIDENCE_AND_VERIFY.md`

Pair: `builder-implementer`, `builder-verifier`
