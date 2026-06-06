"""bob context-audit — Cursor context window usage from local state + transcripts."""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from chat_hygiene import global_state_db
from host_repo import runner_bootstrap_repo

CONTEXT_AUDIT_DOC = "docs/CONTEXT_USAGE_AUDIT.md"
TRANSCRIPT_ROOT = Path.home() / ".cursor" / "projects"

# Baseline fixed overhead from Cursor context panel (200K window).
FIXED_OVERHEAD_TOKENS = {
    "system_prompt": 462,
    "tool_definitions": 9500,
    "rules": 3700,
    "skills": 3600,
    "mcp": 2900,
    "subagent_definitions": 386,
}
FIXED_TOTAL = sum(FIXED_OVERHEAD_TOKENS.values())
CONTEXT_LIMIT = 200_000

BUCKET_ORDER = (
    "80-100% (critical)",
    "60-79% (high)",
    "40-59% (medium)",
    "20-39% (low)",
    "0-19% (minimal)",
)


@dataclass
class ChatContextRecord:
    chat_id: str
    name: str
    pct: float
    archived: bool
    transcript_lines: int = 0


@dataclass
class ContextAuditReport:
    generated_at: str
    db_available: bool
    total_chats: int = 0
    active_chats: int = 0
    archived_chats: int = 0
    with_pct: int = 0
    transcript_count: int = 0
    matched_headers: int = 0
    ghost_transcripts: int = 0
    header_only: int = 0
    avg_pct: float | None = None
    active_avg_pct: float | None = None
    archived_avg_pct: float | None = None
    min_pct: float | None = None
    max_pct: float | None = None
    buckets: Counter[str] = field(default_factory=Counter)
    active_high_count: int = 0
    archived_high_count: int = 0
    top_chats: list[ChatContextRecord] = field(default_factory=list)
    active_high_chats: list[ChatContextRecord] = field(default_factory=list)
    error: str | None = None


def ts_to_date(ms: int | None) -> str | None:
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d")
    except (OSError, ValueError, OverflowError):
        return None


def context_bucket(pct: float) -> str:
    if pct >= 80:
        return "80-100% (critical)"
    if pct >= 60:
        return "60-79% (high)"
    if pct >= 40:
        return "40-59% (medium)"
    if pct >= 20:
        return "20-39% (low)"
    return "0-19% (minimal)"


def pct_to_est_tokens(pct: float) -> int:
    return int(CONTEXT_LIMIT * pct / 100)


def load_composer_headers(db_path: Path | None = None) -> list[dict]:
    path = db_path or global_state_db()
    if not path.is_file():
        return []
    with sqlite3.connect(path) as db:
        row = db.execute(
            "SELECT value FROM ItemTable WHERE key='composer.composerHeaders'"
        ).fetchone()
    if not row:
        return []
    return json.loads(row[0]).get("allComposers", [])


def load_transcripts(root: Path | None = None) -> dict[str, dict]:
    base = root or TRANSCRIPT_ROOT
    transcripts: dict[str, dict] = {}
    if not base.is_dir():
        return transcripts
    for path in base.rglob("*.jsonl"):
        if "subagents" in path.parts:
            continue
        chat_id = path.stem
        if chat_id in transcripts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        transcripts[chat_id] = {
            "lines": len(lines),
            "chars": len(text),
            "msgs": sum(1 for line in lines if '"role"' in line),
        }
    return transcripts


def normalize_header(header: dict) -> dict:
    ws = (header.get("workspaceIdentifier") or {}).get("uri", {}).get("fsPath", "")
    return {
        "id": header.get("composerId", ""),
        "name": header.get("name") or header.get("subtitle") or "(untitled)",
        "pct": header.get("contextUsagePercent"),
        "archived": header.get("isArchived", False),
        "mode": header.get("unifiedMode"),
        "created": ts_to_date(header.get("createdAt")),
        "updated": ts_to_date(header.get("lastUpdatedAt")),
        "workspace": ws,
        "subagents": header.get("numSubComposers", 0),
        "lines_added": header.get("totalLinesAdded", 0),
    }


def build_context_audit(
    *,
    db_path: Path | None = None,
    transcript_root: Path | None = None,
) -> ContextAuditReport:
    path = db_path or global_state_db()
    report = ContextAuditReport(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        db_available=path.is_file(),
    )
    if not report.db_available:
        report.error = f"Cursor state DB not found: {path}"
        return report

    headers = load_composer_headers(path)
    transcripts = load_transcripts(transcript_root)

    records = [normalize_header(h) for h in headers if not h.get("isDraft")]
    active = [r for r in records if not r["archived"]]
    archived = [r for r in records if r["archived"]]
    with_pct = [r for r in records if r["pct"] is not None]

    report.total_chats = len(records)
    report.active_chats = len(active)
    report.archived_chats = len(archived)
    report.with_pct = len(with_pct)
    report.transcript_count = len(transcripts)

    header_ids = {r["id"] for r in records}
    report.matched_headers = len(header_ids & set(transcripts.keys()))
    report.ghost_transcripts = len(set(transcripts.keys()) - header_ids)
    report.header_only = len(header_ids - set(transcripts.keys()))

    if with_pct:
        pcts = [r["pct"] for r in with_pct]
        report.avg_pct = sum(pcts) / len(pcts)
        report.min_pct = min(pcts)
        report.max_pct = max(pcts)
        active_with = [r for r in with_pct if not r["archived"]]
        arch_with = [r for r in with_pct if r["archived"]]
        if active_with:
            report.active_avg_pct = sum(r["pct"] for r in active_with) / len(active_with)
        if arch_with:
            report.archived_avg_pct = sum(r["pct"] for r in arch_with) / len(arch_with)
        report.buckets = Counter(context_bucket(r["pct"]) for r in with_pct)

    act_high = [r for r in with_pct if not r["archived"] and r["pct"] >= 60]
    arch_high = [r for r in with_pct if r["archived"] and r["pct"] >= 60]
    report.active_high_count = len(act_high)
    report.archived_high_count = len(arch_high)

    def to_record(r: dict) -> ChatContextRecord:
        t = transcripts.get(r["id"], {})
        return ChatContextRecord(
            chat_id=r["id"],
            name=r["name"],
            pct=r["pct"],
            archived=r["archived"],
            transcript_lines=t.get("lines", 0),
        )

    report.top_chats = [
        to_record(r)
        for r in sorted(with_pct, key=lambda x: x["pct"], reverse=True)[:20]
    ]
    report.active_high_chats = [
        to_record(r) for r in sorted(act_high, key=lambda x: -x["pct"])
    ]
    return report


def build_context_suggestions(report: ContextAuditReport) -> list[str]:
    if report.error:
        return [f"Context audit skipped: {report.error}"]
    suggestions: list[str] = []
    high_total = report.buckets.get("80-100% (critical)", 0) + report.buckets.get(
        "60-79% (high)", 0
    )
    if report.active_high_count:
        suggestions.append(
            f"{report.active_high_count} active chat(s) at >= 60% context - run `bob chat-hygiene --auto` or archive manually."
        )
    if high_total >= 10:
        suggestions.append(
            f"{high_total} chats overall at >= 60% context - split Plan/Build/Prove into separate threads per ticket."
        )
    if report.ghost_transcripts >= 50:
        suggestions.append(
            f"{report.ghost_transcripts} transcript files have no composer header (deleted UI chats) - disk only, no live context cost."
        )
    if report.avg_pct is not None and report.avg_pct >= 40:
        suggestions.append(
            f"Average context usage {report.avg_pct:.0f}% (~{pct_to_est_tokens(report.avg_pct) // 1000}K tokens) - conversation dominates; fixed overhead is ~{FIXED_TOTAL // 1000}K."
        )
    if not suggestions:
        suggestions.append("Context usage within normal range - re-run `bob context-audit` after heavy multi-day threads.")
    return suggestions


def render_context_audit_md(report: ContextAuditReport) -> str:
    lines = [
        "# Cursor context usage audit",
        "",
        f"**Generated:** {report.generated_at}",
        "",
        "## Data sources",
        "",
        "- `composer.composerHeaders` in Cursor global `state.vscdb` - stores `contextUsagePercent` per chat (last known value)",
        "- `.cursor/projects/*/agent-transcripts/*.jsonl` - parent chat transcripts (survives archive; may survive delete)",
        "- **Not persisted locally:** per-category token breakdown (System prompt, Tool definitions, Rules, etc.) from the Context panel - computed at runtime for the active chat only",
        "",
    ]

    if report.error:
        lines.extend(["## Error", "", f"- {report.error}", ""])
        return "\n".join(lines)

    lines.extend(
        [
            "## Inventory",
            "",
            "| Metric | Count |",
            "|--------|------:|",
            f"| Composer headers (non-draft) | {report.total_chats} |",
            f"| Active chats | {report.active_chats} |",
            f"| Archived chats | {report.archived_chats} |",
            f"| With `contextUsagePercent` | {report.with_pct} |",
            f"| Parent agent transcripts | {report.transcript_count} |",
            f"| Header matched to transcript | {report.matched_headers} |",
            f"| Transcript only (header missing) | {report.ghost_transcripts} |",
            f"| Header only (no transcript) | {report.header_only} |",
            "",
            "## Context percent distribution (200K window)",
            "",
        ]
    )

    if report.avg_pct is not None:
        lines.extend(
            [
                f"- Range: **{report.min_pct:.1f}%** - **{report.max_pct:.1f}%**",
                f"- Average: **{report.avg_pct:.1f}%** (~{pct_to_est_tokens(report.avg_pct) // 1000}K tokens)",
                f"- Active avg: **{report.active_avg_pct:.1f}%**" if report.active_avg_pct else "- Active avg: n/a",
                f"- Archived avg: **{report.archived_avg_pct:.1f}%**" if report.archived_avg_pct else "- Archived avg: n/a",
                "",
                "### By bucket",
                "",
            ]
        )
        for label in BUCKET_ORDER:
            lines.append(f"- {label}: **{report.buckets.get(label, 0)}** chats")

    lines.extend(
        [
            "",
            "### Fixed overhead (current session baseline)",
            "",
            "These costs apply to **every** agent chat before conversation grows:",
            "",
            "| Category | Tokens | % of 200K |",
            "|----------|-------:|----------:|",
        ]
    )
    for name, tok in FIXED_OVERHEAD_TOKENS.items():
        label = name.replace("_", " ").title()
        lines.append(f"| {label} | {tok:,} | {tok / CONTEXT_LIMIT * 100:.1f}% |")
    lines.append(
        f"| **Fixed total** | **{FIXED_TOTAL:,}** | **{FIXED_TOTAL / CONTEXT_LIMIT * 100:.1f}%** |"
    )

    lines.extend(
        [
            "",
            "## Top 20 highest-context chats",
            "",
            "| % | ~Tokens | Status | Transcript lines | Name |",
            "|--:|--------:|:-------|-----------------:|------|",
        ]
    )
    for chat in report.top_chats:
        status = "archived" if chat.archived else "active"
        est = pct_to_est_tokens(chat.pct)
        lines.append(
            f"| {chat.pct:.1f} | {est // 1000}K | {status} | {chat.transcript_lines} | {chat.name[:70]} |"
        )

    lines.extend(
        [
            "",
            f"## Active chats at >= 60% ({report.active_high_count} total) - archive candidates",
            "",
        ]
    )
    if report.active_high_chats:
        for chat in report.active_high_chats[:15]:
            lines.append(f"- **{chat.pct:.1f}%** - {chat.name[:80]}")
        if len(report.active_high_chats) > 15:
            lines.append(f"- ... and {len(report.active_high_chats) - 15} more")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Insights and recommendations",
            "",
        ]
    )
    for i, sug in enumerate(build_context_suggestions(report), 1):
        lines.append(f"{i}. {sug}")

    lines.extend(
        [
            "",
            "---",
            "",
            "Re-run: `bob context-audit` - preview: `bob context-audit --dry-run`",
            "",
        ]
    )
    return "\n".join(lines)


def render_context_audit_summary_md(report: ContextAuditReport) -> list[str]:
    lines = ["", "## Cursor context usage", ""]
    if report.error:
        lines.append(f"- Audit skipped: {report.error}")
        return lines

    avg_txt = f"{report.avg_pct:.1f}%" if report.avg_pct is not None else "n/a"
    lines.extend(
        [
            f"- **Chats tracked:** {report.total_chats} (active {report.active_chats}, archived {report.archived_chats})",
            f"- **With context %:** {report.with_pct} · average **{avg_txt}**",
            f"- **Active at >= 60%:** {report.active_high_count} (archive candidates)",
            f"- **Ghost transcripts (no header):** {report.ghost_transcripts}",
        ]
    )
    if report.buckets:
        crit = report.buckets.get("80-100% (critical)", 0)
        high = report.buckets.get("60-79% (high)", 0)
        lines.append(f"- **High/critical buckets:** {crit + high} chats at >= 60%")
    if report.active_high_chats:
        lines.append("- **Top active hot chats:**")
        for chat in report.active_high_chats[:5]:
            lines.append(f"  - {chat.pct:.1f}% - {chat.name[:70]}")
    lines.append(f"- Full report: [CONTEXT_USAGE_AUDIT.md]({CONTEXT_AUDIT_DOC})")
    return lines


def run_context_audit(args: list[str]) -> int:
    dry_run = "--dry-run" in args or "-n" in args
    report = build_context_audit()
    text = render_context_audit_md(report)
    print(text)

    if dry_run:
        print("(dry-run - CONTEXT_USAGE_AUDIT.md not written)")
        return 0

    out = runner_bootstrap_repo() / CONTEXT_AUDIT_DOC
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {out}")
    return 0
