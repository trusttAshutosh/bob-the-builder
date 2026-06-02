"""KAFKA_VERIFY.md — commands from discovered bindings (not bulk-upload specific)."""
from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from bob_home import bob_product_root
from kafka_discovery import KafkaDiscoveryResult, discover_kafka_for_ticket
from kafka_runtime import bootstrap_servers, compose_file, kafka_ui_url


def _compose_path_for_doc(compose: Path) -> str:
    """Repo-relative path for docs (same on Windows dev and Linux CI)."""
    resolved = compose.resolve()
    for root in (bob_product_root(),):
        try:
            return resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
    try:
        from host_repo import runner_bootstrap_repo

        return resolved.relative_to(runner_bootstrap_repo().resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def write_kafka_verify_commands(
    ticket_dir: Path,
    spec: dict,
    *,
    discovery: KafkaDiscoveryResult | None = None,
    capture_results: list[dict[str, Any]] | None = None,
    scenario_results: list[dict[str, Any]] | None = None,
    setup_fixes: list[str] | None = None,
    setup_issues: list[str] | None = None,
) -> Path | None:
    disc = discovery or discover_kafka_for_ticket(spec, ticket_dir)
    if not disc.has_kafka and not (spec.get("kafka_scenarios") or []):
        return None

    bs = bootstrap_servers(spec)
    ui = kafka_ui_url(spec)
    topics = disc.resolved_topics()
    compose = compose_file()

    lines = [
        "# Kafka verification (Bob — discovered from impacted code)",
        "",
        f"Ticket: `{spec.get('ticket_id', ticket_dir.name)}`",
        f"Bootstrap: `{bs}` | UI: {ui}",
        f"Mode: `{(spec.get('run') or {}).get('kafka', {}).get('mode', 'auto')}`",
        "",
        "## Discovered bindings",
        "",
    ]
    if disc.bindings:
        lines.append("| Role | Resolved topic | Source |")
        lines.append("|------|----------------|--------|")
        for b in disc.bindings:
            resolved = b.resolved_topic(disc.tenant, disc.environment)
            lines.append(f"| {b.role} | `{resolved or '—'}` | `{b.source}` |")
    else:
        lines.append("_No bindings in impacted flow — add `impacted.processor_beans` / git-changed paths._")
    lines += ["", "## Start / stop", "", "```bash", "bob kafka up", "bob kafka discover --ticket " + ticket_dir.name, "bob kafka setup --ticket " + ticket_dir.name, "bob kafka down", "```", ""]

    lines += [
        "## Docker",
        "",
        "```bash",
        f"docker compose -f {_compose_path_for_doc(compose)} up -d",
        "```",
        "",
        "## Consume (per discovered topic)",
        "",
    ]
    for topic in topics:
        lines += [
            f"### `{topic}`",
            "",
            "```bash",
            f"bob kafka consume {shlex.quote(topic)} --max 20 --timeout 15",
            "```",
            "",
        ]

    lines += [
        "## CC / service bootRun",
        "",
        "Bob sets `BOB_KAFKA_BOOTSTRAP` and passes:",
        "",
        "```text",
        f"--message.broker.bootstrap.servers={bs}",
        "```",
        "",
        f"Artifact: [kafka-discovered.json](./kafka-discovered.json)",
        "",
    ]

    if setup_fixes:
        lines += ["## Auto-fix (last run)", ""]
        for f in setup_fixes:
            lines.append(f"- {f}")
        lines.append("")
    if setup_issues:
        lines += ["## Setup issues", ""]
        for i in setup_issues:
            lines.append(f"- {i}")
        lines.append("")

    if capture_results:
        lines += ["## Capture results", ""]
        for row in capture_results:
            lines.append(
                f"- `{row.get('topic')}`: {row.get('count', 0)} msg — {row.get('detail', '')}"
            )
        lines.append("")

    if scenario_results:
        lines += ["## kafka_scenarios", "", "| ID | Pass | Topic | Detail |", "|----|------|-------|--------|"]
        for r in scenario_results:
            detail = "; ".join(str(x) for x in (r.get("detail") or []))[:100]
            ev_link = r.get("evidence")
            ev_cell = ""
            if ev_link:
                ev_path = Path(str(ev_link))
                if ev_path.is_absolute():
                    try:
                        rel = ev_path.relative_to(ticket_dir).as_posix()
                    except ValueError:
                        rel = ev_path.name
                else:
                    rel = ev_path.as_posix()
                ev_cell = f" [evidence](./{rel})"
            lines.append(
                f"| {r.get('id', '?')} | {'PASS' if r.get('pass') else 'FAIL'} | "
                f"`{r.get('topic', '')}` | {detail}{ev_cell} |"
            )
        lines.append("")

    ev_kafka = ticket_dir / "evidence" / "kafka"
    if ev_kafka.is_dir() and any(ev_kafka.iterdir()):
        lines += ["## Captured evidence", "", "Files under [evidence/kafka/](./evidence/kafka/):", ""]
        lines += ["| File |", "|------|"]
        for f in sorted(ev_kafka.iterdir()):
            if f.is_file() and f.name != "INDEX.txt":
                rel = f.relative_to(ticket_dir).as_posix()
                lines.append(f"| [{f.name}](./{rel}) |")
        lines.append("")
        lines.append("_Scenario runs and `capture_after_scenarios` write JSONL/JSON here._")
        lines.append("")

    path = ticket_dir / "KAFKA_VERIFY.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
