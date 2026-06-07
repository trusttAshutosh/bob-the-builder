# Contributing a reference pack (`assets/examples/`)

Reference packs are **optional**. Bob never loads `assets/examples/*` at runtime. Live catalogs live under `assets/api-catalog/`, `assets/stub-registry/`, etc., built on your machine via `bob discover-apis` and your tickets.

Commit a reference pack only when your team has **dogfooded Bob** on a service and wants to share **sanitized** API/stub shapes for the next team - same idea as [`assets/examples/novopay-cc/`](../assets/examples/novopay-cc/README.md).

Bob **never** runs `git commit` or `git push`. You open the branch and PR yourself (Ship gate).

---

## When to contribute

| Do | Do not |
|----|--------|
| After at least one real ticket on your service (`validate-ticket` completed locally) | On day one before dogfood |
| Curate a **snapshot** under `assets/examples/<pack-name>/` | Mirror your entire live `assets/` tree |
| Strip secrets, real CRNs, internal URLs, customer data | Commit `local/user.env` or ticket evidence |
| Add a pack `README.md` (what it is, how to copy vs `discover-apis`) | Auto-push on a schedule |

Prove the empty-catalog path first: [`FRESH_INSTALL_VERIFY.md`](FRESH_INSTALL_VERIFY.md) (`bob verify-fresh-install`).

---

## Suggested workflow

### 1. Prepare locally (after usage)

From `bob-the-builder/`:

```bash
# Example layout - adjust pack name for your service
mkdir -p assets/examples/novopay-payments/api-catalog/apis
mkdir -p assets/examples/novopay-payments/stub-registry/bank-operations

# Copy only what others need (edit paths to match what you curated)
cp assets/api-catalog/index.yaml assets/examples/novopay-payments/api-catalog/
cp assets/api-catalog/apis/*.yaml assets/examples/novopay-payments/api-catalog/apis/
# stubs: copy selected bank-operation fixtures only

# Write assets/examples/novopay-payments/README.md
```

Review diffs for secrets and env-specific values before any git step.

### 2. New branch (separate from feature work)

```bash
cd bob-the-builder
git checkout main
git pull
git checkout -b examples/novopay-payments-initial
git add assets/examples/novopay-payments/
git commit -m "examples: add novopay-payments reference pack"
git push -u origin examples/novopay-payments-initial
```

**Branch naming:** `examples/<service-or-pack>-initial` or `examples/<service>-<yyyy-mm>`.

**PR title:** `examples: add novopay-payments reference pack`

**PR body should include:**

- Link to a dogfood ticket folder in the **host service** repo (or Jira id)
- Confirmation: no secrets / no live customer data
- What a reader should copy vs run `bob discover-apis` for themselves

### 3. Review and merge

A `bob-the-builder` maintainer reviews and merges. Reference packs are **curated docs**, not release blockers for your service PRs.

---

## If you are not a collaborator on `bob-the-builder`

You **cannot** push to the upstream repo without access.

| Option | Steps |
|--------|--------|
| **Fork + PR** (default) | Fork on GitHub → clone your fork → branch `examples/...` → push to **your fork** → open PR to upstream |
| **Ask for access** | Maintainer adds you as collaborator; still use a branch + PR, not direct push to `main` |
| **Do not fork Bob** | Keep examples only in your service repo under `docs/` - weaker for org sharing |

There is no supported way to "silently" push to upstream without write access and credentials.

---

## PR checklist (reviewer)

- [ ] Files only under `assets/examples/<pack>/` (plus optional one-line index in [`assets/examples/README.md`](../assets/examples/README.md))
- [ ] Pack `README.md` states reference-only, not loaded by Bob
- [ ] No `local/`, no `user.env`, no ticket `evidence/`
- [ ] No `credit_card_management` leakage unless the pack is intentionally CC
- [ ] Optional: link from [`ADOPTING_BOB_FOR_ANOTHER_SERVICE.md`](ADOPTING_BOB_FOR_ANOTHER_SERVICE.md) if this is the second-service proof

---

## What stays in the host service repo

| Artifact | Repo |
|----------|------|
| `deploy/tdd/` | Host service |
| `docs/tdd-runs/<ticket>/` | Host service (often local-only) |
| Live `assets/api-catalog/` after discover | Usually **not** committed; team choice |
| Curated snapshot for others | `bob-the-builder/assets/examples/` (this doc) |

---

## Related

- [`assets/examples/README.md`](../assets/examples/README.md) - pack index
- [`ADOPTING_BOB_FOR_ANOTHER_SERVICE.md`](ADOPTING_BOB_FOR_ANOTHER_SERVICE.md) - onboarding another service
- [`DATA_LAYOUT.md`](DATA_LAYOUT.md) - where Bob writes files
