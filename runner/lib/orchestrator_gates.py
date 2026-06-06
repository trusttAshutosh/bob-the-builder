"""Orchestrator gate summary (Plan / Build / Prove / Ship) for Bob validate-ticket runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from _yaml_util import load


def _step_failed(steps: list[dict], keywords: tuple[str, ...]) -> bool:
    for step in steps:
        label = f"{step.get('label', '')} {step.get('id', '')}".lower()
        if any(k in label for k in keywords):
            if str(step.get("status", "")).lower() in ("fail", "error"):
                return True
    return False


def _unit_scenarios(scenarios: list[dict]) -> list[dict]:
    return [s for s in scenarios if str(s.get("level", "")).lower() == "unit"]


def _assess_plan(ticket_dir: Path, spec: dict | None) -> dict[str, Any]:
    spec_path = ticket_dir / "ticket-spec.yaml"
    test_plan = ticket_dir / "TEST_PLAN.md"
    ticket = (spec or {}).get("ticket") or {}
    ac = ticket.get("acceptance_criteria") or []
    scenario_count = len((spec or {}).get("scenarios") or [])

    missing: list[str] = []
    if not spec_path.exists():
        missing.append("ticket-spec.yaml")
    if not ac:
        missing.append("acceptance_criteria")
    if scenario_count == 0:
        missing.append("scenarios")
    if not test_plan.exists():
        missing.append("TEST_PLAN.md")

    if not missing:
        status = "PASS"
        detail = f"{scenario_count} scenario(s), {len(ac)} acceptance criteria"
    elif spec_path.exists() and scenario_count:
        status = "REVIEW"
        detail = f"partial plan; missing: {', '.join(missing)}"
    else:
        status = "FAIL"
        detail = f"missing: {', '.join(missing)}"

    evidence = []
    if spec_path.exists():
        evidence.append("[ticket-spec.yaml](./ticket-spec.yaml)")
    if test_plan.exists():
        evidence.append("[TEST_PLAN.md](./TEST_PLAN.md)")

    return {
        "id": "plan",
        "name": "Plan",
        "status": status,
        "detail": detail,
        "evidence": " | ".join(evidence) or "-",
        "orchestrator_checkbox": status in ("PASS", "REVIEW"),
    }


def _assess_build(run_data: dict) -> dict[str, Any]:
    steps = run_data.get("steps") or []
    scenarios = run_data.get("scenarios") or []
    units = _unit_scenarios(scenarios)

    compile_fail = _step_failed(steps, ("compile", "gradle", "build"))
    unit_fail = any(str(s.get("status", "")).lower() != "pass" for s in units)
    unit_pass = units and all(str(s.get("status", "")).lower() == "pass" for s in units)

    if compile_fail or unit_fail:
        status = "FAIL"
        detail = "compile or unit step failed"
    elif unit_pass:
        status = "PASS"
        detail = f"{len(units)} unit scenario(s) passed"
    elif units:
        status = "REVIEW"
        detail = "unit scenarios present but not all passed"
    else:
        e2e_only = [s for s in scenarios if str(s.get("level", "")).lower() in ("e2e", "integration")]
        if e2e_only and not compile_fail:
            status = "REVIEW"
            detail = "no unit scenarios; e2e/integration only"
        else:
            status = "REVIEW"
            detail = "no unit proof recorded in this run"

    ev = ticket_dir_evidence(run_data, "unit")
    return {
        "id": "build",
        "name": "Build",
        "status": status,
        "detail": detail,
        "evidence": ev,
        "orchestrator_checkbox": status == "PASS",
    }


def ticket_dir_evidence(run_data: dict, kind: str) -> str:
    ev = (run_data.get("evidence") or {}).get(f"evidence_{kind}")
    if ev:
        return f"[evidence/{kind}/](./evidence/{kind}/)"
    steps = run_data.get("steps") or []
    labels = [s.get("label", s.get("id", "")) for s in steps if "unit" in str(s.get("label", "")).lower()]
    if labels:
        return "unit steps: " + ", ".join(labels[:3])
    return "pipeline steps in REPORT.md"


def _assess_prove(run_data: dict) -> dict[str, Any]:
    overall = str(run_data.get("overall", "UNKNOWN")).upper()
    scenarios = run_data.get("scenarios") or []
    passed = sum(1 for s in scenarios if str(s.get("status", "")).lower() == "pass")
    total = len(scenarios)

    if overall == "PASS":
        status = "PASS"
    elif overall == "PARTIAL":
        status = "REVIEW"
    else:
        status = "FAIL"

    detail = f"overall {overall}"
    if total:
        detail += f"; {passed}/{total} scenarios passed"

    return {
        "id": "prove",
        "name": "Prove",
        "status": status,
        "detail": detail,
        "evidence": "scenario table below | [run-summary.json](./run-summary.json)",
        "orchestrator_checkbox": status == "PASS",
    }


def _assess_ship(run_data: dict, gates: list[dict]) -> dict[str, Any]:
    upstream = [g for g in gates if g["id"] != "ship"]
    all_pass = all(g["status"] == "PASS" for g in upstream)
    any_fail = any(g["status"] == "FAIL" for g in upstream)

    if any_fail:
        status = "BLOCKED"
        detail = "fix Plan/Build/Prove before ship"
    elif all_pass:
        status = "REVIEW"
        detail = "ready for orchestrator commit/PR decision"
    else:
        status = "REVIEW"
        detail = "review upstream gates first"

    return {
        "id": "ship",
        "name": "Ship",
        "status": status,
        "detail": detail,
        "evidence": "commit/PR only when you check this box",
        "orchestrator_checkbox": False,
    }


def build_orchestrator_gates(
    ticket_dir: Path,
    run_data: dict,
    *,
    spec: dict | None = None,
) -> dict[str, Any]:
    if spec is None and (ticket_dir / "ticket-spec.yaml").exists():
        try:
            spec = load(ticket_dir / "ticket-spec.yaml")
        except Exception:
            spec = None

    plan = _assess_plan(ticket_dir, spec)
    build = _assess_build(run_data)
    prove = _assess_prove(run_data)
    ship = _assess_ship(run_data, [plan, build, prove])
    gates = [plan, build, prove, ship]

    ready = plan["status"] == "PASS" and build["status"] == "PASS" and prove["status"] == "PASS"
    return {
        "gates": gates,
        "ready_for_ship_review": ready,
        "orchestrator_summary": (
            "All automated gates PASS — review Ship to commit/PR"
            if ready
            else "One or more gates need attention before Ship"
        ),
    }


def render_gate_summary_md(ticket_id: str, gate_payload: dict[str, Any]) -> str:
    lines = [
        f"# Orchestrator gates: {ticket_id}",
        "",
        "_One page for the human orchestrator. Bob fills auto status; you check the boxes._",
        "",
        f"**Summary:** {gate_payload.get('orchestrator_summary', '')}",
        "",
        "| # | Gate | Bob (auto) | Detail | Evidence | You approve |",
        "|---|------|------------|--------|----------|-------------|",
    ]
    for i, g in enumerate(gate_payload.get("gates") or [], 1):
        box = "[x]" if g.get("orchestrator_checkbox") else "[ ]"
        lines.append(
            f"| {i} | **{g['name']}** | **{g['status']}** | {g['detail']} | {g['evidence']} | {box} |"
        )
    lines += [
        "",
        "## What you decide at each gate",
        "",
        "1. **Plan** — Scope and acceptance criteria match what you want built.",
        "2. **Build** — Implementation approach and unit compile/test evidence look right.",
        "3. **Prove** — Bob PASS is enough proof for this ticket (not just unit-only).",
        "4. **Ship** — OK to commit and open PR.",
        "",
        "Full evidence: [REPORT.md](./REPORT.md)",
        "",
    ]
    return "\n".join(lines)


def render_gate_section_md(gate_payload: dict[str, Any]) -> list[str]:
    lines = [
        "## Orchestrator gates",
        "",
        f"**{gate_payload.get('orchestrator_summary', '')}** | [GATE_SUMMARY.md](./GATE_SUMMARY.md)",
        "",
        "| # | Gate | Bob (auto) | You approve |",
        "|---|------|------------|-------------|",
    ]
    for i, g in enumerate(gate_payload.get("gates") or [], 1):
        box = "[x]" if g.get("orchestrator_checkbox") else "[ ]"
        lines.append(f"| {i} | **{g['name']}** | **{g['status']}** — {g['detail']} | {box} |")
    lines.append("")
    return lines
