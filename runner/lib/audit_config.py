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


def audit_attribute_keys(spec: dict) -> list[str]:
    """Optional transaction_audit_attributes.attr_key columns on dashboard SELECTs."""
    run = spec.get("run") or {}
    if keys := run.get("audit_attribute_keys"):
        return [str(k) for k in keys if str(k).strip()]
    env = spec.get("_env") or {}
    audit = env.get("audit") or {}
    if keys := audit.get("attribute_keys"):
        return [str(k) for k in keys if str(k).strip()]
    return []


def audit_time_column(audit: dict[str, Any]) -> str:
    """First column in order_by (default updated_on) - latest audit row timestamp."""
    order_by = str(audit.get("order_by") or "updated_on DESC").strip()
    token = order_by.split()[0] if order_by else "updated_on"
    return token or "updated_on"


def _audit_attr_scalar_sql(attr_key: str, audit_table: str) -> str:
    key_safe = str(attr_key).replace("'", "''")
    col = re.sub(r"[^a-zA-Z0-9_]", "_", key_safe)
    if col[0].isdigit():
        col = f"attr_{col}"
    return (
        f"(SELECT taa.attr_value FROM transaction_audit_attributes taa "
        f"WHERE taa.transaction_audit_id = {audit_table}.id "
        f"AND taa.attr_key = '{key_safe}' LIMIT 1) AS {col}"
    )


def db_verify_sql_header(
    base_crn: str, schema: str, attribute_keys: list[str] | None = None
) -> list[str]:
    crn_safe = base_crn.replace("'", "''")
    dash_cols = (
        "test_run_time, txn_status, txn_result_code, txn_result_description, internal_txn_desc"
    )
    keys = attribute_keys or []
    if keys:
        dash_cols += ", " + ", ".join(keys)
    dash_cols += ", assert_result"
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
        f"-- {dash_cols}",
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
    time_col = audit_time_column(a)
    crn_safe = crn.replace("'", "''")
    sid_safe = str(scenario_id).replace("'", "''")
    desc_safe = scenario_description(scenario_id, scenario_name).replace("'", "''")
    pass_expr = _sql_pass_fail_expr(db_expect or {})
    attr_keys = audit_attribute_keys(spec)
    attr_sql = ""
    if attr_keys:
        attr_sql = ", " + ", ".join(
            _audit_attr_scalar_sql(k, a["table"]) for k in attr_keys
        )
    inner = (
        f"SELECT '{sid_safe}' AS scenario_id, '{desc_safe}' AS scenario_description, "
        f"'{crn_safe}' AS client_reference_code, {time_col} AS test_run_time, "
        f"{audit_cols}{attr_sql}, {pass_expr} "
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


def build_audit_attributes_raw_query(base_crn: str, attribute_keys: list[str]) -> str:
    """All attribute rows for this Bob run (manual spot-check in Workbench)."""
    if not attribute_keys:
        return ""
    keys_sql = ", ".join(
        "'" + str(k).replace("'", "''") + "'" for k in attribute_keys
    )
    return (
        "-- Raw rows: transaction_audit_attributes for this Bob run\n"
        "\n"
        "SELECT ta.client_reference_code,\n"
        "       ta.txn_status,\n"
        "       ta.txn_result_code,\n"
        "       taa.attr_key,\n"
        "       taa.attr_value\n"
        "FROM transaction_audit ta\n"
        "JOIN transaction_audit_attributes taa ON taa.transaction_audit_id = ta.id\n"
        "WHERE ta.client_reference_code LIKE CONCAT(@BASE_CRN, '%')\n"
        f"  AND taa.attr_key IN ({keys_sql})\n"
        "ORDER BY ta.client_reference_code, taa.attr_key;"
    )


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
