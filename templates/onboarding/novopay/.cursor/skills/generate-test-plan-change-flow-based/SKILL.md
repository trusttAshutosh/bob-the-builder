---
name: backend-test-plan-generation
description: Generate execution-driven backend test plans using DB + API validation by tracing full impacted flow from code changes. Use when user asks for test plans, QA validation steps, regression scenarios, or impact-based testing for backend services.
---

# Backend Test Plan Generation (Change + Flow Based)

## When To Use

Use this skill when:

- A PR / code change needs test coverage validation
- Backend feature/API requires QA test plan
- Regression scenarios need to be created
- DB + API validation is required
- Flow-level validation is important (not just unit-level)
- Impact analysis of change is required

---

## Inputs Required

If missing, ask:

Share:
1) PR / diff / changed files
2) Feature / flow impacted
3) Any known edge cases (optional)

---

## Core Objective

Identify the COMPLETE FLOW impacted by the change and generate a test plan covering ALL involved components.

DO NOT rely on open/visible files  
DO NOT generate partial test plans

Always derive from:
- Code change (PR/diff)
- Full flow traversal

---

## Change Impact Analysis (MANDATORY)

Analyze the change and identify:

### Entry Points
- APIs / Controllers affected

### Flow Traversal
- Service methods
- Internal method calls
- Utility classes

### Data Layer
- Tables impacted (INSERT / UPDATE / SELECT)
- Repositories used
- Entity mappings

### Dependencies
- External services
- Queues / events
- Cache / configs

### Side Effects
- Audit/history tables
- Logs
- Status transitions

### Indirect Impact
- Shared methods reused
- Other flows impacted

---

## Flow Trace (MANDATORY)

Controller → Service → Repository → DB → External Systems

---

## Source of Truth

- Use entire repository
- Follow method calls across files
- Infer APIs, schema, logic from code

If unclear → ASK  
DO NOT assume or invent

---

## Strict Test Execution Format (NON-NEGOTIABLE)

For EVERY test scenario:

1. Insert minimal data in DB using SQL query
2. Run the API
3. Observe API response
4. Run SELECT query to validate DB
5. Expected output
6. Conclusion from actual output

---

## Test Scenario Template

### Scenario: <name>

#### Step 1: Insert Minimal Data

    -- SQL: exact insert query using real tables/columns

#### Step 2: Run API
- Endpoint:
- Method:
- Headers:
- Payload:

#### Step 3: Observe API Response

    {
      "expected": "response structure"
    }

#### Step 4: Validate DB

    -- SQL: select query verifying state

#### Step 5: Expected Output
- API:
- DB:
- Side effects (audit/events/logs):

#### Step 6: Conclusion
- Pass/Fail reasoning

---

## Coverage (MANDATORY)

### Functional
- Happy path
- Invalid input
- Missing fields
- Boundary values

### Change Impact
- Existing flows affected
- Backward compatibility

### Data Integrity
- Correct DB operations
- No unintended updates
- Referential integrity

### Reliability
- Idempotency / duplicate requests
- Transaction rollback
- Partial failures

### System Behavior
- Concurrency
- Retry / timeout

### Dependencies
- Downstream failures

### Observability
- Audit/history tables
- Logs (if applicable)

---

## Must-Have Practices

- Minimal test data
- Test independence
- Validate BOTH API + DB
- Use real schema names
- Verify:
    - status transitions
    - rollback behavior
    - no duplicate entries

---

## Good-to-Have

- Tag scenarios (smoke / regression / critical)
- Cleanup queries
- Automation feasibility
- Risk-based prioritization
- Edge cases from code

---

## Strict Rules

### DO NOT:
- Refer to open files
- Miss indirect flows
- Skip SQL or DB validation
- Write generic test cases
- Assume schema/APIs

### DO:
- Trace from change
- Cover full flow
- Keep steps executable
- Align with repository code

---

## Output Format

Return:

1. Impacted flow summary
2. Scenario list
3. Detailed test scenarios (strict format)
4. Coverage summary
5. Gaps / risks

---

## Final Expectation

Test plan must be:

- End-to-end
- Change-impact driven
- Fully executable
- Zero fluff

## Debugging Addendum (MANDATORY for bank-dependent status flows)

When generating plans for any flow that depends on partner/bank callbacks or downstream status fetch:

- Seed all mandatory preconditions for partner call (for example: non-blank external reference fields, required status keys, required identifiers) in insert SQL if the flow checks them before partner call.
- Add a **Pre-API DB Check** step in the scenario:
    - verify row exists for the request identifier used by the flow
    - verify required preconditions for partner call are non-blank/present
    - verify query method can return row (status filters/flags).
- Add a **Breakpoint Playbook** section with exact checkpoints:
    1) around DAO/repository fetch result (`null` guard),
    2) before partner call,
    3) at persistence/update method.
- Explicitly list null/blank short-circuit points (example: fetched entity null, required external reference blank) and their error codes if known.
- Provide a **bank-response mimic step** for local/offline runs:
    - set success/error keys expected by the flow in `executionContext` (or equivalent context object),
    - set domain-specific response fields required for persistence logic,
    - then continue from just before persistence call.
- Always include expected DB attributes/row updates after mimic run to prove scenario validity.

### Debugger Rescue Procedure (REQUIRED when bank call is unavailable)

In generated test plans, include this as an explicit, copy-paste runbook (not optional):

1. Place breakpoints:
    - In entry processor/service around DAO/repository fetch + precondition null/blank guards.
    - Immediately before partner call.
    - Immediately before persistence/update method call.
    - First line inside `catch`/error handler.
2. Start API call in debug mode.
3. If flow enters `catch` before persistence:
    - Open **Evaluate Expression**.
    - Evaluate EXACT statements one by one (flow-specific keys from code trace), for example:
        - set success envelope keys (e.g., `errorCode`, `errorMessage`)
        - set domain response fields consumed by persistence logic (status/category/date/etc.)
    - Evaluate persistence call directly (actual method from flow under test).
4. Continue execution till API completes (end of request/response lifecycle).
5. Run DB verification queries after API completion:
    - Query base transaction/entity row by request identifier to fetch actual row id.
    - Query affected audit/attribute/history tables by that id for fields changed by the flow.
6. Compare with expected values and record pass/fail conclusion.

### Must include short-circuit checks in plan

- repository fetch returned null -> expected error code and no partner call.
- required external/reference field blank -> expected error code and no partner call.
- identifier length/DB truncation risk (e.g., STAN/request IDs) -> mention max length validation before run.

### Non-negotiable wording rule for generated plans

Do not say only “set values in debugger.”  
Always provide:
- exact breakpoint location intent,
- exact Evaluate Expression commands,
- explicit “continue flow to end of API,”
- exact post-run DB queries.

## Kafka Addendum (CONDITIONAL - include only if flow actually uses Kafka)

Before adding Kafka validation to a test plan, confirm from code trace that the impacted flow has:

- Kafka producer/publish in the same path, or
- Kafka consumer/listener as an execution step (`@KafkaListener`, queue consumer class), or
- explicit dependency on queue-handler handoff for that API path.

If Kafka is **not** in the traced flow, do **not** add Kafka setup, topic, consumer, or fallback steps.

If Kafka **is** in the traced flow, test plan must include:

1. What is published (topic/payload/headers/keys).
2. What is consumed (consumer class + expected mapped fields).
3. Failure behavior when Kafka/queue is down.
4. A direct API bypass step (if supported) to continue functional validation when queue infra is unavailable.
5. Observability checks (producer log + consumer log + downstream DB/API effect).

