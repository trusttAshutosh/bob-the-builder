"""Local MySQL execution for Bob validate-ticket (Windows + Linux)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def mysql_bin() -> str:
    for candidate in (
        Path("/c/Program Files/MySQL/MySQL Server 8.0/bin/mysql.exe"),
        Path("C:/Program Files/MySQL/MySQL Server 8.0/bin/mysql.exe"),
    ):
        if candidate.exists():
            return str(candidate)
    return "mysql"


def _mysql_query_local(sql: str, schema: str | None = None) -> tuple[int, str]:
    host = os.environ.get("MYSQL_HOST", "127.0.0.1")
    port = os.environ.get("MYSQL_PORT", "3306")
    user = os.environ.get("MYSQL_USER", "root")
    pw = os.environ.get("MYSQL_PASS", "root")
    db = schema or os.environ.get("MYSQL_AUDIT_SCHEMA", "dsa_credit_card_mgmt")
    cmd = [mysql_bin(), f"-h{host}", f"-P{port}", f"-u{user}", f"-p{pw}", db, "-e", sql]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return 1, str(e)


def mysql_query(sql: str, schema: str | None = None) -> tuple[int, str]:
    """Run SQL via tool bridge (local by default; MCP when BOB_TOOL_BACKEND=mcp|auto)."""
    try:
        from tool_bridge import run_tool

        result = run_tool("mysql.query", sql=sql, schema=schema)
        out = result.text()
        return (0 if result.ok else result.exit_code or 1), out
    except ImportError:
        return _mysql_query_local(sql, schema=schema)


def mysql_exec_script(sql_text: str, schema: str | None = None) -> tuple[int, str]:
    chunks: list[str] = []
    for stmt in sql_text.split(";"):
        stmt = stmt.strip()
        if stmt and not stmt.startswith("--"):
            chunks.append(stmt)
    if not chunks:
        return 0, ""
    last_out = ""
    for stmt in chunks:
        rc, last_out = mysql_query(stmt, schema=schema)
        if rc != 0:
            return rc, last_out
    return 0, last_out


def ensure_dsa_masterdata_configuration_schema() -> tuple[bool, str]:
    """Add permission_code to dsa_masterdata.configuration when missing (local Bob drift)."""
    rc, out = mysql_query(
        "SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA='dsa_masterdata' AND TABLE_NAME='configuration' "
        "AND COLUMN_NAME='permission_code'",
        schema="platform_master",
    )
    if rc != 0:
        return False, out[-300:]
    scalar = None
    for line in reversed((out or "").splitlines()):
        token = line.strip()
        if token.isdigit():
            scalar = token
            break
    if scalar != "0":
        return True, "permission_code column present"
    rc, out = mysql_query(
        "ALTER TABLE dsa_masterdata.configuration ADD COLUMN permission_code VARCHAR(64) NULL",
        schema="platform_master",
    )
    if rc != 0:
        return False, out[-300:]
    mysql_query(
        "CREATE INDEX idx_permission_code ON dsa_masterdata.configuration(permission_code(64))",
        schema="platform_master",
    )
    return True, "added permission_code column to dsa_masterdata.configuration"


def ensure_dsa_notifications_sms_log_schema() -> tuple[bool, str]:
    """Add gateway_response_code to dsa_notifications.sms_log when missing (local Bob drift)."""
    rc, out = mysql_query(
        "SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA='dsa_notifications' AND TABLE_NAME='sms_log' "
        "AND COLUMN_NAME='gateway_response_code'",
        schema="platform_master",
    )
    if rc != 0:
        return False, out[-300:]
    scalar = None
    for line in reversed((out or "").splitlines()):
        token = line.strip()
        if token.isdigit():
            scalar = token
            break
    if scalar != "0":
        return True, "sms_log.gateway_response_code present"
    rc, out = mysql_query(
        "ALTER TABLE dsa_notifications.sms_log "
        "ADD COLUMN gateway_response_code VARCHAR(64) NULL AFTER status",
        schema="platform_master",
    )
    if rc != 0:
        return False, out[-300:]
    return True, "added gateway_response_code to dsa_notifications.sms_log"
