from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from _yaml_util import dump, load, repo_root


def _git_branch() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root(),
            capture_output=True,
            text=True,
            timeout=15,
        )
        return (r.stdout or "").strip() or "unknown"
    except Exception:
        return "unknown"


def _fmt_path(p: Path) -> str:
    """Windows-friendly absolute path for terminal display."""
    try:
        return str(p.resolve())
    except Exception:
        return str(p)


def _overall_status(scenarios: list[dict]) -> str:
    if not scenarios:
        return "UNKNOWN"
    passes = [s for s in scenarios if s.get("status") == "pass"]
    if len(passes) == len(scenarios):
        return "PASS"
    if passes:
        return "PARTIAL"
    return "FAIL"


class RunRecorder:
    """Collect step timing, decisions, and assertion detail during a run."""

    def __init__(self, ticket_dir: Path, spec: dict) -> None:
        self.ticket_dir = ticket_dir
        self.spec = spec
        self.ticket = spec.get("ticket") or {}
        self.started = time.time()
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self.steps: list[dict[str, Any]] = []
        self.scenarios: list[dict[str, Any]] = []
        self.assertions: list[dict[str, Any]] = []
        self.decisions: dict[str, Any] = {}
        self._step_t0: float | None = None

    def set_decisions(self, **kwargs: Any) -> None:
        self.decisions.update(kwargs)

    def begin_step(self, step_id: str, label: str = "") -> None:
        self._step_t0 = time.time()
        self._pending = (step_id, label)

    def end_step(self, status: str, detail: str = "") -> None:
        step_id, label = getattr(self, "_pending", ("?", ""))
        dur_ms = int((time.time() - (self._step_t0 or time.time())) * 1000)
        self.steps.append(
            {
                "id": step_id,
                "label": label or step_id,
                "status": status,
                "detail": detail,
                "duration_ms": dur_ms,
            }
        )
        self._step_t0 = None

    def add_scenario(
        self,
        sid: str,
        level: str,
        status: str,
        detail: str = "",
        duration_ms: int | None = None,
    ) -> None:
        self.scenarios.append(
            {
                "id": sid,
                "level": level,
                "status": status,
                "detail": detail,
                "duration_ms": duration_ms,
            }
        )

    def add_assertion(
        self,
        scenario_id: str,
        kind: str,
        passed: bool,
        expected: Any,
        actual: Any,
        errors: list[str] | None = None,
    ) -> None:
        self.assertions.append(
            {
                "scenario_id": scenario_id,
                "kind": kind,
                "passed": passed,
                "expected": expected,
                "actual": actual,
                "errors": errors or [],
            }
        )

    def finalize(self, exit_code: int) -> dict:
        finished_at = datetime.now().isoformat(timespec="seconds")
        duration_s = round(time.time() - self.started, 2)
        overall = _overall_status(self.scenarios)
        if exit_code != 0 and overall == "PASS":
            overall = "FAIL"
        return {
            "ticket_id": self.ticket.get("id", self.ticket_dir.name),
            "title": self.ticket.get("title", ""),
            "started_at": self.started_at,
            "finished_at": finished_at,
            "duration_seconds": duration_s,
            "overall": overall,
            "exit_code": exit_code,
            "branch": self.decisions.get("branch") or _git_branch(),
            "decisions": self.decisions,
            "steps": self.steps,
            "scenarios": self.scenarios,
            "assertions": self.assertions,
            "evidence": evidence_index(self.ticket_dir),
        }


def evidence_index(ticket_dir: Path) -> dict[str, str]:
    ev = ticket_dir / "evidence"
    paths: dict[str, str] = {}
    if (ticket_dir / "REPORT.md").exists():
        paths["report_md"] = _fmt_path(ticket_dir / "REPORT.md")
    if ev.exists():
        paths["evidence_dir"] = _fmt_path(ev)
        for sub in ("api", "db", "logs", "unit"):
            d = ev / sub
            if d.exists() and any(d.iterdir()):
                paths[f"evidence_{sub}"] = _fmt_path(d)
    for name in ("log-search.txt", "execution-summary.txt", "db-verify.txt", "branch.txt"):
        p = ticket_dir / name
        if p.exists():
            paths[name.replace(".", "_")] = _fmt_path(p)
    return paths


def publish_run_summary(ticket_dir: Path, run_data: dict) -> tuple[Path, Path, Path | None]:
    """Write RUN_SUMMARY.md, run-summary.json, and REPORT.html."""
    ticket_dir.mkdir(parents=True, exist_ok=True)
    json_path = ticket_dir / "run-summary.json"
    json_path.write_text(json.dumps(run_data, indent=2), encoding="utf-8")

    md_path = ticket_dir / "RUN_SUMMARY.md"
    md_path.write_text(_render_markdown(run_data), encoding="utf-8")

    html_path = ticket_dir / "REPORT.html"
    html_path.write_text(_render_html(run_data), encoding="utf-8")
    return md_path, json_path, html_path


def _render_markdown(d: dict) -> str:
    tid = d.get("ticket_id", "")
    lines = [
        f"# Run summary: {tid}",
        "",
        f"- **Title:** {d.get('title', '')}",
        f"- **Started:** {d.get('started_at', '')}",
        f"- **Finished:** {d.get('finished_at', '')}",
        f"- **Duration:** {d.get('duration_seconds', 0)}s",
        f"- **Overall:** **{d.get('overall', 'UNKNOWN')}** (exit {d.get('exit_code', '?')})",
        f"- **Branch:** `{d.get('branch', '')}`",
        "",
        "## Decision trace",
        "",
        "_How the runner chose APIs, stubs, and environment._",
        "",
    ]
    dec = d.get("decisions") or {}
    for key in sorted(dec.keys()):
        val = dec[key]
        if isinstance(val, list):
            lines.append(f"- **{key}:** {', '.join(str(x) for x in val) or '(none)'}")
        else:
            lines.append(f"- **{key}:** {val}")
    if not dec:
        lines.append("- _(no decision metadata recorded)_")

    lines += ["", "## Pipeline steps", "", "| Step | Status | Duration | Detail |", "|------|--------|----------|--------|"]
    for s in d.get("steps") or []:
        st = s.get("status", "?").upper()
        ms = s.get("duration_ms", 0)
        detail = (s.get("detail") or "").replace("|", "\\|")[:120]
        lines.append(f"| {s.get('label', s.get('id', '?'))} | {st} | {ms}ms | {detail} |")
    if not d.get("steps"):
        lines.append("| — | — | — | _No step timing recorded_ |")

    lines += ["", "## Scenarios", ""]
    for sc in d.get("scenarios") or []:
        ms = f" ({sc.get('duration_ms')}ms)" if sc.get("duration_ms") else ""
        lines.append(
            f"- **{sc.get('id', '?')}** [{sc.get('level', '')}]: "
            f"**{str(sc.get('status', '?')).upper()}**{ms} — {sc.get('detail', '')}"
        )

    lines += ["", "## Assertions (expected vs actual)", ""]
    for a in d.get("assertions") or []:
        mark = "PASS" if a.get("passed") else "FAIL"
        lines.append(f"- **{a.get('scenario_id')}** / {a.get('kind')} — **{mark}**")
        lines.append(f"  - expected: `{a.get('expected')}`")
        lines.append(f"  - actual: `{a.get('actual')}`")
        for err in a.get("errors") or []:
            lines.append(f"  - error: {err}")
    if not d.get("assertions"):
        lines.append("- _(no structured assertions; see REPORT.md and evidence/db/)_")

    lines += ["", "## Performance", ""]
    total = d.get("duration_seconds", 0)
    lines.append(f"- **Total run:** {total}s")
    slow = sorted(
        [s for s in (d.get("steps") or []) if s.get("duration_ms")],
        key=lambda x: x.get("duration_ms", 0),
        reverse=True,
    )[:5]
    if slow:
        lines.append("- **Slowest steps:**")
        for s in slow:
            lines.append(f"  - {s.get('label', s.get('id'))}: {s.get('duration_ms')}ms")

    lines += ["", "## Evidence paths", ""]
    for k, v in sorted((d.get("evidence") or {}).items()):
        lines.append(f"- **{k}:** `{v}`")
    lines += [
        "",
        "## Related artifacts",
        "",
        f"- [REPORT.md](./REPORT.md) — validation report",
        f"- [ticket-spec.yaml](./ticket-spec.yaml)",
        f"- [run-summary.json](./run-summary.json) — machine-readable (same data)",
        f"- [REPORT.html](./REPORT.html) — browser view",
        "",
    ]
    return "\n".join(lines)


def _render_html(d: dict) -> str:
    tid = d.get("ticket_id", "")
    overall = d.get("overall", "UNKNOWN")
    color = {"PASS": "#0a0", "FAIL": "#c00", "PARTIAL": "#c80", "UNKNOWN": "#666"}.get(overall, "#666")

    def esc(s: Any) -> str:
        return (
            str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    rows_steps = "".join(
        f"<tr><td>{esc(s.get('label', s.get('id')))}</td>"
        f"<td>{esc(s.get('status'))}</td>"
        f"<td>{s.get('duration_ms', 0)}ms</td>"
        f"<td>{esc(s.get('detail', ''))}</td></tr>"
        for s in d.get("steps") or []
    )
    rows_sc = "".join(
        f"<li><b>{esc(sc.get('id'))}</b> [{esc(sc.get('level'))}] "
        f"<span style='color:{color}'>{esc(sc.get('status'))}</span> — {esc(sc.get('detail', ''))}</li>"
        for sc in d.get("scenarios") or []
    )
    dec_items = "".join(
        f"<li><b>{esc(k)}:</b> {esc(v)}</li>" for k, v in sorted((d.get("decisions") or {}).items())
    )
    assert_items = "".join(
        f"<li><b>{esc(a.get('scenario_id'))}</b> / {esc(a.get('kind'))} — "
        f"{'PASS' if a.get('passed') else 'FAIL'}<br>"
        f"<small>expected: {esc(a.get('expected'))} | actual: {esc(a.get('actual'))}</small></li>"
        for a in d.get("assertions") or []
    )
    ev_items = "".join(
        f"<li><b>{esc(k)}:</b> <code>{esc(v)}</code></li>"
        for k, v in sorted((d.get("evidence") or {}).items())
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>TDD Run — {esc(tid)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 960px; }}
h1 {{ margin-bottom: 0.2rem; }}
.meta {{ color: #444; }}
section {{ margin-top: 1.5rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }}
th {{ background: #f4f4f4; }}
.overall {{ font-size: 1.2rem; color: {color}; font-weight: bold; }}
code {{ font-size: 0.85rem; word-break: break-all; }}
</style>
</head>
<body>
<h1>Run: {esc(tid)}</h1>
<p class="meta">{esc(d.get('title', ''))} · {esc(d.get('started_at'))} → {esc(d.get('finished_at'))} · {d.get('duration_seconds', 0)}s · branch <code>{esc(d.get('branch'))}</code></p>
<p class="overall">Overall: {esc(overall)}</p>

<section><h2>Decision trace</h2><ul>{dec_items or '<li><em>none recorded</em></li>'}</ul></section>

<section><h2>Pipeline steps</h2>
<table><thead><tr><th>Step</th><th>Status</th><th>Duration</th><th>Detail</th></tr></thead>
<tbody>{rows_steps or '<tr><td colspan="4"><em>none</em></td></tr>'}</tbody></table></section>

<section><h2>Scenarios</h2><ul>{rows_sc or '<li><em>none</em></li>'}</ul></section>

<section><h2>Assertions</h2><ul>{assert_items or '<li><em>none</em></li>'}</ul></section>

<section><h2>Evidence</h2><ul>{ev_items}</ul>
<p><a href="RUN_SUMMARY.md">RUN_SUMMARY.md</a> · <a href="REPORT.md">REPORT.md</a></p></section>
</body>
</html>
"""


def load_last_summary(ticket_dir: Path) -> dict | None:
    p = ticket_dir / "run-summary.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def print_status(ticket_id: str) -> int:
    from ticket_spec import ticket_dir

    td = ticket_dir(ticket_id)
    if not td.exists():
        print(f"No ticket folder: {td}")
        print(f"Init: python bob.py init-ticket {ticket_id} \"Title\"")
        return 1
    data = load_last_summary(td)
    if not data:
        if (td / "REPORT.md").exists():
            print(f"Ticket {ticket_id}: REPORT.md exists but no run-summary.json yet.")
            print(f"Re-run: python bob.py validate-ticket {ticket_id}")
            print(f"Report: {_fmt_path(td / 'REPORT.md')}")
            return 0
        print(f"Ticket {ticket_id}: no runs yet.")
        print(f"Init:  python bob.py init-ticket {ticket_id} \"Title\"")
        print(f"Run:   python bob.py validate-ticket {ticket_id}")
        return 1

    print(f"=== {data.get('ticket_id')} — {data.get('overall')} ===")
    print(f"Title:    {data.get('title', '')}")
    print(f"When:     {data.get('finished_at', data.get('started_at', ''))}")
    print(f"Duration: {data.get('duration_seconds', 0)}s  branch={data.get('branch', '')}")
    print()
    print("Scenarios:")
    for sc in data.get("scenarios") or []:
        print(f"  {sc.get('id', '?'):8} {str(sc.get('status', '?')).upper():6}  {sc.get('detail', '')[:60]}")
    print()
    print("Steps:")
    for s in data.get("steps") or []:
        print(f"  {s.get('label', s.get('id', '?')):20} {str(s.get('status', '?')).upper():6}  {s.get('duration_ms', 0)}ms")
    if data.get("assertions"):
        print()
        print("Assertions:")
        for a in data.get("assertions") or []:
            mark = "OK" if a.get("passed") else "FAIL"
            print(f"  [{mark}] {a.get('scenario_id')} {a.get('kind')}")
    print()
    print(f"Full summary: {_fmt_path(td / 'RUN_SUMMARY.md')}")
    print(f"HTML report:  {_fmt_path(td / 'REPORT.html')}")
    return 0 if data.get("overall") == "PASS" else 1


def print_open(ticket_id: str) -> int:
    from ticket_spec import ticket_dir

    td = ticket_dir(ticket_id)
    if not td.exists():
        print(f"No ticket folder: {td}")
        return 1
    summary = td / "RUN_SUMMARY.md"
    html = td / "REPORT.html"
    ev = td / "evidence"
    print(f"Ticket dir:     {_fmt_path(td)}")
    print(f"RUN_SUMMARY.md: {_fmt_path(summary)}{'' if summary.exists() else ' (not generated — run bob validate-ticket first)'}")
    print(f"REPORT.html:    {_fmt_path(html)}{'' if html.exists() else ' (not generated)'}")
    print(f"Evidence:       {_fmt_path(ev)}")
    if not summary.exists():
        print()
        print(f"Run: python bob.py validate-ticket {ticket_id}")
    return 0


def list_tickets() -> int:
    root = repo_root() / "docs/tdd-runs"
    if not root.exists():
        print("No docs/tdd-runs/")
        return 0
    rows: list[tuple[str, str, str, str]] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        data = load_last_summary(d)
        if data:
            rows.append(
                (
                    data.get("ticket_id", d.name),
                    str(data.get("overall", "?")),
                    str(data.get("finished_at", ""))[:19],
                    str(data.get("title", ""))[:40],
                )
            )
        elif (d / "ticket-spec.yaml").exists():
            rows.append((d.name, "—", "never", ""))
    if not rows:
        print("No tickets under docs/tdd-runs/")
        print("Create: python bob.py init-ticket MY-TICKET \"Title\"")
        return 0
    print(f"{'TICKET':<24} {'STATUS':<8} {'LAST RUN':<20} TITLE")
    print("-" * 72)
    for tid, status, when, title in rows:
        print(f"{tid:<24} {status:<8} {when:<20} {title}")
    return 0


def build_summary_from_artifacts(ticket_dir: Path) -> dict | None:
    """Lightweight summary when only prior bash artifacts exist (no run-summary.json)."""
    spec_path = ticket_dir / "ticket-spec.yaml"
    if not spec_path.exists():
        spec_path = ticket_dir / "ticket-spec.yaml"
    if not spec_path.exists():
        return None
    try:
        spec = load(spec_path)
    except Exception:
        return None
    ticket = spec.get("ticket") or {}
    exec_txt = ""
    if (ticket_dir / "execution-summary.txt").exists():
        exec_txt = (ticket_dir / "execution-summary.txt").read_text(encoding="utf-8")[:2000]
    overall = "UNKNOWN"
    if "FAIL" in exec_txt.upper():
        overall = "FAIL"
    elif "PASS" in exec_txt.upper():
        overall = "PASS"
    return {
        "ticket_id": ticket.get("id", ticket_dir.name),
        "title": ticket.get("title", ""),
        "started_at": "",
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "duration_seconds": 0,
        "overall": overall,
        "exit_code": 1 if overall == "FAIL" else 0,
        "branch": _git_branch(),
        "decisions": {"note": "reconstructed from prior run artifacts"},
        "steps": [],
        "scenarios": [],
        "assertions": [],
        "evidence": evidence_index(ticket_dir),
        "prior_execution_summary": exec_txt[:500],
    }
