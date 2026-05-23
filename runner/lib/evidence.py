from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from _yaml_util import dump, load, repo_root

BOB_NAME = "Bob the Builder"


def evidence_root(ticket_dir: Path) -> Path:
    p = ticket_dir / "evidence"
    p.mkdir(parents=True, exist_ok=True)
    for sub in ("api", "db", "logs", "unit"):
        (p / sub).mkdir(exist_ok=True)
    return p


def copy_api_responses(ticket_dir: Path) -> None:
    ev = evidence_root(ticket_dir)
    src = ticket_dir / "responses"
    if src.exists():
        for f in src.glob("*.json"):
            shutil.copy2(f, ev / "api" / f.name)


def save_db_evidence(ticket_dir: Path, scenario_id: str, text: str) -> None:
    ev = evidence_root(ticket_dir)
    (ev / "db" / f"{scenario_id}.txt").write_text(text, encoding="utf-8")


def save_log_evidence(ticket_dir: Path, text: str) -> None:
    ev = evidence_root(ticket_dir)
    src = ticket_dir / "log-search.txt"
    if src.exists():
        shutil.copy2(src, ev / "logs" / "log-search.txt")
    else:
        (ev / "logs" / "log-search.txt").write_text(text, encoding="utf-8")


def save_unit_evidence(ticket_dir: Path, summary: str) -> None:
    (evidence_root(ticket_dir) / "unit" / "gradle-test-summary.txt").write_text(summary, encoding="utf-8")


def publish_run_summary(ticket_dir: Path, spec: dict, summary_lines: list[str]) -> Path:
    """Short markdown summary for sharing (RUN_SUMMARY.md)."""
    ticket = spec.get("ticket") or {}
    tid = ticket.get("id", "")
    path = ticket_dir / "RUN_SUMMARY.md"
    lines = [
        f"# {BOB_NAME} — Run Summary",
        "",
        f"**Ticket:** `{tid}`",
        f"**Title:** {ticket.get('title', '')}",
        f"**When:** {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Summary",
        "",
        "```",
        *summary_lines,
        "```",
        "",
        f"Full report: [REPORT.md](./REPORT.md) · Evidence: [evidence/](./evidence/)",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    manifest = {
        "system": BOB_NAME,
        "ticket_id": tid,
        "title": ticket.get("title", ""),
        "at": datetime.now().isoformat(timespec="seconds"),
        "summary_lines": summary_lines,
    }
    dump(ticket_dir / "evidence" / "run-summary.json", manifest)
    return path


def publish_report(ticket_dir: Path, spec: dict, summary_lines: list[str]) -> Path:
    ticket = spec.get("ticket") or {}
    tid = ticket.get("id", "")
    report = ticket_dir / "REPORT.md"
    ev = evidence_root(ticket_dir)
    publish_run_summary(ticket_dir, spec, summary_lines)
    lines = [
        f"# {BOB_NAME} — Validation report",
        "",
        f"**Ticket:** `{tid}`",
        f"- **Title:** {ticket.get('title', '')}",
        f"- **When:** {datetime.now().isoformat(timespec='seconds')}",
        f"- **Env profile:** {spec.get('env_profile', 'local-dsa')}",
        f"- **Feature:** {(spec.get('impacted') or {}).get('feature', '')}",
        "",
        "## Acceptance criteria",
        "",
    ]
    for ac in (ticket.get("acceptance_criteria") or []):
        lines.append(f"- [ ] {ac}")
    if not ticket.get("acceptance_criteria"):
        lines.append(f"- See {ticket_dir / 'TEST_PLAN.md'}")
    lines += ["", "## Execution summary", "", "```"]
    lines.extend(summary_lines)
    lines += ["```", "", "## Evidence bundle", ""]
    for sub in ("api", "db", "logs", "unit"):
        files = list((ev / sub).glob("*"))
        lines.append(f"- **{sub}/** ({len(files)} file(s))")
    lines += ["", "## Ticket spec", "", f"[ticket-spec.yaml](./ticket-spec.yaml)", ""]
    if (ticket_dir / "TEST_PLAN.md").exists():
        lines.append(f"[TEST_PLAN.md](./TEST_PLAN.md)")
    lines += ["", "## Sign-off", "", "- [ ] All scenarios PASS", "- [ ] Evidence reviewed", ""]
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def write_run_manifest(ticket_dir: Path, spec: dict, results: dict) -> None:
    manifest = {
        "ticket_id": (spec.get("ticket") or {}).get("id"),
        "at": datetime.now().isoformat(timespec="seconds"),
        "scenarios": results,
    }
    dump(ticket_dir / "evidence" / "run-manifest.yaml", manifest)
