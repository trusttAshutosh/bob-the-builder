"""Central Bob squad policy for Cursor MCP + plugin overhead (reads local state only).

Bob does not replace Cursor MCP servers or plugins. It discovers what is installed on
this machine and applies a small Novopay-backend squad policy so agents spend context
on ticket work, not browser/Postman/tldraw tooling Bob already covers locally.
"""
from __future__ import annotations

import glob
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from chat_hygiene import global_state_db
from cursor_plugins import RECOMMENDED_PLUGINS
from host_repo import runner_bootstrap_repo

APPLICATION_USER_KEY = (
    "src.vs.platform.reactivestorage.browser.reactiveStorageServiceImpl."
    "persistentStorage.applicationUser"
)
PLUGIN_INSTALLED_PREFIX = "cursor.plugins.installedIds.no-team|"
MCP_AUDIT_DOC = "docs/MCP_AUDIT.md"
MCP_JSON = Path.home() / ".cursor" / "mcp.json"
PLUGIN_CACHE_ROOT = Path.home() / ".cursor" / "plugins" / "cache" / "cursor-public"
MCP_PROJECTS_ROOT = Path.home() / ".cursor" / "projects"
DISABLED_SUFFIX = ".disabled-bob"

KEEP_MCP_SERVERS = frozenset({"cursor-app-control"})
DISABLE_MCP_SERVER_PREFIXES = (
    "cursor-ide-browser",
    "plugin-postman-postman",
    "plugin-tldraw-tldraw",
    "user-lumyst-",
    "cursor-backend-control",
)
DISABLE_PLUGIN_DIRS = frozenset({"postman", "tldraw"})
DISABLE_PLUGIN_IDS = frozenset({"788"})
KEEP_PLUGIN_DIRS = frozenset({"continual-learning", "cursor-team-kit", "superpowers"})

PLUGIN_SLUG_BY_NAME = {
    "Superpowers": "superpowers",
    "Cursor Team Kit": "cursor-team-kit",
    "Continual Learning": "continual-learning",
    "Postman": "postman",
}


@dataclass
class McpServerRecord:
    name: str
    tools: list[str]
    verdict: str
    reason: str
    tools_disabled: int = 0
    tools_pending_disable: int = 0


@dataclass
class PluginRecord:
    name: str
    cache_dir: str | None
    installed: bool
    disabled_by_bob: bool
    marketplace_id: str | None
    verdict: str
    reason: str
    tier: str


@dataclass
class McpAuditReport:
    generated_at: str
    mcp_servers: list[McpServerRecord] = field(default_factory=list)
    plugins: list[PluginRecord] = field(default_factory=list)
    user_mcp_json_servers: list[str] = field(default_factory=list)
    disabled_tools_in_state: list[str] = field(default_factory=list)
    allowed_tools_in_state: list[str] = field(default_factory=list)
    recommended_disable_tools: list[str] = field(default_factory=list)
    pending_disable_tools: list[str] = field(default_factory=list)
    error: str | None = None


def _plugin_cache_name(path: Path) -> str:
    name = path.name
    if name.endswith(DISABLED_SUFFIX):
        return name[: -len(DISABLED_SUFFIX)]
    return name


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


def read_mcp_state() -> tuple[list[str], list[str]]:
    db_path = global_state_db()
    if not db_path.is_file():
        return [], []
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        app = _read_application_user(conn)
        if not app:
            return [], []
        disabled = app.get("mcpDisabledTools")
        allowed = app.get("mcpAllowedTools")
        disabled_list = list(disabled) if isinstance(disabled, list) else []
        allowed_list = list(allowed) if isinstance(allowed, list) else []
        return disabled_list, allowed_list
    finally:
        conn.close()


def read_user_mcp_json_servers() -> list[str]:
    if not MCP_JSON.is_file():
        return []
    try:
        payload = json.loads(MCP_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    servers = payload.get("mcpServers")
    if not isinstance(servers, dict):
        return []
    return sorted(str(k) for k in servers.keys())


def discover_mcp_servers() -> dict[str, list[str]]:
    servers: dict[str, list[str]] = {}
    pattern = str(MCP_PROJECTS_ROOT / "*" / "mcps" / "*" / "tools" / "*.json")
    for path_str in sorted(glob.glob(pattern)):
        parts = Path(path_str).parts
        try:
            idx = parts.index("mcps")
            server = parts[idx + 1]
            tool = Path(path_str).stem
        except ValueError:
            continue
        servers.setdefault(server, [])
        if tool not in servers[server]:
            servers[server].append(tool)
    for name in servers:
        servers[name].sort()
    return servers


def classify_mcp_server(name: str) -> tuple[str, str]:
    if name in KEEP_MCP_SERVERS:
        return "keep", "Needed for Bob workspace orchestration (move_agent_to_root)."
    for prefix in DISABLE_MCP_SERVER_PREFIXES:
        if name == prefix or name.startswith(prefix):
            if "postman" in name:
                return "disable", "Bob writes local Postman collections per ticket; cloud MCP adds context."
            if "browser" in name:
                return "disable", "Backend TDD uses Bob + curl/DB checks, not browser automation."
            if "tldraw" in name:
                return "disable", "Visual canvas is not used in Novopay backend ticket flow."
            if "lumyst" in name:
                return "disable", "Local Lumyst server is rarely running; adds dead MCP tools."
            if "backend-control" in name:
                return "disable", "No tools exposed; still costs context metadata."
            return "disable", "Not in Bob Novopay backend squad policy."
    return "review", "Unknown MCP server - confirm you need it; otherwise disable via `bob prune-overhead`."


def recommended_tools_to_disable(servers: dict[str, list[str]] | None = None) -> list[str]:
    discovered = servers if servers is not None else discover_mcp_servers()
    disabled: list[str] = []
    seen: set[str] = set()
    for server, tools in discovered.items():
        if server in KEEP_MCP_SERVERS:
            continue
        verdict, _ = classify_mcp_server(server)
        if verdict == "review":
            continue
        for tool in tools:
            entry = f"{server}|{tool}"
            if entry not in seen:
                seen.add(entry)
                disabled.append(entry)
    return sorted(disabled)


def all_non_keep_tools_to_disable(servers: dict[str, list[str]] | None = None) -> list[str]:
    """Aggressive list for prune-overhead: every tool not on KEEP_MCP_SERVERS."""
    discovered = servers if servers is not None else discover_mcp_servers()
    disabled: list[str] = []
    seen: set[str] = set()
    for server, tools in discovered.items():
        if server in KEEP_MCP_SERVERS:
            continue
        for tool in tools:
            entry = f"{server}|{tool}"
            if entry not in seen:
                seen.add(entry)
                disabled.append(entry)
    return sorted(disabled)


def discover_plugin_ids_from_mcp() -> dict[str, str]:
    mapping: dict[str, str] = {}
    pattern = str(MCP_PROJECTS_ROOT / "*" / "mcps" / "*" / "tools" / "*.json")
    for path_str in glob.glob(pattern):
        try:
            payload = json.loads(Path(path_str).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        plugin_id = payload.get("pluginId")
        if not plugin_id:
            continue
        parts = Path(path_str).parts
        idx = parts.index("mcps")
        server = parts[idx + 1]
        if server.startswith("plugin-"):
            slug = server.removeprefix("plugin-").rsplit("-", 1)[0]
            mapping[slug] = str(plugin_id)
    return mapping


def discover_installed_plugin_ids() -> set[str]:
    db_path = global_state_db()
    if not db_path.is_file():
        return set()
    ids: set[str] = set()
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT value FROM ItemTable WHERE key LIKE ?",
            (f"{PLUGIN_INSTALLED_PREFIX}%",),
        ).fetchall()
        for (raw,) in rows:
            try:
                entries = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(entries, list):
                continue
            for item in entries:
                if isinstance(item, dict) and item.get("id") is not None:
                    ids.add(str(item["id"]))
    finally:
        conn.close()
    return ids


def discover_plugins() -> list[PluginRecord]:
    installed_ids = discover_installed_plugin_ids()
    mcp_plugin_ids = discover_plugin_ids_from_mcp()
    cache_dirs: dict[str, Path] = {}
    if PLUGIN_CACHE_ROOT.is_dir():
        for path in PLUGIN_CACHE_ROOT.iterdir():
            if path.is_dir():
                cache_dirs[_plugin_cache_name(path)] = path

    records: list[PluginRecord] = []
    seen_slugs: set[str] = set()

    for plug in RECOMMENDED_PLUGINS:
        slug = PLUGIN_SLUG_BY_NAME.get(plug.name, plug.marketplace_search.replace(" ", "-"))
        cache_path = cache_dirs.get(slug)
        disabled_by_bob = bool(cache_path and cache_path.name.endswith(DISABLED_SUFFIX))
        marketplace_id = mcp_plugin_ids.get(slug)
        installed = bool(marketplace_id and marketplace_id in installed_ids) or bool(cache_path)
        if plug.tier == "recommended":
            verdict = "keep"
            reason = plug.summary
        else:
            verdict = "disable"
            reason = plug.summary
        if disabled_by_bob:
            verdict = "disabled"
            reason = f"Already disabled by Bob ({DISABLED_SUFFIX})."
        elif cache_path and slug in DISABLE_PLUGIN_DIRS and plug.tier != "recommended":
            verdict = "disable"
        records.append(
            PluginRecord(
                name=plug.name,
                cache_dir=cache_path.name if cache_path else None,
                installed=installed,
                disabled_by_bob=disabled_by_bob,
                marketplace_id=marketplace_id,
                verdict=verdict,
                reason=reason,
                tier=plug.tier,
            )
        )
        seen_slugs.add(slug)

    for slug, path in sorted(cache_dirs.items()):
        if slug in seen_slugs or slug in KEEP_PLUGIN_DIRS:
            continue
        if slug in DISABLE_PLUGIN_DIRS:
            records.append(
                PluginRecord(
                    name=slug,
                    cache_dir=path.name,
                    installed=True,
                    disabled_by_bob=path.name.endswith(DISABLED_SUFFIX),
                    marketplace_id=mcp_plugin_ids.get(slug),
                    verdict="disabled" if path.name.endswith(DISABLED_SUFFIX) else "disable",
                    reason="Optional/noise plugin for Novopay backend Bob workflow.",
                    tier="optional",
                )
            )
    return records


def build_mcp_audit() -> McpAuditReport:
    report = McpAuditReport(generated_at=datetime.now(timezone.utc).isoformat())
    try:
        servers = discover_mcp_servers()
        disabled_state, allowed_state = read_mcp_state()
        report.disabled_tools_in_state = sorted(disabled_state)
        report.allowed_tools_in_state = sorted(allowed_state)
        report.user_mcp_json_servers = read_user_mcp_json_servers()
        report.recommended_disable_tools = recommended_tools_to_disable(servers)
        disabled_set = set(disabled_state)
        report.pending_disable_tools = [
            t for t in report.recommended_disable_tools if t not in disabled_set
        ]

        for name, tools in sorted(servers.items()):
            verdict, reason = classify_mcp_server(name)
            tool_entries = [f"{name}|{t}" for t in tools]
            report.mcp_servers.append(
                McpServerRecord(
                    name=name,
                    tools=tools,
                    verdict=verdict,
                    reason=reason,
                    tools_disabled=sum(1 for e in tool_entries if e in disabled_set),
                    tools_pending_disable=sum(
                        1 for e in tool_entries if e in report.pending_disable_tools
                    ),
                )
            )

        report.plugins = discover_plugins()
    except OSError as exc:
        report.error = str(exc)
    return report


def build_mcp_audit_suggestions(report: McpAuditReport) -> list[str]:
    if report.error:
        return [f"MCP audit failed: {report.error}"]

    suggestions: list[str] = []
    if report.pending_disable_tools:
        suggestions.append(
            f"{len(report.pending_disable_tools)} MCP tools still enabled in Cursor state - "
            "run `bob prune-overhead --apply` then reload Cursor."
        )
    if report.user_mcp_json_servers:
        labels = ", ".join(report.user_mcp_json_servers)
        suggestions.append(
            f"User mcp.json defines servers ({labels}) - Bob clears unused entries on prune-overhead."
        )
    if report.allowed_tools_in_state:
        suggestions.append(
            "mcpAllowedTools wildcards are set - prune-overhead clears them to avoid forced MCP load."
        )

    noisy = [p for p in report.plugins if p.verdict == "disable" and p.installed and not p.disabled_by_bob]
    if noisy:
        names = ", ".join(p.name for p in noisy)
        suggestions.append(f"Noisy plugins still active: {names} - run `bob prune-overhead --apply`.")

    missing = [
        p.name
        for p in report.plugins
        if p.tier == "recommended" and p.verdict == "keep" and not p.installed and not p.disabled_by_bob
    ]
    if missing:
        suggestions.append(
            f"Recommended plugins missing: {', '.join(missing)} - run `bob plugins` and install once."
        )

    review = [s for s in report.mcp_servers if s.verdict == "review"]
    if review:
        names = ", ".join(s.name for s in review)
        suggestions.append(f"Review unknown MCP servers: {names}.")

    if not suggestions:
        suggestions.append("MCP/plugin overhead matches Bob squad policy on this machine.")
    return suggestions


def render_mcp_audit_md(report: McpAuditReport) -> str:
    lines = [
        "# Cursor MCP + plugin audit (Bob squad policy)",
        "",
        f"Generated: {report.generated_at}",
        "",
        "Bob reads **local** Cursor state on this machine only. It does not install or run MCP servers.",
        "Policy targets Novopay **backend** work: keep orchestration + recommended plugins;",
        "disable browser, Postman cloud MCP, tldraw, lumyst, and other context-heavy tooling Bob replaces.",
        "",
    ]
    if report.error:
        lines.extend(["## Error", "", report.error, ""])
        return "\n".join(lines)

    keep_servers = [s for s in report.mcp_servers if s.verdict == "keep"]
    disable_servers = [s for s in report.mcp_servers if s.verdict == "disable"]
    review_servers = [s for s in report.mcp_servers if s.verdict == "review"]

    lines.extend(
        [
            "## Summary",
            "",
            f"- **MCP servers discovered:** {len(report.mcp_servers)}",
            f"- **Tools to disable (policy):** {len(report.recommended_disable_tools)}",
            f"- **Already disabled in state:** {len(report.disabled_tools_in_state)}",
            f"- **Still pending disable:** {len(report.pending_disable_tools)}",
            f"- **user mcp.json servers:** {len(report.user_mcp_json_servers)}",
            "",
            "## MCP servers - keep",
            "",
        ]
    )
    if keep_servers:
        lines.append("| Server | Tools | Reason |")
        lines.append("|--------|------:|--------|")
        for s in keep_servers:
            lines.append(f"| `{s.name}` | {len(s.tools)} | {s.reason} |")
    else:
        lines.append("- None detected")

    lines.extend(["", "## MCP servers - disable", "", "| Server | Tools | Disabled | Pending | Reason |", "|--------|------:|-----------|--------:|--------|"])
    if disable_servers:
        for s in disable_servers:
            lines.append(
                f"| `{s.name}` | {len(s.tools)} | {s.tools_disabled} | {s.tools_pending_disable} | {s.reason} |"
            )
    else:
        lines.append("| - | 0 | 0 | 0 | None |")

    lines.extend(["", "## MCP servers - review", ""])
    if review_servers:
        for s in review_servers:
            lines.append(f"- `{s.name}` ({len(s.tools)} tools) - {s.reason}")
    else:
        lines.append("- None")

    lines.extend(["", "## Plugins", "", "| Plugin | Tier | Verdict | Installed | Reason |", "|--------|------|---------|-----------|--------|"])
    for p in report.plugins:
        inst = "yes" if p.installed else "no"
        if p.disabled_by_bob:
            inst = "disabled-bob"
        lines.append(f"| {p.name} | {p.tier} | {p.verdict} | {inst} | {p.reason} |")

    if report.user_mcp_json_servers:
        lines.extend(["", "## user mcp.json", ""])
        for name in report.user_mcp_json_servers:
            lines.append(f"- `{name}`")

    if report.pending_disable_tools:
        lines.extend(["", "## Pending MCP tool disables", ""])
        for entry in report.pending_disable_tools[:40]:
            lines.append(f"- `{entry}`")
        if len(report.pending_disable_tools) > 40:
            lines.append(f"- ... and {len(report.pending_disable_tools) - 40} more")

    lines.extend(["", "## Recommendations", ""])
    for i, sug in enumerate(build_mcp_audit_suggestions(report), 1):
        lines.append(f"{i}. {sug}")

    lines.extend(
        [
            "",
            "---",
            "",
            "Audit: `bob mcp-audit` - fix: `bob prune-overhead --apply` - reload Cursor after apply.",
            "",
        ]
    )
    return "\n".join(lines)


def render_mcp_audit_summary_md(report: McpAuditReport) -> list[str]:
    lines = ["", "## Cursor MCP + plugins", ""]
    if report.error:
        lines.append(f"- Audit skipped: {report.error}")
        return lines

    lines.extend(
        [
            f"- **MCP servers:** {len(report.mcp_servers)} discovered; "
            f"**{len(report.pending_disable_tools)}** tools still pending disable",
            f"- **user mcp.json:** {len(report.user_mcp_json_servers)} server(s)",
        ]
    )
    noisy = [p.name for p in report.plugins if p.verdict == "disable" and p.installed and not p.disabled_by_bob]
    if noisy:
        lines.append(f"- **Noisy plugins active:** {', '.join(noisy)}")
    lines.append(f"- Full report: [MCP_AUDIT.md]({MCP_AUDIT_DOC})")
    return lines


def print_mcp_audit_terminal(report: McpAuditReport) -> None:
    if report.error:
        print(f"MCP audit error: {report.error}")
        return

    print("Bob squad policy (Novopay backend) - local machine scan")
    print(f"  MCP servers: {len(report.mcp_servers)}")
    print(f"  Pending tool disables: {len(report.pending_disable_tools)}")
    print()

    print("KEEP MCP:")
    for s in report.mcp_servers:
        if s.verdict != "keep":
            continue
        print(f"  {s.name} ({len(s.tools)} tools) - {s.reason}")

    print("\nDISABLE MCP:")
    for s in report.mcp_servers:
        if s.verdict != "disable":
            continue
        pending = s.tools_pending_disable
        print(f"  {s.name} ({len(s.tools)} tools, {pending} pending) - {s.reason}")

    if any(s.verdict == "review" for s in report.mcp_servers):
        print("\nREVIEW MCP:")
        for s in report.mcp_servers:
            if s.verdict != "review":
                continue
            print(f"  {s.name} ({len(s.tools)} tools) - {s.reason}")

    print("\nPLUGINS:")
    for p in report.plugins:
        flag = ""
        if p.disabled_by_bob:
            flag = " [disabled-bob]"
        elif p.installed:
            flag = " [installed]"
        print(f"  [{p.verdict.upper()}] {p.name}{flag} - {p.reason}")

    if report.user_mcp_json_servers:
        print("\nuser mcp.json servers:")
        for name in report.user_mcp_json_servers:
            print(f"  - {name}")

    print("\nRecommendations:")
    for i, sug in enumerate(build_mcp_audit_suggestions(report), 1):
        print(f"  {i}. {sug}")

    if report.pending_disable_tools:
        print("\nFix: bob prune-overhead --apply  (then reload Cursor)")


def run_mcp_audit(args: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Audit Cursor MCP + plugin overhead.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write MCP_AUDIT.md.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary to stdout.")
    ns = parser.parse_args(args or [])

    report = build_mcp_audit()

    if ns.json:
        payload = {
            "generated_at": report.generated_at,
            "error": report.error,
            "mcp_servers": [
                {
                    "name": s.name,
                    "tools": s.tools,
                    "verdict": s.verdict,
                    "reason": s.reason,
                    "tools_disabled": s.tools_disabled,
                    "tools_pending_disable": s.tools_pending_disable,
                }
                for s in report.mcp_servers
            ],
            "plugins": [
                {
                    "name": p.name,
                    "verdict": p.verdict,
                    "tier": p.tier,
                    "installed": p.installed,
                    "disabled_by_bob": p.disabled_by_bob,
                    "reason": p.reason,
                }
                for p in report.plugins
            ],
            "pending_disable_tools": report.pending_disable_tools,
            "user_mcp_json_servers": report.user_mcp_json_servers,
            "suggestions": build_mcp_audit_suggestions(report),
        }
        print(json.dumps(payload, indent=2))
        return 0

    print_mcp_audit_terminal(report)

    if ns.dry_run:
        print("\n(dry-run - MCP_AUDIT.md not written)")
        return 0

    text = render_mcp_audit_md(report)
    out = runner_bootstrap_repo() / MCP_AUDIT_DOC
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"\nWrote {out}")
    return 0
