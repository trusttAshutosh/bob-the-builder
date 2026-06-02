"""Evidence contract for validate-ticket — unit tests alone cannot prove DB/API work."""
from __future__ import annotations

from pathlib import Path

from assertions import resolve_db_expect
from ticket_spec import scenarios


def validate_evidence_contract(spec: dict, ticket_dir: Path | None = None) -> tuple[bool, list[str]]:
    """
    When a ticket claims gateway/DB evidence, Bob must run e2e steps + DB asserts.
    Opt out only with run.allow_unit_only_evidence: true (local dev).
    """
    run = spec.get("run") or {}
    if run.get("allow_unit_only_evidence"):
        return True, []

    evidence = set(spec.get("evidence_required") or [])
    impacted = spec.get("impacted") or {}
    gateway_apis = impacted.get("gateway_apis") or []
    bank_ops = impacted.get("bank_operations") or []

    needs_live = (
        "transaction_audit" in evidence
        or "api_response" in evidence
        or bool(gateway_apis)
    )
    if not needs_live:
        return True, []

    errors: list[str] = []
    e2e_with_steps: list[dict] = []
    for sc in scenarios(spec):
        level = (sc.get("verification_level") or "e2e").lower()
        steps = sc.get("steps") or []
        if level in ("e2e", "integration") and steps:
            e2e_with_steps.append(sc)

    if not e2e_with_steps:
        errors.append(
            "Bob requires at least one scenario with verification_level e2e|integration "
            "and non-empty steps[] when evidence_required includes transaction_audit/api_response "
            "or impacted.gateway_apis is set. Unit tests (Mockito) do not write to MySQL. "
            "Add E2E scenarios + stubs, or set run.allow_unit_only_evidence: true for dev-only runs."
        )

    if "transaction_audit" in evidence and e2e_with_steps:
        has_e2e_db = False
        for sc in e2e_with_steps:
            db = resolve_db_expect(sc, spec)
            if db.get("expect") or db.get("internal_txn_desc_prefix") or db.get("internal_txn_desc"):
                has_e2e_db = True
            if db.get("expect_internal_txn_desc_pattern"):
                has_e2e_db = True
        if not has_e2e_db:
            errors.append(
                "transaction_audit evidence requires at least one E2E scenario with db.expect "
                "(or internal_txn_desc_prefix / expect_internal_txn_desc_pattern). "
                "Unit-scenario db: blocks do not count as live proof."
            )

    if gateway_apis and bank_ops:
        stubs = spec.get("stubs") or []
        masterdata = spec.get("masterdata") or []
        has_ticket_stub_dir = False
        if ticket_dir:
            mappings = ticket_dir / "stubs" / "mappings"
            has_ticket_stub_dir = mappings.is_dir() and any(mappings.iterdir())
        if not stubs and not masterdata and not has_ticket_stub_dir:
            errors.append(
                "impacted.gateway_apis + bank_operations need stubs[] or masterdata[] "
                "(WireMock bank URLs) so E2E failures are reproducible."
            )

    return len(errors) == 0, errors
