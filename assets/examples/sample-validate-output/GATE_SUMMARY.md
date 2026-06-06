# Orchestrator gates: sample-gateway-health-check

_One page for the human orchestrator. Bob fills auto status; you check the boxes._

**Summary:** One or more gates need attention before Ship

| # | Gate | Bob (auto) | Detail | Evidence | You approve |
|---|------|------------|--------|----------|-------------|
| 1 | **Plan** | **PASS** | 2 scenario(s), 2 acceptance criteria | [ticket-spec.yaml](./ticket-spec.yaml) | [TEST_PLAN.md](./TEST_PLAN.md) | [x] |
| 2 | **Build** | **REVIEW** | no unit scenarios; e2e/integration only | pipeline steps in REPORT.md | [ ] |
| 3 | **Prove** | **PASS** | overall PASS; 2/2 scenarios passed | scenario table below | [run-summary.json](./run-summary.json) | [x] |
| 4 | **Ship** | **REVIEW** | review upstream gates first | commit/PR only when you check this box | [ ] |

## What you decide at each gate

1. **Plan** — Scope and acceptance criteria match what you want built.
2. **Build** — Implementation approach and unit compile/test evidence look right.
3. **Prove** — Bob PASS is enough proof for this ticket (not just unit-only).
4. **Ship** — OK to commit and open PR.

Full evidence: [REPORT.md](./REPORT.md)
