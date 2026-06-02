"""Resolve audit DB settings from env profile + ticket-spec."""
from __future__ import annotations

import re
from typing import Any


def audit_settings(spec: dict) -> dict[str, Any]:
    env = spec.get("_env") or {}
    from host_profile import audit_table_defaults

    audit = dict(env.get("audit") or {})
    for k, v in audit_table_defaults().items():
        if k == "columns":
            audit.setdefault("columns", list(v))
        else:
            audit.setdefault(k, v)
    from host_profile import audit_schema

    audit["schema"] = audit_schema(spec)
    return audit


def scenario_description(scenario_id: str, name: str) -> str:
    label = (name or "").strip()
    return f"{scenario_id}: {label}" if label else str(scenario_id)


def e2e_scenario_crns(
    spec: dict, base_crn: str, run_crns: dict[str, str] | None = None
) -> dict[str, str]:
    """E2E CRNs from validate-ticket run, or `{base}-{scenarioId}` from ticket-spec."""
    if run_crns:
        return dict(run_crns)
    from ticket_spec import scenarios

    out: dict[str, str] = {}
    for sc in scenarios(spec):
        sid = sc.get("id", "?")
        level = (sc.get("verification_level") or "e2e").lower()
        if level in ("integration", "e2e"):
            out[sid] = sc.get("crn") or f"{base_crn}-{sid}"
    return out


def db_verify_sql_header(base_crn: str, schema: str) -> list[str]:
    crn_safe = base_crn.replace("'", "''")
    return [
        "-- Bob generated after validate-ticket. Your part: run these in MySQL Workbench.",
        f"-- @BASE_CRN: {base_crn}",
        f"-- Schema: {schema}",
        "",
        f"SET @BASE_CRN = '{crn_safe}';",
        "",
        f"USE {schema};",
        "",
        "-- Dashboard (all E2E scenarios): scenario_id, scenario_description, client_reference_code,",
        "-- txn_status, txn_result_code, txn_result_description, internal_txn_desc, assert_result",
        "",
    ]


def _sql_pass_fail_expr(db_expect: dict) -> str:
    parts: list[str] = []
    for k, v in (db_expect.get("expect") or {}).items():
        col = str(k).replace("'", "''")
        val = str(v).replace("'", "''")
        parts.append(f"COALESCE({col}, '') = '{val}'")
    mnc = db_expect.get("must_not_contain") or {}
    for col, vals in mnc.items():
        col_sql = str(col).replace("'", "''")
        for v in vals or []:
            val_sql = str(v).replace("'", "''")
            parts.append(
                f"(COALESCE({col_sql}, '') = '' OR COALESCE({col_sql}, '') <> '{val_sql}')"
            )
    if prefix := db_expect.get("internal_txn_desc_prefix"):
        safe = str(prefix).replace("'", "''")
        parts.append(f"internal_txn_desc LIKE '{safe}%'")
    if exact := db_expect.get("internal_txn_desc"):
        safe = str(exact).replace("'", "''")
        parts.append(f"internal_txn_desc = '{safe}'")
    if not parts:
        return "'REVIEW' AS assert_result"
    joined = " AND ".join(parts)
    return f"CASE WHEN {joined} THEN 'PASS' ELSE 'FAIL' END AS assert_result"


def validate_union_dashboard_sql(sql: str) -> list[str]:
    """MySQL: each UNION ALL branch with ORDER BY must be wrapped in a subquery."""
    errors: list[str] = []
    if "UNION ALL" not in sql.upper():
        return errors
    for i, branch in enumerate(re.split(r"\nUNION ALL\n", sql, flags=re.IGNORECASE)):
        chunk = branch.strip()
        if not chunk or "ORDER BY" not in chunk.upper():
            continue
        if "SELECT * FROM (" not in chunk.split("ORDER BY")[0]:
            errors.append(
                f"UNION branch {i + 1}: ORDER BY/LIMIT must be inside subquery "
                "(wrap with SELECT * FROM (...) AS alias)"
            )
    return errors


def build_scenario_audit_select(
    scenario_id: str,
    scenario_name: str,
    crn: str,
    spec: dict,
    db_expect: dict | None = None,
    *,
    for_union: bool = False,
) -> str:
    """Build latest audit row SELECT. Use for_union=True for UNION ALL branches (MySQL requires subquery)."""
    a = audit_settings(spec)
    audit_cols = ", ".join(a["columns"])
    crn_safe = crn.replace("'", "''")
    sid_safe = str(scenario_id).replace("'", "''")
    desc_safe = scenario_description(scenario_id, scenario_name).replace("'", "''")
    pass_expr = _sql_pass_fail_expr(db_expect or {})
    inner = (
        f"SELECT '{sid_safe}' AS scenario_id, '{desc_safe}' AS scenario_description, "
        f"'{crn_safe}' AS client_reference_code, {audit_cols}, {pass_expr} "
        f"FROM {a['table']} WHERE {a['crn_column']}='{crn_safe}' "
        f"ORDER BY {a['order_by']} LIMIT 1"
    )
    if not for_union:
        return inner
    alias = re.sub(r"[^a-zA-Z0-9_]", "_", f"_bob_{sid_safe}")
    if alias[0].isdigit():
        alias = f"bob_{alias}"
    return f"SELECT * FROM (\n{inner}\n) AS {alias}"


def build_audit_dashboard_query(
    scenario_rows: list[tuple[str, str, str, dict | None]],
    spec: dict,
) -> str:
    """UNION ALL dashboard: scenario id, description, CRN, audit cols, pass/fail."""
    if not scenario_rows:
        return ""
    parts = [
        build_scenario_audit_select(sid, name, crn, spec, db_expect, for_union=True)
        for sid, name, crn, db_expect in scenario_rows
    ]
    return "\nUNION ALL\n".join(parts)


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
