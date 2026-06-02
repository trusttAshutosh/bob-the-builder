"""KAFKA_VERIFY.md — commands from discovered bindings (not bulk-upload specific)."""
from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from kafka_discovery import KafkaDiscoveryResult, discover_kafka_for_ticket
from kafka_runtime import bootstrap_servers, compose_file, kafka_ui_url


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
        f"docker compose -f {compose} up -d",
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
            lines.append(
                f"| {r.get('id', '?')} | {'PASS' if r.get('pass') else 'FAIL'} | "
                f"`{r.get('topic', '')}` | {detail} |"
            )
        lines.append("")

    path = ticket_dir / "KAFKA_VERIFY.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
