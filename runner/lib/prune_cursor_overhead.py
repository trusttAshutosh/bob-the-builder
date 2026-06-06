"""bob prune-overhead — apply Bob squad MCP/plugin policy on this machine."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

from chat_hygiene import global_state_db
from cursor_overhead import (
    APPLICATION_USER_KEY,
    DISABLE_PLUGIN_DIRS,
    DISABLE_PLUGIN_IDS,
    DISABLED_SUFFIX,
    KEEP_MCP_SERVERS,
    MCP_JSON,
    PLUGIN_CACHE_ROOT,
    PLUGIN_INSTALLED_PREFIX,
    all_non_keep_tools_to_disable,
    build_mcp_audit as _build_mcp_audit,
)


def _backup_file(path: Path, *, dry_run: bool) -> Path | None:
    if not path.is_file() or dry_run:
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.name}.bak-{stamp}")
    shutil.copy2(path, backup)
    return backup


def _read_application_user(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT value FROM ItemTable WHERE key = ?",
        (APPLICATION_USER_KEY,),
    ).fetchone()
    if not row:
        return None
    try:
        parsed = json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _write_application_user(conn: sqlite3.Connection, payload: dict) -> None:
    conn.execute(
        "UPDATE ItemTable SET value = ? WHERE key = ?",
        (json.dumps(payload), APPLICATION_USER_KEY),
    )


def prune_mcp_json(*, dry_run: bool) -> tuple[bool, Path | None]:
    backup: Path | None = None
    if MCP_JSON.is_file():
        try:
            current = json.loads(MCP_JSON.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            current = {}
        servers = current.get("mcpServers")
        if isinstance(servers, dict) and servers:
            backup = _backup_file(MCP_JSON, dry_run=dry_run)
            if not dry_run:
                MCP_JSON.write_text(
                    json.dumps({"mcpServers": {}}, indent=2) + "\n",
                    encoding="utf-8",
                )
            return True, backup
        return False, None

    if dry_run:
        return False, None
    MCP_JSON.parent.mkdir(parents=True, exist_ok=True)
    MCP_JSON.write_text(json.dumps({"mcpServers": {}}, indent=2) + "\n", encoding="utf-8")
    return True, None


def prune_state_mcp(*, dry_run: bool, tools: list[str]) -> tuple[bool, bool]:
    db_path = global_state_db()
    if not db_path.is_file():
        return False, False

    conn = sqlite3.connect(str(db_path))
    try:
        app = _read_application_user(conn)
        if app is None:
            return False, False

        existing = app.get("mcpDisabledTools")
        merged = list(existing) if isinstance(existing, list) else []
        seen = set(merged)
        for entry in tools:
            if entry not in seen:
                merged.append(entry)
                seen.add(entry)

        allowed_cleared = False
        allowed = app.get("mcpAllowedTools")
        if isinstance(allowed, list) and allowed:
            app["mcpAllowedTools"] = []
            allowed_cleared = True

        if merged == (existing or []) and not allowed_cleared:
            return False, allowed_cleared

        app["mcpDisabledTools"] = merged
        if dry_run:
            return True, allowed_cleared

        _write_application_user(conn, app)
        conn.commit()
        return True, allowed_cleared
    finally:
        conn.close()


def _rmtree_resilient(path: Path) -> bool:
    """Remove a directory tree; tolerate read-only or locked files on Windows."""
    if not path.is_dir():
        return True

    def onexc(func, p, exc):
        if isinstance(exc, PermissionError):
            try:
                os.chmod(p, stat.S_IWRITE)
                func(p)
            except OSError:
                pass
            return
        raise exc

    shutil.rmtree(path, onexc=onexc)
    return not path.exists()


def prune_plugin_cache(*, dry_run: bool) -> list[str]:
    disabled: list[str] = []
    if not PLUGIN_CACHE_ROOT.is_dir():
        return disabled

    for name in sorted(DISABLE_PLUGIN_DIRS):
        src = PLUGIN_CACHE_ROOT / name
        dest = PLUGIN_CACHE_ROOT / f"{name}{DISABLED_SUFFIX}"
        if dest.is_dir():
            disabled.append(str(dest))
            if src.is_dir() and not dry_run:
                if not _rmtree_resilient(src):
                    print(
                        f"Warning: {src} still present (Cursor may have files locked). "
                        "Quit Cursor and re-run: bob prune-overhead --apply",
                        file=sys.stderr,
                    )
            continue
        if not src.is_dir():
            continue
        disabled.append(str(dest))
        if dry_run:
            continue
        try:
            src.rename(dest)
        except OSError as exc:
            if dest.is_dir():
                disabled.append(str(dest))
                if _rmtree_resilient(src):
                    continue
            print(f"Warning: could not disable plugin cache {src}: {exc}", file=sys.stderr)
    return disabled


def prune_installed_plugin_ids(*, dry_run: bool) -> tuple[list[str], int]:
    db_path = global_state_db()
    if not db_path.is_file():
        return [], 0

    removed: list[str] = []
    updated = 0
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT key, value FROM ItemTable WHERE key LIKE ?",
            (f"{PLUGIN_INSTALLED_PREFIX}%",),
        ).fetchall()
        for key, raw in rows:
            try:
                entries = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(entries, list):
                continue
            new_entries = [
                item
                for item in entries
                if not (
                    isinstance(item, dict)
                    and str(item.get("id", "")) in DISABLE_PLUGIN_IDS
                )
            ]
            if new_entries == entries:
                continue
            for item in entries:
                pid = str(item.get("id", "")) if isinstance(item, dict) else ""
                if pid in DISABLE_PLUGIN_IDS and pid not in removed:
                    removed.append(pid)
            updated += 1
            if not dry_run:
                conn.execute(
                    "UPDATE ItemTable SET value = ? WHERE key = ?",
                    (json.dumps(new_entries), key),
                )
        if not dry_run and updated:
            conn.commit()
    finally:
        conn.close()
    return removed, updated


def run_prune_cursor_overhead(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply Bob squad MCP/plugin policy.")
    parser.add_argument("--dry-run", action="store_true", help="Preview only.")
    parser.add_argument("--apply", action="store_true", help="Write changes.")
    ns = parser.parse_args(args or [])
    dry_run = ns.dry_run and not ns.apply

    audit = _build_mcp_audit()
    tools = all_non_keep_tools_to_disable()
    print(f"MCP tools to disable: {len(tools)} (keeping {', '.join(sorted(KEEP_MCP_SERVERS))})")
    if audit.pending_disable_tools:
        print(f"Policy pending on this machine: {len(audit.pending_disable_tools)} tools")
    for entry in tools:
        print(f"  - {entry}")

    if not dry_run:
        backup_db = _backup_file(global_state_db(), dry_run=False)
        if backup_db:
            print(f"Backed up state DB: {backup_db}")

    mcp_cleared, mcp_backup = prune_mcp_json(dry_run=dry_run)
    if mcp_cleared:
        verb = "Would clear" if dry_run else "Cleared"
        print(f"{verb} ~/.cursor/mcp.json user MCP servers.")
        if mcp_backup:
            print(f"  backup: {mcp_backup}")

    state_changed, allowed_cleared = prune_state_mcp(dry_run=dry_run, tools=tools)
    if state_changed:
        verb = "Would update" if dry_run else "Updated"
        print(f"{verb} mcpDisabledTools in state.vscdb ({len(tools)} entries).")
    if allowed_cleared:
        verb = "Would clear" if dry_run else "Cleared"
        print(f"{verb} mcpAllowedTools wildcard entries.")

    dirs = prune_plugin_cache(dry_run=dry_run)
    for d in dirs:
        verb = "Would disable plugin cache" if dry_run else "Disabled plugin cache"
        print(f"{verb}: {d}")

    removed, keys = prune_installed_plugin_ids(dry_run=dry_run)
    if removed:
        verb = "Would remove plugin IDs" if dry_run else "Removed plugin IDs"
        print(f"{verb}: {', '.join(removed)} ({keys} installedIds keys)")

    if dry_run:
        print("\nRe-run with --apply to write changes. Reload Cursor after applying.")
        print("Audit anytime: bob mcp-audit")
    else:
        print("\nDone. Reload Cursor so changes take effect.")
        print("Verify: bob mcp-audit")
    return 0
