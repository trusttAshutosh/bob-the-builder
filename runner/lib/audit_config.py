"""Resolve audit DB settings from env profile + ticket-spec."""
from __future__ import annotations

from typing import Any


def audit_settings(spec: dict) -> dict[str, Any]:
    env = spec.get("_env") or {}
    audit = dict(env.get("audit") or {})
    mysql = env.get("mysql") or {}
    run = spec.get("run") or {}
    schemas = mysql.get("schemas") or {}
    audit.setdefault("table", "transaction_audit")
    audit.setdefault("crn_column", "client_reference_code")
    audit.setdefault("order_by", "updated_on DESC")
    audit.setdefault(
        "columns",
        ["txn_status", "txn_result_code", "txn_result_description", "internal_txn_desc"],
    )
    audit["schema"] = run.get("audit_db") or schemas.get("audit") or "dsa_credit_card_mgmt"
    return audit


def build_audit_query(crn: str, spec: dict) -> str:
    a = audit_settings(spec)
    cols = ", ".join(a["columns"])
    crn_safe = crn.replace("'", "''")
    return (
        f"SELECT {cols} FROM {a['table']} "
        f"WHERE {a['crn_column']}='{crn_safe}' "
        f"ORDER BY {a['order_by']} LIMIT 1"
    )


def parse_audit_row(out: str, spec: dict) -> dict[str, str]:
    cols = audit_settings(spec)["columns"]
    lines = [ln for ln in out.splitlines() if ln.strip() and "Warning" not in ln and "mysql" not in ln.lower()]
    if len(lines) < 2:
        return {}
    parts = lines[-1].split("\t")
    if len(parts) < len(cols):
        return {}
    return {str(cols[i]): parts[i].strip() for i in range(len(cols))}
