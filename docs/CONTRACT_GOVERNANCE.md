# Contract governance

Bob separates **product code/features** (`product-features.yaml`) from **doc truth** (`doc-invariants.yaml`). Weakening either file to silence CI is blocked unless you **explicitly approve** and record why.

## Protected files

| File | Role |
|------|------|
| `docs/doc-invariants.yaml` | Doc contract (scope, CLI, links, forbidden phrases) |
| `docs/product-features.yaml` | Registered Bob features (paths, commands) |

## What counts as weakening

Examples (require approval):

- Removing a content rule, forbidden pattern, or required file
- Removing `must_contain` needles from a rule
- Removing a registered product feature, command, or path
- Expanding skip lists (`skip_commands`, `skip_rows_containing`)

Adding rules or documentation (strengthening) does **not** require approval.

## Workflow

### 1. CI or pre-commit fails

```text
Contract WEAKENED without human approval — run: bob contract-diff
Then: bob approve-contract-change --reason "..."
Commit the new docs/contract-approvals/<id>.yaml with the contract change.
```

### 2. Review impact (required)

```bash
bob contract-diff              # vs last commit
bob contract-diff --vs main    # vs branch base (CI uses this on PR)
```

Read the **Weakenings** section — what guardrails are removed and what can regress.

### 3. Conscious approval (human only)

```bash
bob approve-contract-change --reason "Why this is safe and what we accept"
```

Interactive prompt: type **`APPROVE`** (exact token). Bob writes:

`docs/contract-approvals/<timestamp>-<slug>.yaml`

**Commit that approval file in the same commit/PR** as the contract change.

Non-interactive (use sparingly — you still must review `contract-diff` first):

```bash
bob approve-contract-change --reason "..." --yes --approver "your.name"
```

Agents must **not** use `--yes` unless you typed `APPROVE` in the same session.

### 4. Verify before push

```bash
bob verify-all
```

Runs product features, doc invariants, and contract governance.

## CI and git hooks

| Gate | Behavior |
|------|----------|
| **GitHub Actions** | Compares PR/push to base; weakened contracts need matching approval hashes |
| **pre-commit hook** | Blocks commit if staged contract files weaken without staged approval file |

Install hooks: `bob install-hooks`

## Agent policy

Cursor rule: `.cursor/rules/bob-doc-contract.mdc`

- Do not weaken `doc-invariants.yaml` or `product-features.yaml` to green CI.
- If the user directs a legitimate contract change, run `contract-diff`, explain impact, then **wait for the user** to run `approve-contract-change`.
