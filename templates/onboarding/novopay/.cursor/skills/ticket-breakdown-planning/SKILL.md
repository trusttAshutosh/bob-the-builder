---
name: ticket-breakdown-planning
description: Break down epics or features into Jira-ready work items with Product ticket body, Engineering reference, QA reference, journey impact tables, <=4h estimation slices, and justification. Judges Epic vs Story vs subtasks before splitting. Use when user asks to create tickets, split tickets, sub-tasks, estimate work, sprint planning, or plan breakdown in data-purging/remarketing style for Novopay backend flows.
---

# Ticket Breakdown and Estimation Planning (Novopay Style)

## When To Use

Use when the user asks to:

- Break down a ticket / epic / feature into sub-tickets
- Create Jira-ready ticket text (Product + Engg + QA comments)
- Estimate work in **<=4 hour** slices with justification
- Plan sprint delivery order and dependencies
- Produce plans matching **data-purging** or **remarketing** format

Canonical format references (read when available):

- Data-purging style: `%USERPROFILE%\.cursor\plans\dsa_lead_lifecycle_tickets_02a51237.plan.md`
- Remarketing SMS style: `%USERPROFILE%\.cursor\plans\cc_remarketing_subtickets_47faa95c.plan.md`
- Technical depth (test matrices): `%USERPROFILE%\.cursor\plans\cc_remarketing_sms_batch_ddadc85b.plan.md`

Detailed copy-paste templates: [templates.md](templates.md)  
Worked examples: [examples.md](examples.md)

---

## Inputs Required

If missing, ask (use AskQuestion when available):

1. **Source material**: PRD snippet, product UD, raw notes, existing Jira, or conversation decisions
2. **Scope**: single feature vs full epic breakdown
3. **Target**: Jira hierarchy (Epic vs Story vs subtasks only) - apply judgment below if user does not specify
4. **Deliverable**: sub-ticket stories only, or also main/parent ticket text
5. **Estimation unit**: hours (default), story points only if user requests
6. **Max slice size**: default **4 hours** per subtask row
7. **Modules/services** affected (for Engg/QA flow map)
8. **Branch baseline** (default: backend `ddp-prod`, frontend `dsa-prod` when UI touched)

Optional but valuable:

- Locked decisions already agreed (reduces rework)
- Open questions for Product sign-off (blockers vs non-blockers)

---

## Core Rules

1. **Content differs, format stays the same** - adapt wording to the feature; never drop sections from the template.
2. **Every slice gets all blocks** - Product ticket, Engineering reference, QA reference (as separate Jira comments or subtask bodies). For **1 Story + subtasks**, one Product body on the parent is enough; Engg/QA can live on the Story or per subtask.
3. **Journeys impacted is always a 3-column table**: `Journey | Who | What changes`.
4. **Estimation is always a 3-column table**: `Subtask | Est (hrs) | Why this size / justification`.
5. **Subtasks must be <=4h** unless user explicitly allows larger slices.
6. **Separate policy/foundation from delivery** when risk is high (eligibility, schema, config before batch/send paths).
7. **No existing MIS/report contract changes** unless user explicitly includes reporting work - use separate remarketing audit / tracking instead.
8. **Mark assumptions** as `ASSUMPTION` until Product confirms.

---

## Workflow

### Step 1 - Ingest and normalize requirements

Extract and label:

| Label | Meaning |
| --- | --- |
| **LOCKED** | Agreed in discussion or UD |
| **OPEN** | Needs Product/Engg answer before dev |
| **ASSUMPTION** | Reasonable default; confirm in sign-off |

Produce a short **UD vs decisions** section when source material is messy (mirror remarketing/purging plans).

### Step 1.5 - Epic vs story + subtasks (Jira structure judgment)

Run this **before** naming multiple Story-level tickets. State at the **top of the plan** (first line after title):

`Recommended Jira structure: <Epic + N stories | 1 Story + N subtasks | Epic + 2 stories>`

#### Default (Novopay backend)

For most features (**~1-2 sprints**, **one business rule**, **one squad**), prefer:

**1 Story (or Task) + 5-8 subtasks**

Use numbered plan slices (e.g. `CC-LOC-PEPQ-001`) as **subtask titles** and implementation spec - not always as separate Jira Stories. Paste Engg/QA blocks into Story comments or subtask descriptions.

#### When to use **Epic + multiple Stories**

- Multi-sprint initiative or **quarter-level** bucket
- **Different teams/squads** with **different release trains** (e.g. `platform-lib` vs service cannot ship same sprint)
- Slices can be **prioritized or released independently** and each delivers value alone
- Total estimate often **> ~80h** OR explicitly **multi-product** scope
- **Follow-on work** expected under same initiative (MIS, reporting, other channels)

#### When to use **1 Story + subtasks** (preferred for tight features)

- **Single business outcome**, tightly coupled flow (e.g. one eligibility rule across offers + submit APIs)
- Roughly **~20-60h** total, **one assignee** or one squad
- **Two repos** but **one coordinated release** (lib bump + consumer in same sprint)
- **One QA regression matrix**, not a separate product line
- Error-code / notification / UAT rows are **subtasks**, not Stories

#### Lightweight split: **Epic + 2 Stories**

Only when exactly **two release trains** matter (e.g. Story 1: `infra-transaction-hdfc`; Story 2: `creditcard-management` + QA). Do **not** add Stories for tests-only or config-only slices unless the team tracks capacity that way.

#### Decision checklist (signals)

| Signal | Favors Story + subtasks | Favors Epic + Stories |
| --- | --- | --- |
| Business rules / outcomes | 1 | 2+ independent outcomes |
| Teams / owners | 1 squad | 2+ squads, different sprints |
| Sprint span | 1-2 sprints | 3+ sprints or phased rollout |
| Repo / release | Same train (lib + service together) | Cannot ship together |
| Estimate (dev+QA) | ~20-60h | Often **> ~80h** |
| Board tracking | One "done" when flow works | PM tracks slice priorities separately |
| Follow-on | None in scope | MIS / channels / phase 2 expected |

**Quick rule:** Count how many **Favors Epic + Stories** rows clearly apply.

- **0-1** → **1 Story + subtasks** (default)
- **2** → **Epic + 2 Stories** or **1 Story + subtasks** if same sprint anyway
- **3+** → **Epic + multiple Stories**

#### Anti-patterns

- **5+ Stories** for **one rule change** (~50h, one squad) unless the user asked for Epic structure
- Epic where nothing is Done until every Story closes (coupled slices)
- Subtasks with **no parent Story**
- Separate Story per unit-test or flyway-only row

#### Map plan output to Jira

| Recommended shape | What to do with `CC-XXX-001..00N` blocks in markdown |
| --- | --- |
| 1 Story + subtasks | One Product ticket on Story; slices → subtasks; Engg/QA per slice as subtask text or comments |
| Epic + Stories | Each slice → Story with full Product + Engg + QA |
| User asked "epic or subtasks?" | Always output **Recommended Jira shape**, **Why** (2-3 bullets), **How to relabel** the plan |

### Step 2 - Choose breakdown strategy

| Strategy | When |
| --- | --- |
| **Vertical slices** | Independent deliverables (schema, batch, consumer, QA pack) |
| **Flow slices** | One ticket per major flow (retail vs bulk vs assisted) |
| **Risk slices** | High-risk logic first (eligibility, dedupe, link resolution) |
| **Layer slices** | Infra → domain → integration → QA/docs |

Default for backend batch/SMS features: **Risk + Vertical** (foundation → retail path → bulk path → config → QA/docs).

Re-check **Step 1.5** after choosing slices: vertical slices that are **not** independently shippable still belong under **one Story** as subtasks.

### Step 3 - Size and split tickets

Target ticket count guidance:

| Epic size | Typical sub-ticket count |
| --- | --- |
| Small feature | 2-4 |
| Medium feature | 4-7 |
| Large epic | 6-10 |

If total estimate > ~40h, split further into **subtasks** (or Stories only if Step 1.5 says Epic). Do not auto-create an Epic solely because hours > 40 or because the plan has 5+ numbered slices.

### Step 4 - Write each sub-ticket (mandatory sections)

For **each** sub-ticket, output in this order:

1. `### Product ticket` - Title, Description, Acceptance criteria, Depends on, Jira journey select/do not select, **Journeys impacted** (table), **Estimation** (table)
2. `### Engineering reference` - Journey/flow map table, modules, baseline patterns, implementation steps, schema/config if any
3. `### QA reference` - Pre-requisites, test data setup table, functional tests, DB checks, regression, out of scope

Use [templates.md](templates.md) verbatim structure; fill content only.

### Step 5 - Roll up and validate

- **Estimation summary** table per epic
- **Justification table** (why this split)
- **Dependency diagram** (text or mermaid)
- **Delivery order** (numbered list)
- **Sign-off table** for OPEN items (ID, blocker?, owner, decision)

---

## Section Standards (Do Not Skip)

### Product ticket - Description

Write for **Product/PM/QA readers**, not engineers:

- Business outcome in plain language
- Bullet eligibility / exclusions / behavior rules
- What is explicitly out of scope
- Acceptance criteria as testable bullets

### Engineering reference

Must include:

- **Journey / flow map** table: `Flow | API / entry | Module`
- **Modules** list (all repos touched)
- **Baseline patterns** (link to similar existing code in repo; see [examples.md](examples.md) for Jira shape examples)
- **Implementation** numbered steps (concrete, not vague)
- **Frontend** line only if UI/regression relevant

### QA reference

Must include:

- **Pre-requisites** (env, data, access, upstream tickets)
- **Test data setup (minimum)** table with columns appropriate to feature (Lead/Age/State/Expected pattern)
- **Functional tests** numbered scenarios (happy path, exclusions, failures, idempotency, regression)
- **DB checks (sample)** SQL when DB validation matters
- **Out of scope** for this ticket
- **Depends on** upstream ticket when applicable

### Jira journey field (Novopay)

When project uses journey dropdown, include per ticket:

- **Jira journey field - select these (multiple)**
- **Do not select** with explicit exclusions

See [examples.md](examples.md) for CC remarketing and DSA lifecycle patterns.

### Estimation justification quality bar

Each `Why this size / justification` cell must state one of:

- Blocks downstream work
- Isolated risk/domain
- Integration surface count
- Test matrix size
- Operational/config-only scope
- Review/QA handoff slice

Bad: "Development work"  
Good: "Integration-heavy path; failure-prone SMS + audit writes"

---

## Estimation Heuristics (Hours)

| Work type | Typical range (hrs) |
| --- | --- |
| Decision / contract finalization | 1.5-3 |
| Single DAO query or small service method | 2-4 |
| Processor + orchestration wiring | 3-5 |
| New entity + repository + flyway | 4-6 |
| Kafka publish + consumer | 8-14 (split across 2-4 tickets) |
| Config + scheduler only | 6-10 |
| Unit test slice (focused matrix) | 3-4 |
| QA matrix + evidence pack | 8-12 |
| Docs + runbook only | 4-8 |

Always split work so **no single subtask row exceeds 4h** unless user overrides.

---

## Output Modes

| Mode | Output |
| --- | --- |
| `full-plan` | Complete markdown plan file (like `.cursor/plans/*.plan.md`); **Recommended Jira structure** on line 1 |
| `jira-ready` | Per-slice blocks (`CC-XXX-001` style) with Product + Engg + QA - **tell user** whether each slice is a Story or a subtask per Step 1.5 |
| `story-plus-subtasks` | One Story body + **Subtasks** table; detailed Engg/QA under each slice heading (default when Step 1.5 says Story) |
| `single-story` | Same as `story-plus-subtasks`; collapse all slices; optional appendix with full Engg/QA |
| `estimation-only` | Tables only (subtasks + summary + justification) + **Recommended Jira structure** |
| `single-ticket` | Break down one existing parent ticket ID/title only |

Default: `jira-ready` or `story-plus-subtasks` (pick from Step 1.5) + **Recommended Jira structure** on line 1 + offer consolidated plan file if useful.

**`jira-ready` note:** Numbered slices in the markdown are **planning units**, not an instruction to create that many Stories. If Step 1.5 says Story + subtasks, say explicitly: "Create 1 Story; use CC-XXX-001..00N as subtask titles."

---

## Quality Checklist (Before Handoff)

- [ ] Every sub-ticket has Product + Engg + QA sections
- [ ] Journeys impacted table present and non-empty
- [ ] Estimation table present; all rows <=4h (unless approved)
- [ ] Dependencies and delivery order documented
- [ ] OPEN questions listed with blocker flag
- [ ] No engineering jargon in Product ticket Description
- [ ] Engg reference includes flow map and modules
- [ ] QA reference includes pre-reqs, setup table, functional tests
- [ ] Terminology consistent within the plan (one name for txn status, consent state, etc.)
- [ ] **Epic vs Story vs subtasks** recommendation stated on line 1; plan structure matches it (slices are Stories vs subtasks)

---

## Anti-Patterns

- Do not produce generic "Implement feature" tickets without journey table and acceptance criteria.
- Do not merge Engg details into Product description (keep separate comments).
- Do not estimate in story points unless user asked.
- Do not invent modules or APIs - mark `TBD` and add OPEN question.
- Do not skip QA reference for "small" infra tickets if they affect release confidence.
- Do not default to Epic + many Stories for a single coupled feature (~50h, one squad) without running Step 1.5 checklist.
- Do not emit 5+ Story titles for one rule change when Step 1.5 says Story + subtasks unless user requested Epic structure.

---

## Quick Invoke Examples

- "Break down remarketing SMS epic into sub-tickets like data purging plan"
- "Create Jira tickets with engg and QA comments for this feature"
- "Estimate this ticket in 4 hour tasks with justification table"
- "Split CC-RMK epic into implementable sub-tickets with journey impact tables"
- "Is this epic-worthy or one story with subtasks?"
- "Break down LOC PE-PQ jumbo - story or epic?"

When user references a plan file path, read it and mirror its section structure exactly.
