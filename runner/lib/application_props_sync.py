"""Write Bob setup MySQL credentials into service application.properties before bootRun."""
from __future__ import annotations

import os
import re
from pathlib import Path

_JDBC_URL = re.compile(r"^spring\.datasource\.url\s*=\s*jdbc:mysql://[^/]+/([^?\s]+)", re.M)
_MASTER_DB = re.compile(r"^novopay\.platform\.master\.datasource\.db\s*=\s*(\S+)", re.M)

_PROP_FILES = (
    Path("src/main/resources/application.properties"),
    Path("deploy/application/dist/application.properties"),
)

def _mysql_env() -> dict[str, str]:
    return {
        "host": (os.environ.get("MYSQL_HOST") or "127.0.0.1").strip(),
        "port": (os.environ.get("MYSQL_PORT") or "3306").strip(),
        "user": (os.environ.get("MYSQL_USER") or "root").strip(),
        "pass": (os.environ.get("MYSQL_PASS") or "root").strip(),
        "platform_schema": (os.environ.get("MYSQL_PLATFORM_SCHEMA") or "platform_master").strip(),
    }


def _default_db_name(text: str, creds: dict[str, str]) -> str:
    m = _MASTER_DB.search(text)
    if m:
        return m.group(1).strip()
    m = _JDBC_URL.search(text)
    if m:
        return m.group(1).strip()
    return creds["platform_schema"]


def _rewrite_line(line: str, creds: dict[str, str], db_name: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return line
    if stripped.startswith("spring.datasource.url="):
        return f"spring.datasource.url=jdbc:mysql://{creds['host']}:{creds['port']}/{db_name}"
    if stripped.startswith("spring.datasource.username="):
        return f"spring.datasource.username={creds['user']}"
    if stripped.startswith("spring.datasource.password="):
        return f"spring.datasource.password={creds['pass']}"
    if stripped.startswith("novopay.platform.master.datasource.host="):
        return f"novopay.platform.master.datasource.host={creds['host']}"
    if stripped.startswith("novopay.platform.master.datasource.port="):
        return f"novopay.platform.master.datasource.port={creds['port']}"
    if stripped.startswith("novopay.platform.master.datasource.username="):
        return f"novopay.platform.master.datasource.username={creds['user']}"
    if stripped.startswith("novopay.platform.master.datasource.password="):
        return f"novopay.platform.master.datasource.password={creds['pass']}"
    return None


def _patch_properties_file(path: Path, creds: dict[str, str]) -> bool:
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8", errors="replace")
    db_name = _default_db_name(original, creds)
    lines: list[str] = []
    changed = False
    for line in original.splitlines():
        new_line = _rewrite_line(line, creds, db_name)
        if new_line is not None and new_line != line.rstrip():
            lines.append(new_line)
            changed = True
        else:
            lines.append(line.rstrip("\n\r"))
    if changed:
        path.write_text("\n".join(lines) + ("\n" if original.endswith("\n") else ""), encoding="utf-8")
    return changed


def sync_application_properties_from_prefs(repo: Path) -> tuple[bool, str]:
    """
    Apply MYSQL_* from Bob setup (user.env) to known datasource keys in application.properties.
    Returns (ok, detail). ok=False only when a target file exists but cannot be written.
    """
    creds = _mysql_env()
    if not creds["user"]:
        return False, "MYSQL_USER not set — run: bob setup"

    updated: list[str] = []
    for rel in _PROP_FILES:
        path = repo / rel
        if not path.is_file():
            continue
        try:
            if _patch_properties_file(path, creds):
                updated.append(rel.as_posix())
        except OSError as e:
            return False, f"cannot write {rel}: {e}"

    if updated:
        return True, f"synced MySQL creds ({creds['user']}@{creds['host']}:{creds['port']}) in {', '.join(updated)}"
    dist = repo / _PROP_FILES[1]
    if not dist.is_file():
        return True, "no application.properties to sync yet (run copyProperties first)"
    return True, "application.properties already match Bob MySQL prefs"
