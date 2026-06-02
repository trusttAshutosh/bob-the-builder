"""Regression eval over run-summary / scenario results (baseline vs current run)."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from _yaml_util import load


@dataclass
class ScenarioSnapshot:
    scenario_id: str
    level: str
    status: str
    pass_: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.scenario_id,
            "level": self.level,
            "status": self.status,
            "pass": self.pass_,
            "detail": self.detail[:200],
        }


@dataclass
class EvalCompareResult:
    ok: bool
    baseline_path: Path | None
    regressions: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)
    new_scenarios: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "baseline": str(self.baseline_path) if self.baseline_path else None,
            "regressions": self.regressions,
            "fixed": self.fixed,
            "new_scenarios": self.new_scenarios,
            "removed": self.removed,
            "message": self.message,
        }


def baseline_path(ticket_dir: Path) -> Path:
    return ticket_dir / "eval-baseline.json"


def _snapshots_from_run_data(run_data: dict) -> dict[str, ScenarioSnapshot]:
    out: dict[str, ScenarioSnapshot] = {}
    for sc in run_data.get("scenarios") or []:
        sid = sc.get("scenario_id") or sc.get("id") or "?"
        status = sc.get("status", "unknown")
        out[sid] = ScenarioSnapshot(
            scenario_id=sid,
            level=sc.get("level", ""),
            status=status,
            pass_=status == "pass",
            detail=sc.get("detail", ""),
        )
    return out


def capture_baseline(ticket_dir: Path, run_data: dict, *, captured_at: str | None = None) -> Path:
    path = baseline_path(ticket_dir)
    snaps = _snapshots_from_run_data(run_data)
    payload = {
        "version": 1,
        "captured_at": captured_at or time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ticket_id": run_data.get("ticket_id", ticket_dir.name),
        "branch": run_data.get("branch", ""),
        "overall": run_data.get("overall", ""),
        "scenarios": {k: v.to_dict() for k, v in snaps.items()},
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_baseline(ticket_dir: Path) -> dict | None:
    path = baseline_path(ticket_dir)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def compare_to_baseline(ticket_dir: Path, run_data: dict) -> EvalCompareResult:
    base = load_baseline(ticket_dir)
    path = baseline_path(ticket_dir)
    current = _snapshots_from_run_data(run_data)
    if not base:
        return EvalCompareResult(
            ok=True,
            baseline_path=None,
            message="No eval-baseline.json — run: bob eval baseline <ticket-id>",
        )

    base_sc: dict[str, ScenarioSnapshot] = {}
    for k, v in (base.get("scenarios") or {}).items():
        base_sc[k] = ScenarioSnapshot(
            scenario_id=k,
            level=v.get("level", ""),
            status=v.get("status", ""),
            pass_=bool(v.get("pass")),
            detail=v.get("detail", ""),
        )

    regressions: list[str] = []
    fixed: list[str] = []
    new_ids: list[str] = []
    removed: list[str] = []

    for sid, cur in current.items():
        if sid not in base_sc:
            new_ids.append(sid)
            continue
        prev = base_sc[sid]
        if prev.pass_ and not cur.pass_:
            regressions.append(f"{sid} ({prev.level}): was PASS, now {cur.status.upper()}")
        elif not prev.pass_ and cur.pass_:
            fixed.append(f"{sid}: was {prev.status.upper()}, now PASS")

    for sid in base_sc:
        if sid not in current:
            removed.append(sid)

    ok = len(regressions) == 0
    msg = f"{len(regressions)} regression(s), {len(fixed)} fixed, {len(new_ids)} new scenario(s)"
    return EvalCompareResult(
        ok=ok,
        baseline_path=path,
        regressions=regressions,
        fixed=fixed,
        new_scenarios=new_ids,
        removed=removed,
        message=msg,
    )


def eval_config(spec: dict) -> dict:
    return (spec.get("run") or {}).get("eval") or {}


def should_fail_on_regression(spec: dict) -> bool:
    ec = eval_config(spec)
    if ec.get("fail_on_regression") is False:
        return False
    return ec.get("mode", "check") in ("check", "strict")


def auto_eval_after_run(ticket_dir: Path, run_data: dict, spec: dict) -> EvalCompareResult:
    ec = eval_config(spec)
    mode = (ec.get("mode") or "check").lower()
    if mode == "off":
        return EvalCompareResult(ok=True, message="eval mode off")

    if mode == "baseline" or (mode == "update-on-pass" and run_data.get("overall") == "PASS"):
        capture_baseline(ticket_dir, run_data)
        return EvalCompareResult(
            ok=True,
            baseline_path=baseline_path(ticket_dir),
            message="Baseline captured/updated",
        )

    if mode in ("check", "strict") and not baseline_path(ticket_dir).is_file():
        if ec.get("auto_baseline_on_first_pass") and run_data.get("overall") == "PASS":
            capture_baseline(ticket_dir, run_data)
            return EvalCompareResult(ok=True, baseline_path=baseline_path(ticket_dir), message="First PASS — baseline created")
        return EvalCompareResult(ok=True, message="No baseline yet (skipped)")

    return compare_to_baseline(ticket_dir, run_data)


def write_eval_regression_md(
    ticket_dir: Path,
    result: EvalCompareResult,
    run_data: dict,
    *,
    checked_at: str | None = None,
) -> Path:
    path = ticket_dir / "EVAL_REGRESSION.md"
    checked = checked_at or time.strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# Eval regression",
        "",
        f"**Checked:** {checked}",
        f"**Result:** {'PASS' if result.ok else 'FAIL'} — {result.message}",
        "",
    ]
    if result.baseline_path:
        lines.append(f"**Baseline:** `{result.baseline_path.name}` captured {(load_baseline(ticket_dir) or {}).get('captured_at', '')}")
        lines.append("")

    lines.extend(
        [
            "## Current run",
            "",
            f"- Overall: **{run_data.get('overall', '?')}**",
            f"- Branch: `{run_data.get('branch', '')}`",
            "",
        ]
    )

    if result.regressions:
        lines.append("## Regressions (was PASS in baseline)")
        lines.append("")
        for r in result.regressions:
            lines.append(f"- {r}")
        lines.append("")

    if result.fixed:
        lines.append("## Fixed since baseline")
        lines.append("")
        for f in result.fixed:
            lines.append(f"- {f}")
        lines.append("")

    if result.new_scenarios:
        lines.append("## New scenarios (not in baseline)")
        lines.append("")
        for n in result.new_scenarios:
            lines.append(f"- {n}")
        lines.append("")

    lines.extend(
        [
            "## Commands",
            "",
            "```bash",
            f"bob eval baseline {ticket_dir.name}   # snapshot current PASS/FAIL",
            f"bob eval check {ticket_dir.name}      # compare without updating",
            f"bob eval update {ticket_dir.name}     # refresh baseline from last run-summary",
            "```",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
