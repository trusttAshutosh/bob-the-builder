# Cursor plugins for Novopay + Bob

Bob cannot install Cursor marketplace plugins for you. Install these once per
machine so agents can use the skills and slash-commands referenced in this repo.

Bob, `novopay-orchestrator.mdc`, and `.cursor/skills/` work without plugins.
Plugins add structured **Plan**, **review/CI**, and **memory** on top of Bob proof.

## How to install

1. Open **Cursor** > **Extensions** (marketplace).
2. Search each plugin name below.
3. Click **Install**.
4. Reload Cursor if prompted.

Re-show this list in terminal: `bob plugins`

## Recommended

### Superpowers

**Marketplace search:** `superpowers`

Plan and prove discipline before and after Bob runs.

**Helps with workflows in this repo:**
- Gate 1 Plan: /brainstorming and /writing-plans before you code
- Gate 3 Prove: /verification-before-completion after bob validate-ticket
- Complements .cursor/skills/ticket-breakdown-planning (Jira-ready breakdown)

### Cursor Team Kit

**Marketplace search:** `cursor team kit`

Review, CI, and ship skills for Gate 4 and PR hygiene.

**Helps with workflows in this repo:**
- Gate 4 Ship: /review-and-ship, /new-branch-and-pr, /make-pr-easy-to-review
- CI loops: /fix-ci and /loop-on-ci when checks fail
- Quality pass: /thermo-nuclear-code-quality-review before large diffs

### Continual Learning

**Marketplace search:** `continual learning`

Keeps AGENTS.md in sync so Bob sessions do not re-learn prefs every chat.

**Helps with workflows in this repo:**
- Updates novopay/AGENTS.md on agent stop (Learned sections)
- Works with weekly /workflow-from-chats hygiene from the orchestrator stop hook
- Pairs with ~/.cursor/rules/novopay-orchestrator.mdc (hard rules stay separate)

## Optional

### Postman

**Marketplace search:** `postman`

Only if you use Postman Cloud; Bob already writes local collections per ticket.

- Optional cloud sync for collections Bob generates under docs/tdd-runs/<id>/postman/
- Not required for bob validate-ticket or local TDD

## Novopay skills (no plugin required)

Canonical skills live at `.cursor/skills/`:

| Skill | Use when |
|-------|----------|
| `ticket-breakdown-planning` | Jira-ready breakdown, epic vs story |
| `cc-backend-test-generation` | CC unit/journey tests |
| `generate-test-plan-change-flow-based` | QA test plans with API + DB matrices |

See also: [KT_CURSOR_AND_BOB.md](../docs/KT_CURSOR_AND_BOB.md)
