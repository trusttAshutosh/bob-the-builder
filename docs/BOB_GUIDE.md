# Bob the Builder - team guide (everything in one place)

**Audience:** Teammates, KT sessions, and anyone presenting how the squad works.  
**Use this doc alone** for "what is Bob, why it exists, how to use it." Deep internals and per-topic runbooks are listed only in the appendix at the end.

---

## 1. What Bob is (and is not)

| | Bob | Cursor (IDE + agent) |
|---|-----|----------------------|
| **What it is** | Python CLI (`bob.py`) + ticket layout + local proof engine | Agent that plans, writes Java, drafts specs, runs Gradle tests |
| **What it is not** | A second AI, a code generator, or a replacement for thinking | A standardized boot + WireMock + evidence pipeline |
| **Typical output** | `REPORT.md`, `GATE_SUMMARY.md`, `evidence/` under the host repo | Code, unit tests, `ticket-spec.yaml`, `TEST_PLAN.md` |
| **Who runs it** | You or the agent via terminal: `bob validate-ticket <id>` | Chat in Cursor |

**One sentence:** Cursor builds; Bob proves the same way every time.

Bob lives in **`bob-the-builder/`** only. Service repos (e.g. credit-card-management) hold ticket folders under `docs/tdd-runs/<ticket-id>/` - they do not ship the engine.

---

## 2. Why Bob exists - original intent

**Problem:** Backend tickets need repeatable local proof - correct gateway APIs, bank/partner stub behavior, DB rows, logs, Kafka/Redis when in scope - without manual Postman + grep + SQL every time.

**Solution we built:**

1. **Raw requirement** (thoughts, Jira, email) → structured **`ticket-spec.yaml`** + **`TEST_PLAN.md`** in the host repo.
2. **Implement** on a feature branch (Cursor + you).
3. **`bob validate-ticket`** - boot Novopay peers, WireMock for bank/HDFC, hit APIs, run DB/log/Kafka/Redis checks, write evidence.
4. **You** review **`GATE_SUMMARY.md`** (Plan / Build / Prove / Ship) and ship when satisfied.

**Bank rule:** HDFC/partner APIs stay on **WireMock** - Bob never bootRuns the real bank.

That was the full TDD loop we designed. It is still the recommended path for non-trivial tickets.

---

## 3. Was Bob required if Cursor is enough?

| Need | Cursor alone | Bob |
|------|--------------|-----|
| Understand requirement, write Java | Yes | No |
| Unit tests (`gradle test`) | Yes (when you ask) | Opt-in via `run.unit_tests: true`; **not** default proof |
| WireMock bank APIs in a repeatable run | Painful / manual | **Core Bob** |
| Boot CC + peers + same proof every time | Manual | **Core Bob** |
| `REPORT.md` / `GATE_SUMMARY` for the squad | No standard | **Core Bob** |

**Conclusion:** Bob was not redundant for bank mimicry + standardized local proof. It was never meant to replace thinking and coding - that was always Cursor (+ you).

---

## 4. Three roles - orchestrator model

```
You (orchestrator) - approve only 4 gates
  Gate 1 Plan     -> scope, tickets, open questions
  Gate 2 Build    -> skim diff vs intent
  Gate 3 Prove    -> Bob GATE_SUMMARY.md + REPORT.md
  Gate 4 Ship     -> commit / PR when you approve

Cursor agent  -> plans, codes, reviews; may run Bob when asked
Bob CLI       -> validate-ticket: boot, stubs, scenarios, evidence
AGENTS.md     -> durable squad memory (not chat history)
```

**Bob is not redundant with Cursor.** Cursor does not replace booting Gradle services, applying WireMock mappings, DB asserts, and PASS/FAIL reports the whole team can read.

---

## 5. Full Bob TDD vs minimal Bob

Both are valid. The difference is **when** you write the spec and **how often** you prove.

### Full Bob TDD (recommended for non-trivial work)

```text
raw thoughts
  -> (Cursor) ticket-spec.yaml + TEST_PLAN.md + GATE_SUMMARY stub
  -> (Cursor) code + unit tests on feature branch
  -> (Bob) validate-ticket -> evidence/ + REPORT.md
  -> (you) GATE_SUMMARY gates -> ship
```

**When to use:** New flows, bank stub behavior, multi-service boot, regression-sensitive changes, anything QA will ask "show me proof."

**Cursor phrases that help:**

- *"Plan only: init adhoc-foo, no code yet"*
- *"Fill ticket-spec from this requirement; use builder-analyst playbook"*
- *"Implement from ticket-spec; then bob validate-ticket adhoc-foo"*

### Minimal Bob (common in practice)

```text
(Cursor) implement from chat / Jira (maybe light ticket folder)
  -> (Bob) validate-ticket when you want proof
  -> (you) skim GATE_SUMMARY / REPORT
```

**When to use:** Small fixes, spikes, or when you already know the scenario list and just need a proof run.

**Gap to be aware of:** Code-first without `ticket-spec` means Bob has less to run until someone fills the spec. Minimal Bob is fine; **full Bob TDD** is what gives you spec-first review and repeatable scenarios for the squad.

### What does *not* happen automatically

- Typing **"bob"** in chat does not switch modes or run `validate-ticket`.
- **`builder-analyst` / `builder-implementer` / `builder-verifier`** are Cursor skill playbooks (`disable-model-invocation: true`) - they are not auto-on; invoke them explicitly or ask the agent to follow them.
- **"bob let's test"**, **"validate"**, or **"test this ticket"** (or explicit `bob validate-ticket`) ≈ E2E prove step - still needs a ticket id and folder under `docs/tdd-runs/<id>/`. Do not substitute `gradle test` unless the user explicitly asks for unit tests.

---

## 6. Builder skills (Cursor playbooks, not Bob)

These live in `bob-the-builder/skills/` and load when Bob is in the workspace:

| Skill | Agent job |
|-------|-----------|
| `builder-analyst` | Raw text → `ticket-spec.yaml`, `TEST_PLAN.md`, gate stub; no product code |
| `builder-implementer` | Implement from spec; unit tests; no commit unless you ask |
| `builder-verifier` | Run / interpret `validate-ticket`; update gate evidence narrative |

Squad skills from `bob onboard` (ticket-breakdown, cc-backend-test-generation, etc.) live in `{workspace}/.cursor/skills/` - separate from builder-* but same idea: **playbooks for the agent**, not separate bots.

---

## 7. What was built - repo and ticket layout

### Bob engine repo

```text
bob-the-builder/
  bob.py              # CLI entry
  runner/             # Python + shell engine
  assets/             # api-catalog, stub-registry, platform graph (seeded on install)
  local/              # gitignored - user.env, WireMock, agent session
  skills/             # builder-* Cursor skills
  docs/               # this guide + cheatsheet + internals
```

### Per-ticket folder (host service repo)

```text
<host>/docs/tdd-runs/<ticket-id>/
  ticket-spec.yaml    # scenarios Bob runs
  TEST_PLAN.md        # human QA narrative
  GATE_SUMMARY.md     # your 4-gate checklist
  REPORT.md           # Bob proof summary
  evidence/
    api/ db/ logs/ kafka/ redis/ ...
  TICKET_RESUME.md    # optional - continue in a fresh chat
```

**Two backlogs (do not mix):**

| Backlog | Path | Scope |
|---------|------|--------|
| **Host ticket** | `<host>/docs/tdd-runs/<id>/` | Your feature work |
| **Bob product** | `bob-the-builder/docs/NEXT.md` | Improving Bob itself (`bob next`) |

---

## 8. Setup (first machine)

**Prerequisites:** Git, Python 3, JDK 21, MySQL (default `root`/`root`), Cursor 2.5+.

**Layout:** One parent folder (e.g. `Desktop/novopay/`) with clones:

```text
novopay/
  bob-the-builder/
  novopay-platform-creditcard-management/   # example host
  novopay-platform-lib/
  novopay-platform-api-gateway/             # optional peers
  novopay-platform-actor/
```

**One command after clone:**

```bash
cd bob-the-builder
python bob.py onboard
```

Creates: `AGENTS.md`, workspace skills/rules, `novopay.code-workspace`, orchestrator rule, `local/user.env`, plugin checklist. You do **not** run `setup` + `install` separately on first use.

**Verify:**

```bash
python bob.py memory-budget
python bob.py validate-ticket sample-gateway-health-check
```

Optional plugins (Superpowers, Team Kit, Continual Learning): `bob plugins` - Bob cannot click Install for you.

---

## 9. Daily workflow

| Step | Who | Action |
|------|-----|--------|
| Plan | You + Cursor | `ticket-spec.yaml`, scope, open questions |
| Build | Cursor | Java + tests; no commit unless you ask |
| Prove | Bob | `bob validate-ticket <id>` |
| Review | **You** | `GATE_SUMMARY.md` + `REPORT.md` |
| Ship | You | commit / PR when Gate 4 approved |

**Common commands:**

```bash
cd novopay-platform-creditcard-management   # or your host repo
bob init-ticket MY-123 "Short title"
bob discover-apis
bob validate-ticket MY-123
bob open-report MY-123
bob ticket-status MY-123
```

First `bob` use adds `local/bin` to PATH (plus flat shims for hyphenated commands). Until then: `python bob.py <cmd>` or `.\bob.cmd <cmd>` from `bob-the-builder/`. If commands fail: `bob doctor` or `bob path-shim --force`, then open a **new** terminal.

**Service boot:** `validate-ticket` can auto-boot peers (`run.auto_boot_services: true` by default). Bank stays WireMock. If services are already up but **git shows `.java` / `.xml` / `.properties` changes** in the ticket flow (including platform-lib), Bob **restarts** those boot targets so API proof hits fresh code; with no code changes, healthy services are reused for faster "test again" runs. See commands: `bob ensure-peers`, `bob services-status`, `bob stop-services`.

---

## 10. What `validate-ticket` does (proof pipeline)

At a high level:

1. Read **`ticket-spec.yaml`** (APIs, stubs, DB/log/Kafka/Redis scenarios).
2. Ensure WireMock mappings for bank/partner calls.
3. Boot required Novopay services (discovered from code + profile).
4. Run **E2E** scenarios first (HTTP, SQL, log grep, optional Kafka/Redis). Gradle unit tests run only when `run.unit_tests: true` in ticket-spec.
5. Write **`evidence/`**, **`REPORT.md`**, update gate-oriented summaries.

You bring **MySQL** (and Redis/Kafka when the ticket needs them). Evidence paths and verify doc names are standardized so any teammate can review without watching your terminal.

---

## 11. Memory and chat hygiene (squad habits)

| System | Role |
|--------|------|
| `AGENTS.md` | Learned prefs + facts (Continual Learning) |
| `novopay-orchestrator.mdc` | Hard rules - you approve gates only |
| `TICKET_RESUME.md` | Pause / resume a ticket in a fresh chat |
| `bob memory-budget` | Keep active ticket chats under ~60% context |

**Sidebar target:** ~6-8 active chats (pinned + today + yesterday). Archive stale chats; do not delete history you might need.

**Monthly:** stop hook may run `bob meta-review` - suggestions only; you approve rule/skill changes.

---

## 12. FAQ (presentation-ready)

**Q: Why not only Cursor + Gradle tests?**  
A: Unit tests do not boot real services, apply WireMock bank behavior, or produce a squad-standard evidence bundle with DB/log proof.

**Q: Why GATE_SUMMARY?**  
A: One page for Plan / Build / Prove / Ship so you approve outcomes, not tooling steps.

**Q: Can I use Bob on non-CC services?**  
A: Yes - set `BOB_HOST_REPO` and copy `templates/host-deploy-tdd/` into the host repo.

**Q: What if boot fails?**  
A: Fix belongs in Bob boot/remediation or local env - encode fixes in Bob so the squad does not re-debug every session.

**Q: Does Bob commit or push?**  
A: Never. You own git.

**Q: Where is the product backlog for Bob itself?**  
A: `bob-the-builder/docs/NEXT.md` (`bob next`) - not the same as host ticket folders.

---

## 13. Appendix - specialist docs (optional depth)

Use these only when you need more detail than this guide:

| Topic | Doc |
|-------|-----|
| Command reference | [BOB_CHEATSHEET.md](BOB_CHEATSHEET.md) |
| Machine setup walkthrough | [ONBOARDING_DEVELOPER.md](ONBOARDING_DEVELOPER.md) |
| Runner architecture + mermaid | [TDD_SYSTEM_DEVELOPER_GUIDE.md](TDD_SYSTEM_DEVELOPER_GUIDE.md) |
| Evidence subdirs | [EVIDENCE_AND_VERIFY.md](EVIDENCE_AND_VERIFY.md) |
| Another Novopay service | [ADOPTING_BOB_FOR_ANOTHER_SERVICE.md](ADOPTING_BOB_FOR_ANOTHER_SERVICE.md) |
| Runner modules | [../runner/ARCHITECTURE.md](../runner/ARCHITECTURE.md) |
| Bob product backlog | [NEXT.md](NEXT.md) |

**Clone + onboard quick link:** [../README.md](../README.md)
