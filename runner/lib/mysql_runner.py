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


def mysql_query(sql: str, schema: str | None = None) -> tuple[int, str]:
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
