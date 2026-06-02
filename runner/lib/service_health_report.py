"""Format UP/DOWN service lists for Bob RUN_SUMMARY and pipeline steps."""
from __future__ import annotations

from typing import Any


def _status_from_ok(ok: bool) -> str:
    return "UP" if ok else "DOWN"


def summarize_boot_outcomes(
    boot_out: dict[str, tuple[bool, str]],
) -> dict[str, Any]:
    """Turn ensure_services_running() output into explicit UP/DOWN lists."""
    rows: list[dict[str, str]] = []
    up: list[str] = []
    down: list[str] = []
    for key in sorted(boot_out.keys()):
        ok, msg = boot_out[key]
        status = _status_from_ok(ok)
        rows.append({"service": key, "status": status, "detail": msg})
        (up if ok else down).append(key)
    total = len(boot_out)
    return {
        "rows": rows,
        "up": up,
        "down": down,
        "up_count": len(up),
        "down_count": len(down),
        "total": total,
        "summary_line": (
            f"{len(up)}/{total} UP"
            + (f" — UP: {', '.join(up)}" if up else " — UP: (none)")
            + (f" — DOWN: {', '.join(down)}" if down else "")
        ),
        "detail_short": (
            f"UP ({len(up)}): {', '.join(up) if up else '—'}; "
            f"DOWN ({len(down)}): {', '.join(down) if down else '—'}"
        ),
    }


def summarize_health_map(
    service_health: dict[str, str],
    *,
    bases: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Group post-boot health checks (UP / DOWN / DEGRADED)."""
    bases = bases or {}
    up: list[str] = []
    down: list[str] = []
    degraded: list[str] = []
    rows: list[dict[str, str]] = []
    for key in sorted(service_health.keys()):
        status = service_health[key]
        base = bases.get(key, "")
        detail = f"{base}" if base else ""
        rows.append({"service": key, "status": status, "detail": detail})
        if status == "UP":
            up.append(key)
        elif status == "DEGRADED":
            degraded.append(key)
        else:
            down.append(key)
    return {
        "rows": rows,
        "up": up,
        "down": down,
        "degraded": degraded,
        "summary_line": (
            f"UP: {', '.join(up) if up else '—'}"
            + (f" | DEGRADED: {', '.join(degraded)}" if degraded else "")
            + (f" | DOWN: {', '.join(down) if down else ''}" if down else "")
        ),
    }


def format_markdown_section(
    boot_summary: dict[str, Any] | None,
    health_summary: dict[str, Any] | None,
    *,
    primary_service: str = "",
    primary_health: str = "",
    wiremock_status: str = "",
    wiremock_detail: str = "",
    e2e_blockers: list[str] | None = None,
) -> list[str]:
    """Lines for RUN_SUMMARY.md ## Service health."""
    lines = ["", "## Service health", ""]
    if boot_summary and boot_summary.get("total"):
        lines += [
            "### Boot (Gradle bootRun)",
            "",
            f"- **Summary:** {boot_summary['summary_line']}",
            "",
        ]
        if boot_summary.get("up"):
            lines.append("**UP**")
            for key in boot_summary["up"]:
                row = next(r for r in boot_summary["rows"] if r["service"] == key)
                lines.append(f"- `{key}` — {row['detail'][:200]}")
            lines.append("")
        if boot_summary.get("down"):
            lines.append("**DOWN**")
            for key in boot_summary["down"]:
                row = next(r for r in boot_summary["rows"] if r["service"] == key)
                lines.append(f"- `{key}` — {row['detail'][:200]}")
            lines.append("")
    if health_summary and health_summary.get("rows"):
        lines += [
            "### Health check (after boot)",
            "",
            f"- **Summary:** {health_summary['summary_line']}",
            "",
        ]
        for status_label, keys in (
            ("UP", health_summary.get("up") or []),
            ("DEGRADED", health_summary.get("degraded") or []),
            ("DOWN", health_summary.get("down") or []),
        ):
            if not keys:
                continue
            lines.append(f"**{status_label}**")
            for key in keys:
                row = next(r for r in health_summary["rows"] if r["service"] == key)
                extra = f" — {row['detail']}" if row.get("detail") else ""
                lines.append(f"- `{key}`{extra}")
            lines.append("")
    if wiremock_status:
        lines.append(f"- **WireMock:** {wiremock_status}" + (f" — {wiremock_detail}" if wiremock_detail else ""))
    if primary_service:
        lines.append(
            f"- **E2E primary (`{primary_service}`):** {primary_health or 'unknown'} "
            + ("— gateway E2E can run" if primary_health == "UP" else "— gateway E2E blocked")
        )
    if e2e_blockers:
        lines += ["", "**E2E blockers**", ""]
        for b in e2e_blockers:
            lines.append(f"- {b}")
    lines.append("")
    return lines
