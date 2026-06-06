"""bob meta-review — squad usage audit (suggestions only; human approves changes)."""
from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chat_hygiene import parse_hook_stop_json
from context_audit import (
    CONTEXT_AUDIT_DOC,
    ContextAuditReport,
    build_context_audit,
    build_context_suggestions,
    render_context_audit_md,
    render_context_audit_summary_md,
)
from cursor_overhead import (
    MCP_AUDIT_DOC,
    McpAuditReport,
    build_mcp_audit,
    build_mcp_audit_suggestions,
    discover_plugins,
    render_mcp_audit_md,
    render_mcp_audit_summary_md,
)
from cursor_plugins import RECOMMENDED_PLUGINS
from host_repo import infer_workspace_root, runner_bootstrap_repo
from run_summary import load_last_summary

META_DOC = "docs/META_REVIEW.md"
META_REVIEW_STATE_REL = Path(".cursor/hooks/state/meta-review.json")
META_REVIEW_INTERVAL_DAYS = 30
BOOT_FAIL_KEYWORDS = (
    "health",
    "boot",
    "bootrun",
    "gradle",
    "wiremock",
    "mysql",
    "kafka",
    "redis",
    "peer",
    "service",
)
CHAT_KEYWORDS = (
    "validate-ticket",
    "bob onboard",
    "bob meta-review",
    "workflow-from-chats",
    "GATE_SUMMARY",
    "plugin",
    "onboard",
    "meta-review",
)
OPEN_NEXT_RE = re.compile(r"^- \[ \] \*\*(.+?)\*\*")
DONE_NEXT_RE = re.compile(r"^- \[x\] \*\*(.+?)\*\*", re.I)
PLUGIN_INFO_RE = re.compile(r"<plugin_info[\s\S]*?</plugin_info>\s*", re.I)


@dataclass
class TicketStat:
    ticket_id: str
    host_repo: str
    overall: str
    finished_at: str
    title: str
    boot_failures: list[str] = field(default_factory=list)


@dataclass
class MetaReviewReport:
    generated_at: str
    workspace: str | None
    days_window: int = 30
    tickets: list[TicketStat] = field(default_factory=list)
    boot_failure_counts: Counter[str] = field(default_factory=Counter)
    next_open: list[tuple[str, str]] = field(default_factory=list)
    next_sections: Counter[str] = field(default_factory=Counter)
    rule_drift: str | None = None
    hooks_ok: bool | None = None
    skill_duplicates: list[str] = field(default_factory=list)
    plugin_signals: dict[str, str] = field(default_factory=dict)
    chat_parent_count: int = 0
    chat_keyword_hits: Counter[str] = field(default_factory=Counter)
    context_audit: ContextAuditReport | None = None
    mcp_audit: McpAuditReport | None = None
    suggestions: list[str] = field(default_factory=list)


def _resolve_workspace() -> Path | None:
    from host_repo import workspace_root

    ws = workspace_root() or infer_workspace_root()
    return ws.resolve() if ws and ws.is_dir() else None


def _normalize_rule_text(text: str, workspace: Path | None) -> str:
    out = text.replace("\r\n", "\n").strip()
    if workspace:
        ws = str(workspace.resolve())
        out = out.replace(ws, "{{WORKSPACE_ROOT}}")
        out = out.replace(ws.replace("\\", "/"), "{{WORKSPACE_ROOT}}")
        # Legacy hardcoded path from early squad template
        out = out.replace("Desktop/novopay", "{{WORKSPACE_NAME}}")
        out = re.sub(r"C:\\Users\\[^\\]+\\Desktop\\novopay", "{{WORKSPACE_ROOT}}", out)
    return out


def _template_rule_path() -> Path:
    return (
        runner_bootstrap_repo()
        / "templates"
        / "onboarding"
        / "cursor"
        / "novopay-orchestrator.mdc"
    )


def assess_rule_drift(workspace: Path | None) -> str | None:
    user_rule = Path.home() / ".cursor" / "rules" / "novopay-orchestrator.mdc"
    template = _template_rule_path()
    if not user_rule.is_file():
        return "missing user rule (~/.cursor/rules/novopay-orchestrator.mdc)"
    if not template.is_file():
        return None
    user_norm = _normalize_rule_text(user_rule.read_text(encoding="utf-8"), workspace)
    tpl_norm = _normalize_rule_text(template.read_text(encoding="utf-8"), workspace)
    if user_norm == tpl_norm:
        return None
    return "user rule differs from bob-the-builder/templates/onboarding/cursor/novopay-orchestrator.mdc"


def assess_hooks() -> bool | None:
    from cursor_hook import hooks_assess_ok

    return hooks_assess_ok()


def find_skill_duplicates(workspace: Path) -> list[str]:
    canonical = (workspace / ".cursor" / "skills").resolve()
    if not canonical.is_dir():
        return []
    duplicates: list[str] = []
    for child in workspace.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        skills = child / ".cursor" / "skills"
        if not skills.is_dir():
            continue
        try:
            if skills.resolve() == canonical:
                continue
        except OSError:
            pass
        if any(skills.rglob("SKILL.md")):
            duplicates.append(f"{child.name}/.cursor/skills (not junctioned to workspace canonical)")
    return duplicates


def find_ticket_dirs(workspace: Path) -> list[tuple[Path, str]]:
    rows: list[tuple[Path, str]] = []
    for child in sorted(workspace.iterdir()):
        if not child.is_dir():
            continue
        tdd = child / "docs" / "tdd-runs"
        if not tdd.is_dir():
            continue
        host = child.name
        for ticket_dir in sorted(tdd.iterdir()):
            if ticket_dir.is_dir() and not ticket_dir.name.startswith("."):
                rows.append((ticket_dir, host))
    return rows


def _boot_failures(steps: list[dict]) -> list[str]:
    fails: list[str] = []
    for step in steps:
        status = str(step.get("status", "")).lower()
        if status not in ("fail", "error"):
            continue
        label = str(step.get("label") or step.get("id") or "step")
        low = label.lower()
        if any(k in low for k in BOOT_FAIL_KEYWORDS):
            fails.append(label)
    return fails


def collect_ticket_stats(workspace: Path) -> list[TicketStat]:
    stats: list[TicketStat] = []
    for ticket_dir, host in find_ticket_dirs(workspace):
        data = load_last_summary(ticket_dir)
        if data:
            steps = data.get("steps") or []
            stats.append(
                TicketStat(
                    ticket_id=str(data.get("ticket_id") or ticket_dir.name),
                    host_repo=host,
                    overall=str(data.get("overall", "?")),
                    finished_at=str(data.get("finished_at", ""))[:19],
                    title=str(data.get("title", ""))[:60],
                    boot_failures=_boot_failures(steps),
                )
            )
        elif (ticket_dir / "ticket-spec.yaml").exists():
            stats.append(
                TicketStat(
                    ticket_id=ticket_dir.name,
                    host_repo=host,
                    overall="NEVER",
                    finished_at="",
                    title="",
                )
            )
    return stats


def parse_next_backlog(path: Path) -> tuple[list[tuple[str, str]], Counter[str]]:
    if not path.is_file():
        return [], Counter()
    open_items: list[tuple[str, str]] = []
    sections: Counter[str] = Counter()
    section = "other"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## Adding items"):
            break
        if line.startswith("## Now"):
            section = "Now"
            continue
        if line.startswith("## Next"):
            section = "Next"
            continue
        if line.startswith("## Later"):
            section = "Later"
            continue
        if line.startswith("## Done"):
            section = "Done"
            continue
        if section == "Done":
            continue
        m = OPEN_NEXT_RE.match(line.strip())
        if m and section in ("Now", "Next", "Later"):
            open_items.append((section, m.group(1)))
            sections[section] += 1
    return open_items, sections


def detect_plugin_cache_signals() -> dict[str, str]:
    signals: dict[str, str] = {}
    for record in discover_plugins():
        if record.disabled_by_bob:
            signals[record.name] = f"disabled by Bob ({record.cache_dir})"
        elif record.cache_dir:
            signals[record.name] = f"cache present ({record.cache_dir})"
        elif record.tier == "recommended":
            signals[record.name] = "not detected in local plugin cache"
        else:
            signals[record.name] = "optional - not detected"
    if not signals:
        return {p.name: "no plugin cache dir" for p in RECOMMENDED_PLUGINS if p.tier == "recommended"}
    return signals


def _strip_user_text(raw: str) -> str:
    text = PLUGIN_INFO_RE.sub("", raw)
    if "<user_query>" in text:
        start = text.find("<user_query>") + len("<user_query>")
        end = text.find("</user_query>")
        if end > start:
            text = text[start:end]
    return text.lower()


def scan_chat_patterns(*, days: int, workspace: Path | None) -> tuple[int, Counter[str]]:
    projects_root = Path.home() / ".cursor" / "projects"
    if not projects_root.is_dir():
        return 0, Counter()

    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    keyword_hits: Counter[str] = Counter()
    parent_count = 0
    ws_token = workspace.name.lower() if workspace else ""

    for project_dir in projects_root.iterdir():
        if not project_dir.is_dir():
            continue
        if ws_token and ws_token not in project_dir.name.lower() and "novopay" not in project_dir.name.lower():
            continue
        transcripts = project_dir / "agent-transcripts"
        if not transcripts.is_dir():
            continue
        for jsonl in transcripts.glob("*/*.jsonl"):
            if "subagents" in jsonl.parts:
                continue
            try:
                if jsonl.stat().st_mtime < cutoff:
                    continue
            except OSError:
                continue
            parent_count += 1
            try:
                lines = jsonl.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            blob = []
            for line in lines[:200]:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("role") != "user":
                    continue
                msg = row.get("message") or {}
                for part in msg.get("content") or []:
                    if part.get("type") == "text":
                        blob.append(_strip_user_text(str(part.get("text", ""))))
            combined = "\n".join(blob)
            for kw in CHAT_KEYWORDS:
                if kw.lower() in combined:
                    keyword_hits[kw] += 1
    return parent_count, keyword_hits


def _ticket_pass_rate(tickets: list[TicketStat]) -> tuple[int, int, int, float | None]:
    ran = [t for t in tickets if t.overall != "NEVER"]
    if not ran:
        return 0, 0, len(tickets), None
    passed = sum(1 for t in ran if t.overall == "PASS")
    failed = sum(1 for t in ran if t.overall in ("FAIL", "PARTIAL"))
    rate = passed / len(ran) if ran else None
    return passed, failed, len(tickets), rate


def build_suggestions(report: MetaReviewReport) -> list[str]:
    suggestions: list[str] = []

    passed, failed, total, rate = _ticket_pass_rate(report.tickets)
    never = sum(1 for t in report.tickets if t.overall == "NEVER")
    if total == 0:
        suggestions.append("No ticket folders found — run `bob init-ticket` then `bob validate-ticket` on a host repo.")
    else:
        if never:
            suggestions.append(f"{never} ticket(s) never validated — run `bob validate-ticket <id>` or archive stale folders.")
        if rate is not None and rate < 0.8:
            suggestions.append(
                f"Ticket pass rate {rate:.0%} ({passed}/{passed + failed} runs) — inspect FAIL/PARTIAL tickets and encode boot fixes in Bob."
            )
        if report.boot_failure_counts:
            top = report.boot_failure_counts.most_common(3)
            labels = ", ".join(f"{k} ({v})" for k, v in top)
            suggestions.append(f"Recurring boot/health failures: {labels} — review `bob start-services` logs and boot_plan defaults.")

    if report.next_open:
        suggestions.append(
            f"{len(report.next_open)} open NEXT.md items — prioritize Now ({report.next_sections.get('Now', 0)}) before Later."
        )

    if report.rule_drift:
        suggestions.append(
            f"Orchestrator rule drift: {report.rule_drift}. Merge template via `bob onboard --force` or edit ~/.cursor/rules/novopay-orchestrator.mdc manually."
        )
    if report.hooks_ok is False:
        suggestions.append("Cursor hygiene stop hook missing — run `bob onboard` to merge hooks.json.")

    for dup in report.skill_duplicates:
        suggestions.append(f"Duplicate skills path: {dup} — junction to workspace `.cursor/skills/` only.")

    missing_plugins = [
        name
        for name, sig in report.plugin_signals.items()
        if "not detected" in sig and name != "Postman"
    ]
    if missing_plugins:
        suggestions.append(
            f"Recommended Cursor plugins not detected locally: {', '.join(missing_plugins)}. Run `bob plugins` and install from marketplace."
        )

    if report.chat_keyword_hits.get("workflow-from-chats", 0) >= 2 and report.rule_drift:
        suggestions.append("Chats reference workflow-from-chats while rule drift exists — run hygiene and reconcile rule template.")

    if report.context_audit and not report.context_audit.error:
        if report.context_audit.active_high_count >= 5:
            suggestions.append(
                f"{report.context_audit.active_high_count} active chats at >= 60% context - run `bob chat-hygiene --auto` or `bob context-audit` for details."
            )
        elif report.context_audit.active_high_count:
            suggestions.extend(build_context_suggestions(report.context_audit)[:1])

    if report.mcp_audit and not report.mcp_audit.error:
        mcp_suggestions = build_mcp_audit_suggestions(report.mcp_audit)
        if report.mcp_audit.pending_disable_tools or report.mcp_audit.user_mcp_json_servers:
            suggestions.extend(mcp_suggestions[:2])
        elif mcp_suggestions and mcp_suggestions[0] != "MCP/plugin overhead matches Bob squad policy on this machine.":
            suggestions.append(mcp_suggestions[0])

    if not suggestions:
        suggestions.append("No urgent drift detected — re-run monthly or after major Bob/Cursor workflow changes.")
    return suggestions


def meta_review_state_path() -> Path:
    return Path.home() / META_REVIEW_STATE_REL


def load_meta_review_state() -> dict[str, Any]:
    path = meta_review_state_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_meta_review_state(state: dict[str, Any]) -> None:
    path = meta_review_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def meta_review_hook_due(
    state: dict[str, Any],
    *,
    interval_days: int = META_REVIEW_INTERVAL_DAYS,
) -> bool:
    last = float(state.get("last_run_epoch", 0) or 0)
    return time.time() - last >= interval_days * 86400


def write_meta_review_outputs(report: MetaReviewReport) -> list[Path]:
    bob_root = runner_bootstrap_repo()
    written: list[Path] = []
    out = bob_root / META_DOC
    out.write_text(render_meta_review_md(report), encoding="utf-8")
    written.append(out)
    if report.context_audit and not report.context_audit.error:
        ctx_out = bob_root / CONTEXT_AUDIT_DOC
        ctx_out.write_text(render_context_audit_md(report.context_audit), encoding="utf-8")
        written.append(ctx_out)
    if report.mcp_audit and not report.mcp_audit.error:
        mcp_out = bob_root / MCP_AUDIT_DOC
        mcp_out.write_text(render_mcp_audit_md(report.mcp_audit), encoding="utf-8")
        written.append(mcp_out)
    return written


def touch_meta_review_state() -> None:
    state = load_meta_review_state()
    state["last_run_epoch"] = time.time()
    state["last_run_iso"] = datetime.now(timezone.utc).isoformat()
    save_meta_review_state(state)


def build_meta_review_hook_followup(report: MetaReviewReport) -> str:
    bob_root = runner_bootstrap_repo()
    parts = [
        "Monthly meta-review ran automatically (Bob ticket health, boot failures, plugins, context usage).",
        f"Human gate: review {bob_root}/docs/META_REVIEW.md",
    ]
    if report.context_audit and not report.context_audit.error:
        parts.append("and docs/CONTEXT_USAGE_AUDIT.md.")
    parts.append(
        "Approve any rule/skill/Bob changes manually; use `bob onboard --force` for orchestrator rule sync only."
    )
    if report.context_audit and report.context_audit.active_high_count:
        parts.append(
            f"Note: {report.context_audit.active_high_count} active chat(s) at >= 60% context - "
            "`bob chat-hygiene --auto` if archive is needed."
        )
    parts.append("Reply briefly: reviewed or no changes needed.")
    return " ".join(parts)


def run_meta_review_hook(
    *,
    interval_days: int = META_REVIEW_INTERVAL_DAYS,
    dry_run: bool = False,
) -> int:
    if parse_hook_stop_json(os.environ.get("HOOK_STOP_JSON", "")) is None:
        print("{}")
        return 0

    state = load_meta_review_state()
    if not meta_review_hook_due(state, interval_days=interval_days):
        print("{}")
        return 0

    report = build_meta_review()
    if not dry_run:
        write_meta_review_outputs(report)
        touch_meta_review_state()

    print(json.dumps({"followup_message": build_meta_review_hook_followup(report)}))
    return 0


def build_meta_review(*, days: int = 30) -> MetaReviewReport:
    workspace = _resolve_workspace()
    report = MetaReviewReport(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        workspace=str(workspace) if workspace else None,
        days_window=days,
    )

    if workspace:
        report.tickets = collect_ticket_stats(workspace)
        for t in report.tickets:
            for label in t.boot_failures:
                report.boot_failure_counts[label] += 1
        report.skill_duplicates = find_skill_duplicates(workspace)

    report.rule_drift = assess_rule_drift(workspace)
    report.hooks_ok = assess_hooks()
    report.next_open, report.next_sections = parse_next_backlog(runner_bootstrap_repo() / "docs" / "NEXT.md")
    report.plugin_signals = detect_plugin_cache_signals()
    report.chat_parent_count, report.chat_keyword_hits = scan_chat_patterns(days=days, workspace=workspace)
    report.context_audit = build_context_audit()
    report.mcp_audit = build_mcp_audit()
    report.suggestions = build_suggestions(report)
    return report


def render_meta_review_md(report: MetaReviewReport) -> str:
    lines = [
        "# Meta review (suggestions only)",
        "",
        f"**Generated:** {report.generated_at}",
        "",
        "Human approves any changes to rules, skills, or Bob. This file is audit output, not policy.",
        "",
        f"**Workspace:** {report.workspace or '(not set — run bob setup)'}",
        "",
        "---",
        "",
        "## Bob ticket health",
        "",
    ]

    passed, failed, total, rate = _ticket_pass_rate(report.tickets)
    never = sum(1 for t in report.tickets if t.overall == "NEVER")
    if total == 0:
        lines.append("- No tickets under `docs/tdd-runs/` in workspace repos.")
    else:
        rate_txt = f"{rate:.0%}" if rate is not None else "n/a"
        lines.append(f"- **Tickets tracked:** {total} (PASS {passed}, FAIL/PARTIAL {failed}, never run {never})")
        lines.append(f"- **Pass rate (excl. never run):** {rate_txt}")
        lines.append("")
        lines.append("| Ticket | Host | Status | Last run |")
        lines.append("|--------|------|--------|----------|")
        for t in report.tickets[:25]:
            lines.append(f"| {t.ticket_id} | {t.host_repo} | {t.overall} | {t.finished_at or '-'} |")
        if len(report.tickets) > 25:
            lines.append(f"| ... | | | (+{len(report.tickets) - 25} more) |")

    lines.extend(["", "## Boot / health failure patterns", ""])
    if report.boot_failure_counts:
        for label, count in report.boot_failure_counts.most_common(10):
            lines.append(f"- {label}: {count} failure(s) across runs")
    else:
        lines.append("- No boot/health step failures in stored run-summary.json files.")

    lines.extend(["", "## NEXT.md backlog", ""])
    if report.next_open:
        lines.append(f"- **Open items:** {len(report.next_open)} (Now {report.next_sections.get('Now', 0)}, Next {report.next_sections.get('Next', 0)}, Later {report.next_sections.get('Later', 0)})")
        for section, item in report.next_open[:15]:
            lines.append(f"  - [{section}] {item}")
        if len(report.next_open) > 15:
            lines.append(f"  - ... +{len(report.next_open) - 15} more")
    else:
        lines.append("- No open `- [ ]` items parsed (or NEXT.md missing).")

    lines.extend(["", "## Cursor config drift", ""])
    if report.rule_drift:
        lines.append(f"- **novopay-orchestrator.mdc:** DRIFT - {report.rule_drift}")
    else:
        lines.append("- **novopay-orchestrator.mdc:** matches onboarding template (normalized paths).")
    if report.hooks_ok is True:
        lines.append("- **hooks.json:** hygiene stop hook present.")
    elif report.hooks_ok is False:
        lines.append("- **hooks.json:** hygiene stop hook missing.")
    else:
        lines.append("- **hooks.json:** not found.")
    if report.skill_duplicates:
        for dup in report.skill_duplicates:
            lines.append(f"- **skills:** duplicate — {dup}")
    else:
        lines.append("- **skills:** no duplicate `.cursor/skills` copies detected.")

    lines.extend(["", "## Cursor plugins (local signals only)", ""])
    lines.append("Marketplace install state cannot be verified headlessly; cache dir is a weak signal.")
    for name, sig in report.plugin_signals.items():
        lines.append(f"- **{name}:** {sig}")
    lines.append("- Full list: `bob plugins`")

    lines.extend(["", "## Chat patterns (local, privacy-safe)", ""])
    lines.append(
        f"- **Parent transcripts in last {report.days_window}d:** {report.chat_parent_count}"
    )
    if report.chat_keyword_hits:
        lines.append("- **Keyword hit counts (user messages, no content stored):**")
        for kw, count in report.chat_keyword_hits.most_common():
            lines.append(f"  - `{kw}`: {count} chat(s)")
    else:
        lines.append("- No keyword hits in recent parent transcripts for this workspace.")

    if report.context_audit:
        lines.extend(render_context_audit_summary_md(report.context_audit))

    if report.mcp_audit:
        lines.extend(render_mcp_audit_summary_md(report.mcp_audit))

    lines.extend(["", "## Suggestions (approve before applying)", ""])
    for i, sug in enumerate(report.suggestions, 1):
        lines.append(f"{i}. {sug}")

    lines.extend(
        [
            "",
            "---",
            "",
            "**Cadence:** Monthly - human reviews this file, approves rule/skill/Bob changes manually "
            "(or `bob onboard --force` for orchestrator rule sync only).",
            "",
            "Re-run: `bob meta-review` · write: default · preview: `bob meta-review --dry-run`",
            "",
            f"Context detail: `bob context-audit` -> {CONTEXT_AUDIT_DOC}",
            f"MCP detail: `bob mcp-audit` -> {MCP_AUDIT_DOC}",
            "",
        ]
    )
    return "\n".join(lines)


def run_meta_review(args: list[str]) -> int:
    dry_run = "--dry-run" in args or "-n" in args
    days = 30
    interval_days = META_REVIEW_INTERVAL_DAYS
    hook_stop = False
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--days" and i + 1 < len(args):
            try:
                days = max(1, int(args[i + 1]))
            except ValueError:
                pass
            i += 2
            continue
        if arg == "--interval-days" and i + 1 < len(args):
            try:
                interval_days = max(1, int(args[i + 1]))
            except ValueError:
                pass
            i += 2
            continue
        if arg == "--hook" and i + 1 < len(args) and args[i + 1] == "stop":
            hook_stop = True
            i += 2
            continue
        i += 1

    if hook_stop:
        return run_meta_review_hook(interval_days=interval_days, dry_run=dry_run)

    report = build_meta_review(days=days)
    text = render_meta_review_md(report)
    print(text)

    if dry_run:
        print("(dry-run - META_REVIEW.md not written)")
        return 0

    for path in write_meta_review_outputs(report):
        print(f"Wrote {path}")
    touch_meta_review_state()
    return 0
