# Reference catalogs (Novopay credit-card / LOC)

**Not active `BOB_HOME` data.** Bob reads `assets/api-catalog/`, `assets/stub-registry/`, etc. at the repo root — not this folder.

Use this as a **copy source** when working on CC/LOC tickets, or as documentation of fixture shapes.

## Copy stubs into live registry (optional)

From `bob-the-builder/`:

```bash
cp -r assets/examples/novopay-cc/stub-registry/bank-operations/* assets/stub-registry/bank-operations/
```

## APIs

Prefer **`bob discover-apis`** from the credit-card host repo — that writes to `assets/api-catalog/`.  
To seed from this snapshot instead:

```bash
cp assets/examples/novopay-cc/api-catalog/apis/*.yaml assets/api-catalog/apis/
cp assets/examples/novopay-cc/api-catalog/index.yaml assets/api-catalog/
```

## Contents

- ~52 gateway API YAMLs (CC orchestration snapshot)
- HDFC LOC bank-operation stubs (getCardSummary, submitInstaLoan, inquireCreditCardProductEligibility)
- Sample assertion preset (`transaction-audit-example.yaml`)
- CC team tickets: set `git.branch_policy: novopay-feature` in `ticket-spec.yaml` to allow optional `ddp-fea-*` checkout (still no commit)
