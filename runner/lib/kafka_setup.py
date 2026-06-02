"""Validate and auto-fix local Kafka setup from discovery (Docker, topics, bootstrap)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from host_repo import host_repo_root
from kafka_discovery import (
    KafkaDiscoveryResult,
    discover_kafka_for_ticket,
    kafka_mode,
    should_run_kafka,
    write_discovery_artifact,
)
from kafka_runtime import (
    DEFAULT_BOOTSTRAP,
    apply_kafka_boot_env,
    bootstrap_servers,
    ensure_topic,
    kafka_health,
    kafka_up,
    list_topics,
)


@dataclass
class KafkaSetupResult:
    ok: bool
    skipped: bool
    message: str
    discovery: KafkaDiscoveryResult | None = None
    fixes_applied: list[str] = field(default_factory=list)
    issues_remaining: list[str] = field(default_factory=list)
    resolved_topics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "skipped": self.skipped,
            "message": self.message,
            "fixes_applied": self.fixes_applied,
            "issues_remaining": self.issues_remaining,
            "resolved_topics": self.resolved_topics,
            "discovery": self.discovery.to_dict() if self.discovery else None,
        }


def _write_host_bob_kafka_properties(fixes: list[str]) -> None:
    host = host_repo_root()
    if not host:
        return
    target = host / "deploy" / "tdd" / "bob-kafka.properties"
    if target.is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "# Created by Bob kafka setup (optional; bootRun args override when run.kafka is active)\n"
        f"message.broker.bootstrap.servers={DEFAULT_BOOTSTRAP}\n",
        encoding="utf-8",
    )
    fixes.append(f"Wrote {target} with localhost broker")


def _check_bootstrap_mismatch(discovery: KafkaDiscoveryResult, fixes: list[str], issues: list[str]) -> None:
    for row in discovery.bootstrap_properties:
        raw = row.get("bootstrap", "")
        if not raw:
            continue
        brokers = [b.strip() for b in raw.split(",") if b.strip()]
        if len(brokers) > 1 and DEFAULT_BOOTSTRAP not in brokers:
            issues.append(
                f"Repo bootstrap lists {len(brokers)} brokers ({row.get('file')}); "
                f"Bob local stack uses single broker {DEFAULT_BOOTSTRAP}"
            )
            fixes.append(f"BOB_KAFKA_BOOTSTRAP set to {DEFAULT_BOOTSTRAP} for bootRun override")


def prepare_kafka_for_ticket(
    spec: dict,
    ticket_dir: Path,
    *,
    discovery: KafkaDiscoveryResult | None = None,
    autofix: bool = True,
) -> KafkaSetupResult:
    """
    Discover Kafka in impacted flow, start Docker if needed, create topics, set bootstrap env.
    """
    disc = discovery or discover_kafka_for_ticket(spec, ticket_dir)
    write_discovery_artifact(ticket_dir, disc)

    if not should_run_kafka(spec, disc):
        return KafkaSetupResult(
            ok=True,
            skipped=True,
            message=f"Kafka skipped (mode={kafka_mode(spec)}, bindings={len(disc.bindings)})",
            discovery=disc,
        )

    fixes: list[str] = []
    issues: list[str] = list(disc.issues)
    kcfg = (spec.get("run") or {}).get("kafka") or {}
    if autofix is False:
        kcfg = {**kcfg, "_autofix": False}
    do_fix = kcfg.get("autofix", True) is not False

    if not disc.has_kafka:
        return KafkaSetupResult(
            ok=False,
            skipped=False,
            message="Kafka mode requires bindings but none were discovered in impacted code",
            discovery=disc,
            issues_remaining=issues,
        )

    _check_bootstrap_mismatch(disc, fixes, issues)

    healthy, health_msg = kafka_health()
    if not healthy:
        if do_fix:
            up_ok, up_msg = kafka_up()
            if up_ok:
                fixes.append(f"Started Docker Kafka: {up_msg}")
                healthy = True
            else:
                issues.append(up_msg)
        else:
            issues.append(f"Kafka not healthy: {health_msg}")

    if healthy and do_fix:
        bs = apply_kafka_boot_env(spec)
        fixes.append(f"Bootstrap env → {bs}")
        if do_fix:
            _write_host_bob_kafka_properties(fixes)

        topics = disc.resolved_topics()
        for topic in topics:
            if not topic or "unknown-topic" in topic:
                continue
            ok, msg = ensure_topic(topic)
            if ok:
                fixes.append(msg)
            else:
                issues.append(msg)

        ok_list, existing, _ = list_topics()
        if ok_list:
            missing = [t for t in topics if t not in existing]
            if missing and not do_fix:
                issues.append(f"Topics missing on broker: {', '.join(missing)}")

    if healthy:
        ok_list, existing, _ = list_topics()
        for topic in disc.resolved_topics():
            if topic and ok_list and topic not in existing:
                issues.append(f"Topic not present after setup: {topic}")

    ok = healthy and not any("not available" in i.lower() for i in issues)
    msg_parts = [health_msg if healthy else "; ".join(issues[:3])]
    if fixes:
        msg_parts.append("fixes: " + "; ".join(fixes[:5]))
    return KafkaSetupResult(
        ok=ok,
        skipped=False,
        message=" | ".join(msg_parts),
        discovery=disc,
        fixes_applied=fixes,
        issues_remaining=issues,
        resolved_topics=disc.resolved_topics(),
    )


def format_setup_markdown(setup: KafkaSetupResult) -> str:
    lines = [
        "## Kafka (discovered from impacted code)",
        "",
        f"- **Status:** {'SKIP' if setup.skipped else ('OK' if setup.ok else 'ISSUES')}",
        f"- **Detail:** {setup.message}",
        "",
    ]
    d = setup.discovery
    if not d:
        return "\n".join(lines)
    lines.append(f"- **Mode:** `{d.mode_requested}`")
    lines.append(f"- **Repos scanned:** {', '.join(d.repos_scanned) or '—'}")
    lines.append(f"- **Resolved topics:** {', '.join(f'`{t}`' for t in setup.resolved_topics) or '—'}")
    if d.seed_files:
        lines.append(f"- **Seed files:** {len(d.seed_files)} file(s)")
    lines.append("")
    if d.bindings:
        lines.append("| Role | Topic (resolved) | Source | Detail |")
        lines.append("|------|------------------|--------|--------|")
        for b in d.bindings:
            resolved = b.resolved_topic(d.tenant, d.environment)
            lines.append(
                f"| {b.role} | `{resolved or '—'}` | `{b.source}` | {b.detail[:80]} |"
            )
        lines.append("")
    if setup.fixes_applied:
        lines.append("**Auto-fix applied:**")
        for f in setup.fixes_applied:
            lines.append(f"- {f}")
        lines.append("")
    if setup.issues_remaining:
        lines.append("**Issues (manual):**")
        for i in setup.issues_remaining:
            lines.append(f"- {i}")
        lines.append("")
    lines.append(f"Artifact: [kafka-discovered.json](./kafka-discovered.json)")
    lines.append("")
    return "\n".join(lines)
