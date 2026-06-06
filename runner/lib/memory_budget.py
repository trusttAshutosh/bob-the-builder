"""Working memory budgeting for Cursor + Bob (measure, nudge, agent rules)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from context_audit import (
    CONTEXT_LIMIT,
    FIXED_TOTAL,
    build_context_audit,
    build_context_suggestions,
)
from cursor_overhead import discover_mcp_servers, recommended_tools_to_disable
from host_repo import infer_workspace_root, runner_bootstrap_repo

MEMORY_BUDGET_DOC = "docs/MEMORY_BUDGET.md"
WORKSPACE_STATUS_REL = ".cursor/memory-budget-status.json"

WARN_PCT = 60.0
CRITICAL_PCT = 80.0
TARGET_ACTIVE_CHATS = 8
TARGET_PINNED_WINDOW = 8


@dataclass
class MemoryBudgetReport:
    generated_at: str
    workspace: str | None = None
    status: str = "ok"  # ok | warn | critical
    active_chats: int = 0
    active_high_count: int = 0
    worst_active_pct: float | None = None
    fixed_overhead_tokens: int = FIXED_TOTAL
    mcp_server_count: int = 0
    mcp_tools_recommended_disable: int = 0
    alerts: list[str] = field(default_factory=list)
    habits: list[str] = field(default_factory=list)
    context_suggestions: list[str] = field(default_factory=list)
    error: str | None = None


def default_habits() -> list[str]:
    return [
        "One active ticket per chat; archive the thread when switching tickets.",
        "Pin only ticket-spec + 1-2 files; never @ the whole repo or unrelated docs/tdd-runs.",
        "Run `bob context --ticket <id>` once; link REPORT paths instead of pasting logs.",
        "Gate 3: read GATE_SUMMARY + REPORT summary (5 lines), not full Gradle output in chat.",
        "Keep pinned + today + yesterday at ~6-8 active chats (`bob chat-hygiene --auto`).",
        "Run `bob prune-overhead --apply` after onboard if MCP tool count is high.",
    ]


def four_bucket_guide() -> list[str]:
    return [
        "**Bucket A (fixed, small):** orchestrator rule, active ticket id, gate checklist.",
        "**Bucket B (session):** ticket-spec.yaml, changed files, last Bob REPORT summary.",
        "**Bucket C (on demand):** one API YAML, one DB verify SQL, `bob query-graph` slice.",
        "**Bucket D (never load):** full repo @, stale chats, unrelated tickets, raw boot logs.",
        f"**Target:** active chat context **<{WARN_PCT:.0f}%**; investigate at **>={CRITICAL_PCT:.0f}%**.",
    ]


def build_memory_budget_report() -> MemoryBudgetReport:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    ws = infer_workspace_root()
    ctx = build_context_audit()
    report = MemoryBudgetReport(
        generated_at=now,
        workspace=str(ws) if ws else None,
        habits=default_habits(),
    )

    if ctx.error:
        report.error = ctx.error
        report.status = "warn"
        report.alerts.append(f"Context audit unavailable: {ctx.error}")
        return report

    report.active_chats = ctx.active_chats
    report.active_high_count = ctx.active_high_count
    report.context_suggestions = build_context_suggestions(ctx)

    worst: float | None = None
    for chat in ctx.active_high_chats:
        if worst is None or chat.pct > worst:
            worst = chat.pct
    for chat in ctx.top_chats:
        if chat.archived:
            continue
        if worst is None or chat.pct > worst:
            worst = chat.pct
    report.worst_active_pct = worst

    servers = discover_mcp_servers()
    report.mcp_server_count = len(servers)
    report.mcp_tools_recommended_disable = len(recommended_tools_to_disable(servers))

    if report.active_chats > TARGET_ACTIVE_CHATS:
        report.alerts.append(
            f"{report.active_chats} active chats (target <= {TARGET_ACTIVE_CHATS}) - run `bob chat-hygiene --auto`."
        )
    if report.active_high_count:
        report.alerts.append(
            f"{report.active_high_count} active chat(s) at >= {WARN_PCT:.0f}% context."
        )
    if worst is not None and worst >= CRITICAL_PCT:
        report.status = "critical"
        report.alerts.append(
            f"Worst active chat at {worst:.0f}% - start a fresh chat for the next task."
        )
    elif worst is not None and worst >= WARN_PCT:
        report.status = "warn"
    elif report.active_high_count or report.active_chats > TARGET_ACTIVE_CHATS:
        report.status = "warn"

    if report.mcp_tools_recommended_disable >= 8:
        report.alerts.append(
            f"{report.mcp_tools_recommended_disable} MCP tools flagged for disable - `bob prune-overhead --dry-run`."
        )
        if report.status == "ok":
            report.status = "warn"

    if not report.alerts:
        report.alerts.append("Within squad memory budget targets.")

    return report


def workspace_status_path(workspace: Path | None = None) -> Path | None:
    ws = workspace or infer_workspace_root()
    if not ws:
        return None
    return ws / WORKSPACE_STATUS_REL


def write_workspace_status(report: MemoryBudgetReport, workspace: Path | None = None) -> Path | None:
    dest = workspace_status_path(workspace)
    if not dest:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": report.generated_at,
        "status": report.status,
        "active_chats": report.active_chats,
        "active_high_count": report.active_high_count,
        "worst_active_pct": report.worst_active_pct,
        "alerts": report.alerts[:6],
        "commands": [
            "bob memory-budget",
            "bob chat-hygiene --auto",
            "bob context-audit",
            "bob prune-overhead --dry-run",
        ],
    }
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return dest


def render_memory_budget_md(report: MemoryBudgetReport) -> str:
    lines = [
        "# Working memory budget (Cursor + Bob)",
        "",
        f"**Generated:** {report.generated_at}",
        "",
        "## Status",
        "",
        f"- **Overall:** `{report.status}`",
        f"- **Active chats:** {report.active_chats} (target <= {TARGET_ACTIVE_CHATS})",
        f"- **Active chats >= {WARN_PCT:.0f}% context:** {report.active_high_count}",
    ]
    if report.worst_active_pct is not None:
        lines.append(
            f"- **Worst active chat:** {report.worst_active_pct:.1f}% "
            f"(~{int(CONTEXT_LIMIT * report.worst_active_pct / 100) // 1000}K / 200K tokens)"
        )
    lines.extend(
        [
            f"- **Fixed Cursor overhead (every chat):** ~{report.fixed_overhead_tokens // 1000}K tokens",
            f"- **MCP servers discovered:** {report.mcp_server_count}",
            f"- **MCP tools Bob suggests disabling:** {report.mcp_tools_recommended_disable}",
            "",
            "## Alerts",
            "",
        ]
    )
    for alert in report.alerts:
        lines.append(f"- {alert}")
    lines.extend(["", "## Four buckets", ""])
    lines.extend(f"- {row}" for row in four_bucket_guide())
    lines.extend(["", "## Agent habits (squad)", ""])
    for habit in report.habits:
        lines.append(f"- {habit}")
    if report.context_suggestions:
        lines.extend(["", "## Context audit hints", ""])
        for item in report.context_suggestions[:5]:
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Commands",
            "",
            "```bash",
            "bob memory-budget              # this report",
            "bob context-audit              # per-chat context % detail",
            "bob chat-hygiene --auto        # archive stale / cap active chats",
            "bob prune-overhead --apply     # trim MCP/plugin overhead (reload Cursor)",
            "bob context --ticket <id>      # scoped CONTEXT_PACK (do not paste whole file)",
            "```",
            "",
            "Workspace status file (session hook): `.cursor/memory-budget-status.json`",
            "",
            "Re-run after heavy multi-day threads or before starting a new ticket.",
        ]
    )
    if report.error:
        lines.extend(["", "## Error", "", f"- {report.error}", ""])
    return "\n".join(lines) + "\n"


def format_agent_context_section() -> list[str]:
    """Short block for CONTEXT_PACK.md - keeps agent rules in ticket artifact, not chat."""
    lines = [
        "## Memory budget (agent load rules)",
        "",
        "Keep this chat under ~60% context. Do not paste Bob logs or whole CONTEXT_PACK into chat.",
        "",
    ]
    for habit in default_habits()[:4]:
        lines.append(f"- {habit}")
    lines.append("")
    return lines


def run_memory_budget_hook_session() -> int:
    report = build_memory_budget_report()
    write_workspace_status(report)
    return 0


def run_memory_budget(args: list[str]) -> int:
    dry_run = "--dry-run" in args
    as_json = "--json" in args
    hook_session = "--hook" in args and "session" in args

    if hook_session:
        return run_memory_budget_hook_session()

    report = build_memory_budget_report()
    write_workspace_status(report)

    if as_json:
        print(
            json.dumps(
                {
                    "status": report.status,
                    "active_chats": report.active_chats,
                    "active_high_count": report.active_high_count,
                    "worst_active_pct": report.worst_active_pct,
                    "alerts": report.alerts,
                },
                indent=2,
            )
        )
        return 0 if report.status == "ok" else 1

    text = render_memory_budget_md(report)
    if dry_run:
        print(text)
        return 0

    out = runner_bootstrap_repo() / MEMORY_BUDGET_DOC
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {out}")
    if report.status != "ok":
        print(f"Memory budget: {report.status.upper()} - see alerts in {out}")
        for alert in report.alerts[:3]:
            print(f"  - {alert}")
    else:
        print("Memory budget: OK")
    status = workspace_status_path()
    if status:
        print(f"Workspace status: {status}")
    return 0 if report.status == "ok" else 1
