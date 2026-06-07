# Knowledge transfer: Cursor + Bob + Novopay workflow

**Audience:** Teammates onboarding to how this squad works (idea → proof → ship).  
**Owner:** Squad; update when workflow changes.  
**Bob's role:** Proof engine. **Cursor's role:** Plan, build, review. **Human role:** Orchestrator (4 gates).

---

## 1. The model in one picture

```
Human (orchestrator)
  ├─ Gate 1 Plan     → scope, tickets, open questions
  ├─ Gate 2 Build    → skim diff vs intent
  ├─ Gate 3 Prove    → Bob GATE_SUMMARY.md + REPORT.md
  └─ Gate 4 Ship     → commit / PR when you approve

Cursor agent          → plans, codes, reviews, runs Bob
Bob validate-ticket   → boots services, runs scenarios, writes evidence
AGENTS.md + rules     → durable memory (not chat history)
```

**Bob is not redundant.** Cursor does not replace booting Gradle services, WireMock, DB asserts, and PASS/FAIL reports.

**Cursor vs Bob (read this first):** [README.md](../README.md#cursor-vs-bob) — Cursor plans and implements; Bob CLI proves from `ticket-spec.yaml`. Builder skills are Cursor playbooks, not a separate bot. Typing "bob" in chat does not auto-run the full loop.

---

## 2. What to install (Cursor)

| Piece | Purpose | Required? |
|-------|---------|-----------|
| **Cursor** 2.5+ | IDE + agent | Yes |
| **Plugins:** Superpowers, Cursor Team Kit, Continual Learning | Process, review, memory | Recommended - see [CURSOR_PLUGINS.md](CURSOR_PLUGINS.md) or `bob plugins` |
| **Postman plugin** | Cloud API sync | Optional (Bob local collections are default) |
| **User rule** | `~/.cursor/rules/novopay-orchestrator.mdc` | Yes (`bob onboard`) |
| **Workspace skills** | `{workspace}/.cursor/skills/` | Yes (`bob onboard`) |
| **Workspace rules** | `{workspace}/.cursor/rules/` | Yes (`bob onboard`) |
| **Workspace** | Open `novopay.code-workspace` or `Desktop/novopay` | Yes |

Plugins alone do nothing until **rules + workspace + Bob** are wired.

---

## 3. What to install (Bob)

```bash
cd bob-the-builder
python bob.py setup      # workspace root, MySQL creds, host repo
python bob.py install    # seed assets/local
python bob.py install-hooks   # optional: NEXT.md refresh on commit
```

**Prereqs:** JDK, Gradle, MySQL (local), git clones under one parent folder (`Desktop/novopay` layout).

See [TDD_SYSTEM_DEVELOPER_GUIDE.md](TDD_SYSTEM_DEVELOPER_GUIDE.md) and [BOB_CHEATSHEET.md](BOB_CHEATSHEET.md).

---

## 4. Daily workflow

| Step | Who | Command / artifact |
|------|-----|-------------------|
| Plan ticket | Human + agent | `ticket-breakdown-planning` skill → `docs/.../ticket-spec.yaml` |
| Implement | Agent | No commit unless you ask |
| Prove | Bob | `bob validate-ticket <id>` |
| Review | **You** | `docs/tdd-runs/<id>/GATE_SUMMARY.md` (4 checkboxes) |
| Ship | You + agent | commit / PR when Gate 4 approved |

---

## 5. Memory, chat hygiene, and working memory budget

| System | What it remembers | Your habit |
|--------|-------------------|------------|
| `AGENTS.md` (novopay root) | Learned prefs + facts | Let Continual Learning update it |
| `novopay-orchestrator.mdc` | Hard rules (always on) | Rarely edit |
| `memory-budgeting.mdc` | Context load rules (always on) | Deployed via `bob onboard` |
| `.cursor/skills/` (novopay) | Ticket/test skills | Edit canonical copy only |
| `TICKET_RESUME.md` per ticket | Continue in fresh chat | Update when pausing a ticket |
| Chat archive | Raw history | **Archive > delete**; delete only noise |

**Sidebar target:** pinned + today + yesterday at ~6-8 active chats combined. **Context target:** active ticket chats under ~60% (`bob memory-budget`).

| Cadence | Automation | What happens |
|---------|------------|--------------|
| Session start | `bob-hook-runner.sh session` | Auto-archive + refresh `.cursor/memory-budget-status.json` |
| Weekly stop hook | `bob-hook-runner.sh stop` | `/workflow-from-chats` reminder + archive nudge (never delete) |
| Monthly stop hook | `bob-hook-runner.sh stop` | Auto `bob meta-review` when 30d due (boot/plugins/context audit) |
| Manual | `bob memory-budget` | Full report at `docs/MEMORY_BUDGET.md` |
| Manual | `bob chat-hygiene --dry-run` | Preview stale/overflow archives before applying |

Weekly hygiene (automatic): workflow-from-chats merge into `AGENTS.md`.

Monthly audit: stop hook auto-runs `bob meta-review --hook stop` every 30 days (or run manually). Writes [META_REVIEW.md](META_REVIEW.md) and [CONTEXT_USAGE_AUDIT.md](CONTEXT_USAGE_AUDIT.md) (suggestions only). Human approves any rule/skill/Bob changes; use `bob onboard --force` only for orchestrator rule sync.

---

## 6. Key paths

| Path | What |
|------|------|
| `Desktop/novopay/novopay.code-workspace` | Multi-repo Cursor workspace |
| `Desktop/novopay/AGENTS.md` | Agent memory |
| `Desktop/novopay/.cursor/skills/` | Canonical skills |
| `bob-the-builder/` | Bob engine |
| `<host>/docs/tdd-runs/<ticket>/` | Per-ticket evidence |
| `<ticket>/GATE_SUMMARY.md` | Your review checklist |
| `docs/tdd-runs/<ticket>/TICKET_RESUME.md` | Fresh-chat resume + memory budget for that ticket |
| `{workspace}/.cursor/memory-budget-status.json` | Session hook status (warn/critical) |

---

## 7. Commands cheat sheet

```bash
bob setup
bob init-ticket <id> "Title"
bob validate-ticket <id>
bob memory-budget
bob open-report <id>        # GATE_SUMMARY, REPORT, paths — ticket "what's next"
bob ticket-status <id>
bob next                     # Bob product backlog only (bob-the-builder/docs/NEXT.md)
```

Cursor slash skills (when relevant): `/verification-before-completion`, `/thermo-nuclear-code-quality-review`, `/workflow-from-chats`.

---

## 8. FAQ for KT sessions

**Q: Why not only Cursor tests?**  
A: Bob boots real services, applies stubs, checks DB/logs, and produces a standard evidence bundle the whole squad can read.

**Q: Why GATE_SUMMARY?**  
A: One page for Plan/Build/Prove/Ship so the human only approves gates, not tooling.

**Q: Can I use Bob on non-CC services?**  
A: Yes — [ADOPTING_BOB_FOR_ANOTHER_SERVICE.md](ADOPTING_BOB_FOR_ANOTHER_SERVICE.md).

**Q: What if Bob boot fails?**  
A: Boot fixes belong in Bob (`service_boot`, `boot_remediation`); don't re-prompt the same fixes every session.

---

## 9. Related docs

- [ONBOARDING_DEVELOPER.md](ONBOARDING_DEVELOPER.md) — machine setup + planned one-command bootstrap
- [README.md](README.md) — doc index
- [NEXT.md](NEXT.md) — Bob product backlog and scorecard
