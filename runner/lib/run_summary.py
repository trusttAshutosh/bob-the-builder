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
        from tool_bridge import run_tool

        result = run_tool("git.branch", cwd=str(repo_root()))
        if result.ok and result.data:
            return str(result.data).strip() or "unknown"
    except ImportError:
        pass
    except Exception:
        pass
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
        *,
        name: str = "",
        apis: list[str] | None = None,
    ) -> None:
        self.scenarios.append(
            {
                "id": sid,
                "level": level,
                "status": status,
                "detail": detail,
                "duration_ms": duration_ms,
                "name": name,
                "apis": apis or [],
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
    if (ticket_dir / "TEST_PLAN.md").exists():
        paths["test_plan_md"] = _fmt_path(ticket_dir / "TEST_PLAN.md")
    if ev.exists():
        paths["evidence_dir"] = _fmt_path(ev)
        for sub in ("api", "db", "logs", "unit", "kafka", "redis"):
            d = ev / sub
            if d.exists() and any(d.iterdir()):
                paths[f"evidence_{sub}"] = _fmt_path(d)
    for name in (
        "log-search.txt",
        "execution-summary.txt",
        "db-verify.txt",
        "DB_VERIFY_QUERIES.sql",
        "LOG_VERIFY_COMMANDS.md",
        "REDIS_VERIFY.md",
        "KAFKA_VERIFY.md",
        "kafka-discovered.json",
        "masterdata-stub-urls.sql",
        "branch.txt",
    ):
        p = ticket_dir / name
        if p.exists():
            paths[name.replace(".", "_")] = _fmt_path(p)
    postman_dir = ticket_dir / "postman"
    if postman_dir.is_dir():
        paths["postman_dir"] = _fmt_path(postman_dir)
        for coll in postman_dir.glob("*.postman_collection.json"):
            paths["postman_collection"] = _fmt_path(coll)
            break
        for envf in sorted(postman_dir.glob("*.postman_environment.json")):
            paths[f"postman_env_{envf.stem}"] = _fmt_path(envf)
    return paths


def _md_cell(text: Any, max_len: int = 200) -> str:
    s = str(text or "").replace("|", "\\|").replace("\n", " ").strip()
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s or "—"


def _format_db_expect(db_expect: dict | None) -> str:
    if not db_expect:
        return "—"
    meta_keys = {"expect", "must_not_contain", "internal_txn_desc_prefix", "internal_txn_desc"}
    if not meta_keys.intersection(db_expect.keys()):
        db_expect = {"expect": db_expect}
    parts: list[str] = []
    expect = db_expect.get("expect") or {}
    if expect:
        parts.append("expect: " + ", ".join(f"{k}={v}" for k, v in expect.items()))
    if prefix := db_expect.get("internal_txn_desc_prefix"):
        parts.append(f"internal_txn_desc starts with `{prefix}`")
    if exact := db_expect.get("internal_txn_desc"):
        parts.append(f"internal_txn_desc = `{exact}`")
    mnc = db_expect.get("must_not_contain") or {}
    if mnc:
        parts.append("must not contain: " + ", ".join(f"{k} in {v}" for k, v in mnc.items()))
    return "; ".join(parts) if parts else "—"


def _format_db_actual(row: dict | None) -> str:
    if not row:
        return "—"
    keys = ("txn_status", "txn_result_code", "txn_result_description", "internal_txn_desc")
    parts = [f"{k}={row.get(k, '')}" for k in keys if row.get(k) not in (None, "", "NULL")]
    return "; ".join(parts) if parts else str(row)


def _planned_apis(sc_spec: dict) -> str:
    steps = sc_spec.get("steps") or []
    apis = [s.get("api_id") or s.get("api") for s in steps if s.get("api_id") or s.get("api")]
    if sc_spec.get("gradle_tests"):
        apis.append(f"unit: {', '.join(sc_spec['gradle_tests'])}")
    return ", ".join(apis) if apis else "—"


def _pre_setup_note(sc_spec: dict) -> str:
    if sc_spec.get("pre_sql_file"):
        return f"SQL: `{sc_spec['pre_sql_file']}`"
    if sc_spec.get("pre_sql"):
        return "SQL seed (inline)"
    if (sc_spec.get("verification_level") or "").lower() == "unit":
        return "Gradle unit tests"
    return "—"


def ensure_test_plan(ticket_dir: Path, spec: dict) -> Path:
    """Write or refresh TEST_PLAN.md from ticket-spec (planned scenarios, no run results)."""
    from assertions import resolve_db_expect
    from ticket_spec import scenarios

    ticket = spec.get("ticket") or {}
    tid = ticket.get("id", ticket_dir.name)
    title = ticket.get("title", "")
    lines = [
        f"# Test plan: {title}",
        "",
        f"**Ticket:** `{tid}`",
        f"**Feature:** {(spec.get('impacted') or {}).get('feature', '')}",
        f"**Env profile:** {spec.get('env_profile', 'local-dsa')}",
        "",
        "_Generated/updated by Bob `validate-ticket`. Run results live in [REPORT.md](./REPORT.md)._",
        "",
        "## Acceptance criteria",
        "",
    ]
    for ac in ticket.get("acceptance_criteria") or []:
        lines.append(f"- [ ] {ac}")
    if not ticket.get("acceptance_criteria"):
        lines.append("- _(none in ticket-spec)_")

    lines += [
        "",
        "## Planned scenarios",
        "",
        "| Scenario ID | Description | Level | APIs | Pre-setup | DB expected |",
        "|-------------|-------------|-------|------|-----------|-------------|",
    ]
    for sc in scenarios(spec):
        sid = sc.get("id", "?")
        name = (sc.get("name") or "").strip() or "—"
        level = sc.get("verification_level") or "e2e"
        db_exp = _format_db_expect(resolve_db_expect(sc, spec))
        lines.append(
            f"| {sid} | {_md_cell(name, 80)} | {level} | {_md_cell(_planned_apis(sc), 60)} | "
            f"{_md_cell(_pre_setup_note(sc), 40)} | {_md_cell(db_exp, 120)} |"
        )
    if not scenarios(spec):
        lines.append("| — | _(no scenarios in ticket-spec)_ | — | — | — | — |")

    lines += [
        "",
        "## Manual / Postman",
        "",
        "- Import Postman collection under [postman/](./postman/) after validate-ticket.",
        "- Run **prerequisites** before **apis-under-test** (avoids 4000028).",
        "",
    ]
    path = ticket_dir / "TEST_PLAN.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _scenario_result_rows(run_data: dict, spec: dict) -> list[dict[str, str]]:
    from assertions import resolve_db_expect
    from audit_config import scenario_description
    from ticket_spec import scenarios

    spec_by_id = {sc.get("id", "?"): sc for sc in scenarios(spec)}
    run_by_id = {sc.get("id", "?"): sc for sc in run_data.get("scenarios") or []}
    db_assert: dict[str, dict] = {}
    for a in run_data.get("assertions") or []:
        if a.get("kind") == "db":
            db_assert[a.get("scenario_id", "?")] = a

    dec = run_data.get("decisions") or {}
    scenario_crns = dec.get("scenario_crns") or {}

    ordered_ids: list[str] = []
    for sc in scenarios(spec):
        sid = sc.get("id", "?")
        if sid not in ordered_ids:
            ordered_ids.append(sid)
    for sid in run_by_id:
        if sid not in ordered_ids:
            ordered_ids.append(sid)

    rows: list[dict[str, str]] = []
    for sid in ordered_ids:
        sc_spec = spec_by_id.get(sid, {})
        sc_run = run_by_id.get(sid, {})
        name = (sc_run.get("name") or sc_spec.get("name") or "").strip()
        desc = scenario_description(sid, name) if name else sid
        level = sc_run.get("level") or sc_spec.get("verification_level") or "—"
        apis = sc_run.get("apis") or []
        if not apis:
            apis = [x for x in _planned_apis(sc_spec).split(", ") if x and x != "—"]
        apis_s = ", ".join(apis) if apis else _planned_apis(sc_spec)
        crn = scenario_crns.get(sid) or sc_spec.get("crn") or dec.get("base_crn") or "—"
        db_expect_s = _format_db_expect(resolve_db_expect(sc_spec, spec) if sc_spec else None)
        assertion = db_assert.get(sid)
        if assertion:
            exp_raw = assertion.get("expected")
            if isinstance(exp_raw, dict):
                db_expect_s = _format_db_expect(exp_raw)
            else:
                db_expect_s = str(exp_raw)
            db_actual_s = _format_db_actual(assertion.get("actual"))
            db_status = "PASS" if assertion.get("passed") else "FAIL"
        else:
            db_actual_s = "—"
            has_db = bool(resolve_db_expect(sc_spec, spec)) if sc_spec else False
            db_status = "N/A" if not has_db else "SKIP"

        overall = str(sc_run.get("status", "—")).upper() if sc_run else "NOT RUN"
        ms = sc_run.get("duration_ms")
        duration = f"{ms}ms" if ms else "—"
        exec_detail = sc_run.get("detail") or "—"

        rows.append(
            {
                "id": sid,
                "description": desc,
                "level": level,
                "apis": apis_s,
                "crn": crn,
                "db_expected": db_expect_s,
                "db_actual": db_actual_s,
                "db_status": db_status,
                "execution": exec_detail,
                "overall": overall,
                "duration": duration,
            }
        )
    return rows


def publish_run_summary(
    ticket_dir: Path,
    run_data: dict,
    *,
    spec: dict | None = None,
    execution_log: list[str] | None = None,
    relative_paths: bool = False,
) -> tuple[Path, Path, Path | None]:
    """Write REPORT.md (single human report), run-summary.json, and REPORT.html."""
    ticket_dir.mkdir(parents=True, exist_ok=True)
    if spec:
        ensure_test_plan(ticket_dir, spec)
        run_data = dict(run_data)
        test_plan = ticket_dir / "TEST_PLAN.md"
        run_data["test_plan_path"] = (
            test_plan.name if relative_paths else str(test_plan.resolve())
        )

    json_path = ticket_dir / "run-summary.json"
    json_path.write_text(json.dumps(run_data, indent=2), encoding="utf-8")

    md_path = ticket_dir / "REPORT.md"
    md_path.write_text(_render_markdown(run_data, spec=spec, execution_log=execution_log), encoding="utf-8")

    legacy = ticket_dir / "RUN_SUMMARY.md"
    if legacy.exists():
        legacy.unlink()

    html_path = ticket_dir / "REPORT.html"
    html_path.write_text(_render_html(run_data, spec=spec), encoding="utf-8")
    return md_path, json_path, html_path


def _render_markdown(
    d: dict,
    *,
    spec: dict | None = None,
    execution_log: list[str] | None = None,
) -> str:
    tid = d.get("ticket_id", "")
    lines = [
        f"# Validation report: {tid}",
        "",
        f"- **Title:** {d.get('title', '')}",
        f"- **Started:** {d.get('started_at', '')}",
        f"- **Finished:** {d.get('finished_at', '')}",
        f"- **Duration:** {d.get('duration_seconds', 0)}s",
        f"- **Overall:** **{d.get('overall', 'UNKNOWN')}** (exit {d.get('exit_code', '?')})",
        f"- **Branch:** `{d.get('branch', '')}`",
        "",
    ]
    if spec:
        lines += [
            "## Test plan",
            "",
            "Planned scenarios and acceptance criteria: [TEST_PLAN.md](./TEST_PLAN.md)",
            "",
        ]
        ticket = spec.get("ticket") or {}
        if ticket.get("acceptance_criteria"):
            lines.append("**Acceptance criteria (from ticket-spec):**")
            lines.append("")
            for ac in ticket.get("acceptance_criteria") or []:
                lines.append(f"- [ ] {ac}")
            lines.append("")

    lines += [
        "## Scenario results",
        "",
        "_One row per scenario: description, expected DB outcome, actual DB row, and overall pass/fail._",
        "",
        "| Scenario ID | Description | Level | APIs | CRN | DB expected | DB actual | DB check | Overall | Duration | Execution detail |",
        "|-------------|-------------|-------|------|-----|-------------|-----------|----------|---------|----------|------------------|",
    ]
    if spec:
        for row in _scenario_result_rows(d, spec):
            lines.append(
                f"| {row['id']} | {_md_cell(row['description'], 70)} | {row['level']} | "
                f"{_md_cell(row['apis'], 50)} | `{row['crn']}` | {_md_cell(row['db_expected'], 90)} | "
                f"{_md_cell(row['db_actual'], 90)} | {row['db_status']} | **{row['overall']}** | "
                f"{row['duration']} | {_md_cell(row['execution'], 100)} |"
            )
    else:
        for sc in d.get("scenarios") or []:
            lines.append(
                f"| {sc.get('id', '?')} | {_md_cell(sc.get('name') or sc.get('detail', ''), 70)} | "
                f"{sc.get('level', '')} | — | — | — | — | — | **{str(sc.get('status', '?')).upper()}** | "
                f"{sc.get('duration_ms', '—')}ms | {_md_cell(sc.get('detail', ''), 100)} |"
            )
    if not (d.get("scenarios") or (spec and _scenario_result_rows(d, spec))):
        lines.append("| — | _(no scenarios)_ | — | — | — | — | — | — | — | — | — |")

    lines += [
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

    sh_lines = d.get("service_health_md") or []
    if sh_lines:
        lines.extend(sh_lines)
    elif dec.get("boot_services_detail") or dec.get("service_health_detail"):
        lines += [
            "",
            "## Service health",
            "",
            f"- **Boot:** {dec.get('boot_services_detail', '—')}",
            f"- **Health check:** {dec.get('service_health_detail', '—')}",
        ]
        if dec.get("boot_services_up"):
            lines.append(f"- **Boot UP:** {', '.join(dec['boot_services_up'])}")
        if dec.get("boot_services_down"):
            lines.append(f"- **Boot DOWN:** {', '.join(dec['boot_services_down'])}")
        if dec.get("service_health_up"):
            lines.append(f"- **Health UP:** {', '.join(dec['service_health_up'])}")
        if dec.get("service_health_down"):
            lines.append(f"- **Health DOWN:** {', '.join(dec['service_health_down'])}")
        lines.append("")

    lines += ["", "## Pipeline steps", "", "| Step | Status | Duration | Detail |", "|------|--------|----------|--------|"]
    for s in d.get("steps") or []:
        st = s.get("status", "?").upper()
        ms = s.get("duration_ms", 0)
        detail = (s.get("detail") or "").replace("|", "\\|")[:120]
        lines.append(f"| {s.get('label', s.get('id', '?'))} | {st} | {ms}ms | {detail} |")
    if not d.get("steps"):
        lines.append("| — | — | — | _No step timing recorded_ |")

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

    log_lines = execution_log or []
    lines += ["", "## Execution log", ""]
    if log_lines:
        lines.append("```")
        lines.extend(log_lines[-200:])
        lines.append("```")
    else:
        lines.append("_See [execution-summary.txt](./execution-summary.txt) in this ticket folder._")

    lines += ["", "## Evidence paths", ""]
    for k, v in sorted((d.get("evidence") or {}).items()):
        if k == "report_md":
            continue
        lines.append(f"- **{k}:** `{v}`")

    scenario_crns = dec.get("scenario_crns") or {}
    db_verify = dec.get("db_verify_queries")
    log_verify = dec.get("log_verify_commands") or (d.get("evidence") or {}).get(
        "LOG_VERIFY_COMMANDS_md"
    )
    lines += [
        "",
        "## Manual verification (optional)",
        "",
        "| Kind | File |",
        "|------|------|",
        f"| DB (MySQL Workbench) | [DB_VERIFY_QUERIES.sql](./DB_VERIFY_QUERIES.sql) |",
        f"| Logs (grep/rg on server) | [LOG_VERIFY_COMMANDS.md](./LOG_VERIFY_COMMANDS.md) |",
    ]
    if dec.get("kafka_verify_commands"):
        lines.append(
            "| Kafka (local Docker / consume) | [KAFKA_VERIFY.md](./KAFKA_VERIFY.md) · [evidence/kafka/](./evidence/kafka/) |"
        )
    if dec.get("redis_verify_commands"):
        lines.append(
            "| Redis (config cache / redis-cli) | [REDIS_VERIFY.md](./REDIS_VERIFY.md) · [evidence/redis/](./evidence/redis/) |"
        )
    if dec.get("context_pack"):
        lines.append("| Context (prefs + stale + KG) | [CONTEXT_PACK.md](./CONTEXT_PACK.md) |")
    if dec.get("eval_regression_md"):
        lines.append("| Eval regression | [EVAL_REGRESSION.md](./EVAL_REGRESSION.md) |")
    if (d.get("evidence") or {}).get("evidence_logs") or dec.get("log_search_ran"):
        lines.append(
            "| Log search output (if LOGS_DIR set) | [log-search.txt](./log-search.txt) or [evidence/logs/](./evidence/logs/) |"
        )
    if (d.get("evidence") or {}).get("evidence_kafka"):
        lines.append("| Kafka captures | [evidence/kafka/](./evidence/kafka/) |")
    if (d.get("evidence") or {}).get("evidence_redis"):
        lines.append("| Redis snapshots | [evidence/redis/](./evidence/redis/) |")
    if scenario_crns:
        lines += ["", "| Scenario | CRN |", "|----------|-----|"]
        for sid, sc_crn in sorted(scenario_crns.items()):
            lines.append(f"| {sid} | `{sc_crn}` |")

    lines += [
        "",
        "## Related artifacts",
        "",
        "_Single report file: this `REPORT.md` (no separate RUN_SUMMARY.md)._",
        "",
        "- [TEST_PLAN.md](./TEST_PLAN.md) — planned scenarios (updated each validate-ticket)",
        "- [DB_VERIFY_QUERIES.sql](./DB_VERIFY_QUERIES.sql) — MySQL dashboard + per-scenario SELECTs",
        "- [LOG_VERIFY_COMMANDS.md](./LOG_VERIFY_COMMANDS.md) — copy-paste grep/rg for applogs",
        "- [KAFKA_VERIFY.md](./KAFKA_VERIFY.md) — Kafka UI, consume/produce; captures in [evidence/kafka/](./evidence/kafka/)",
        "- [REDIS_VERIFY.md](./REDIS_VERIFY.md) — redis-cli commands; snapshots in [evidence/redis/](./evidence/redis/)",
        "- [CONTEXT_PACK.md](./CONTEXT_PACK.md) — prefs, staleness, hybrid KG retrieval",
        "- [EVAL_REGRESSION.md](./EVAL_REGRESSION.md) — scenario baseline comparison",
        "- [ticket-spec.yaml](./ticket-spec.yaml)",
        "- [run-summary.json](./run-summary.json) — machine-readable",
        "- [REPORT.html](./REPORT.html) — browser view",
    ]
    postman_coll = (d.get("evidence") or {}).get("postman_collection")
    if postman_coll:
        lines.append(f"- **Postman:** [postman/](./postman/) — `{Path(str(postman_coll)).name}`")
    lines.append("")
    return "\n".join(lines)


def _render_html(d: dict, *, spec: dict | None = None) -> str:
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
    scenario_rows = _scenario_result_rows(d, spec) if spec else []
    rows_sc_table = "".join(
        f"<tr><td>{esc(r['id'])}</td><td>{esc(r['description'])}</td><td>{esc(r['level'])}</td>"
        f"<td>{esc(r['apis'])}</td><td><code>{esc(r['crn'])}</code></td>"
        f"<td><small>{esc(r['db_expected'])}</small></td><td><small>{esc(r['db_actual'])}</small></td>"
        f"<td>{esc(r['db_status'])}</td><td><b>{esc(r['overall'])}</b></td>"
        f"<td>{esc(r['duration'])}</td></tr>"
        for r in scenario_rows
    )
    rows_sc = rows_sc_table or "".join(
        f"<li><b>{esc(sc.get('id'))}</b> [{esc(sc.get('level'))}] "
        f"<span style='color:{color}'>{esc(sc.get('status'))}</span> — {esc(sc.get('detail', ''))}</li>"
        for sc in d.get("scenarios") or []
    )
    dec_items = "".join(
        f"<li><b>{esc(k)}:</b> {esc(v)}</li>" for k, v in sorted((d.get("decisions") or {}).items())
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

<section><h2>Test plan</h2><p><a href="TEST_PLAN.md">TEST_PLAN.md</a> — planned scenarios</p></section>

<section><h2>Scenario results</h2>
{"<table><thead><tr><th>ID</th><th>Description</th><th>Level</th><th>APIs</th><th>CRN</th><th>DB expected</th><th>DB actual</th><th>DB</th><th>Overall</th><th>Time</th></tr></thead><tbody>" + rows_sc + "</tbody></table>" if scenario_rows else "<ul>" + rows_sc + "</ul>"}
</section>

<section><h2>Evidence</h2><ul>{ev_items}</ul>
<p><a href="REPORT.md">REPORT.md</a> · <a href="TEST_PLAN.md">TEST_PLAN.md</a></p></section>
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
    print(f"Report:       {_fmt_path(td / 'REPORT.md')}")
    print(f"Test plan:    {_fmt_path(td / 'TEST_PLAN.md')}")
    print(f"HTML report:  {_fmt_path(td / 'REPORT.html')}")
    return 0 if data.get("overall") == "PASS" else 1


def print_open(ticket_id: str) -> int:
    from ticket_spec import ticket_dir

    td = ticket_dir(ticket_id)
    if not td.exists():
        print(f"No ticket folder: {td}")
        return 1
    report = td / "REPORT.md"
    test_plan = td / "TEST_PLAN.md"
    html = td / "REPORT.html"
    ev = td / "evidence"
    print(f"Ticket dir:   {_fmt_path(td)}")
    print(f"REPORT.md:    {_fmt_path(report)}{'' if report.exists() else ' (not generated — run bob validate-ticket first)'}")
    print(f"TEST_PLAN.md: {_fmt_path(test_plan)}{'' if test_plan.exists() else ' (created on validate-ticket)'}")
    print(f"REPORT.html:    {_fmt_path(html)}{'' if html.exists() else ' (not generated)'}")
    print(f"Evidence:       {_fmt_path(ev)}")
    if not report.exists():
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
