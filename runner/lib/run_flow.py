#!/usr/bin/env python3
"""Full validation run from ticket-spec."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

_LIB = Path(__file__).resolve().parent
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from _yaml_util import repo_root, tdd_root  # noqa: E402
from assertions import check_db_row, resolve_db_expect  # noqa: E402
from evidence import (  # noqa: E402
    copy_api_responses,
    publish_report,
    save_db_evidence,
    save_log_evidence,
    save_unit_evidence,
    write_run_manifest,
)
from run_summary import RunRecorder, publish_run_summary  # noqa: E402
from session_graph import query_slice, update as update_session  # noqa: E402
from stub_registry import apply_registry_stubs, write_masterdata_sql  # noqa: E402
from audit_config import audit_settings, build_audit_query, parse_audit_row  # noqa: E402
from service_boot import auto_boot_enabled  # noqa: E402
from ticket_spec import load_spec, scenarios, wiremock_port  # noqa: E402
from workspace import list_service_hints, properties_files_for_ticket, workspace_root  # noqa: E402


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


def _mysql_query(sql: str, schema: str | None = None) -> str:
    host = os.environ.get("MYSQL_HOST", "127.0.0.1")
    port = os.environ.get("MYSQL_PORT", "3306")
    user = os.environ.get("MYSQL_USER", "root")
    pw = os.environ.get("MYSQL_PASS", "root")
    db = schema or os.environ.get("MYSQL_AUDIT_SCHEMA", "dsa_credit_card_mgmt")
    mysql = "mysql"
    win = Path("/c/Program Files/MySQL/MySQL Server 8.0/bin/mysql.exe")
    if win.exists():
        mysql = str(win)
    cmd = [mysql, f"-h{host}", f"-P{port}", f"-u{user}", f"-p{pw}", db, "-e", sql]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return str(e)


def _run_unit_tests(test_filter: str | None) -> tuple[int, str]:
    if not test_filter or not str(test_filter).strip():
        return 1, "verification_level unit requires scenario.gradle_tests in ticket-spec"
    repo = repo_root()
    tests = str(test_filter).strip()
    cmd = ["./gradlew", "test", f"--tests={tests}", "-q"]
    try:
        r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=600)
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out[-4000:]
    except Exception as e:
        return 1, str(e)


def _header_profile(spec: dict) -> str:
    env = spec.get("_env") or {}
    return env.get("header_profile", "dsa-agent-app")


def _catalog_apis(spec: dict) -> list[str]:
    apis: list[str] = []
    for sc in scenarios(spec):
        for step in sc.get("steps") or []:
            aid = step.get("api_id") or step.get("api")
            if aid and aid not in apis:
                apis.append(aid)
    imp = spec.get("impacted") or {}
    for a in imp.get("gateway_apis") or []:
        if a not in apis:
            apis.append(a)
    return apis


def run(ticket_dir: Path) -> int:
    spec = load_spec(ticket_dir)
    ticket = spec.get("ticket") or {}
    tid = ticket.get("id", ticket_dir.name)
    title = ticket.get("title", "")

    rec = RunRecorder(ticket_dir, spec)
    rec.set_decisions(
        branch=_git_branch(),
        env_profile=spec.get("env_profile", "local-dsa"),
        header_profile=_header_profile(spec),
        workspace_root=str(workspace_root()) if workspace_root() else None,
        workspace_services=list_service_hints(),
        properties_to_review=properties_files_for_ticket(spec),
        stub_refs=[s.get("ref", s) if isinstance(s, dict) else s for s in (spec.get("stubs") or [])],
        feature=(spec.get("impacted") or {}).get("feature", ""),
        gateway_apis_from_spec=(spec.get("impacted") or {}).get("gateway_apis") or [],
        apis_from_catalog=_catalog_apis(spec),
        wiremock_port=wiremock_port(spec),
    )

    kw = f"{tid} {title} {(spec.get('impacted') or {}).get('feature', '')}"
    rec.begin_step("kg_query", "Knowledge graph context")
    query_slice(kw)
    from bob_home import agent_dir

    rec.end_step("pass", f"context slice → {agent_dir() / 'kg-context-last.md'}")

    summary: list[str] = []
    results: dict = {}
    port = wiremock_port(spec)
    stub_refs = spec.get("stubs") or []

    rec.begin_step("stubs", "Stub registry + WireMock runtime")
    summary.append("Stubs: stub-registry")
    runtime = apply_registry_stubs(ticket_dir, stub_refs, port)
    summary.append(f"WireMock root: {runtime}")
    rec.set_decisions(wiremock_runtime=str(runtime))
    write_masterdata_sql(ticket_dir, spec, port)
    rec.end_step("pass", f"{len(stub_refs)} stub ref(s), port {port}")

    if auto_boot_enabled(spec):
        from service_boot import ensure_services_running

        rec.begin_step("boot_services", "Boot services (profile + discovered peers)")
        boot_out = ensure_services_running(spec)
        ok_count = sum(1 for ok, _ in boot_out.values() if ok)
        for _key, (ok, msg) in boot_out.items():
            summary.append(f"  boot: {msg}")
        if not boot_out:
            rec.end_step("skip", "no peers discovered (run ensure-peers or need-service)")
        elif ok_count == len(boot_out):
            rec.end_step("pass", f"{ok_count}/{len(boot_out)} up")
        else:
            rec.end_step("fail", f"{ok_count}/{len(boot_out)} up")
    else:
        rec.begin_step("boot_services", "Boot Gradle services")
        rec.end_step("skip", "run.auto_boot_services: false")

    rec.begin_step("wiremock_start", "Start WireMock")
    wm_sh = tdd_root() / "start-wiremock-runtime.sh"
    if wm_sh.exists():
        subprocess.run(["bash", str(wm_sh)], cwd=repo_root(), check=False)
        rec.end_step("pass", "start-wiremock-runtime.sh")
    else:
        rec.end_step("skip", "no start-wiremock-runtime.sh")

    import tdd_engine

    crn = os.environ.get("CRN", f"TDD{int(time.time())}")
    os.environ["CRN"] = crn
    rec.set_decisions(crn=crn)
    api_rc = 0

    import urllib.request

    env_block = spec.get("_env") or {}
    primary_key = env_block.get("primary_service") or "credit_card_management"
    service_health: dict[str, str] = {}
    primary_up = False
    primary_base = ""
    for svc_key, svc_cfg in (env_block.get("services") or {}).items():
        base_var = svc_cfg.get("base_env_var", "")
        env_base = os.environ.get(base_var, "").strip() if base_var else ""
        if svc_cfg.get("optional") and not env_base:
            continue
        base = (env_base or svc_cfg.get("default_base", "")).rstrip("/")
        health_path = svc_cfg.get("health_path", "/actuator/health")
        if not base:
            continue
        rec.begin_step(f"health_{svc_key}", f"Health {svc_key}")
        try:
            urllib.request.urlopen(f"{base}{health_path}", timeout=5)
            service_health[svc_key] = "UP"
            rec.end_step("pass", base)
            if svc_key == primary_key:
                primary_up = True
                primary_base = base
        except Exception:
            service_health[svc_key] = "DOWN"
            rec.end_step("fail", base)
        summary.append(f"{svc_key}: {service_health.get(svc_key, '?')} at {base}")
    if not env_block.get("services"):
        svc_cfg = {}
        base_var = "CC_BASE"
        primary_base = os.environ.get(base_var, "http://localhost:8016/cc-mgmt")
        rec.begin_step("primary_health", f"Health {primary_key}")
        try:
            urllib.request.urlopen(f"{primary_base.rstrip('/')}/actuator/health", timeout=5)
            primary_up = True
            service_health[primary_key] = "UP"
            rec.end_step("pass", primary_base)
        except Exception:
            primary_up = False
            service_health[primary_key] = "DOWN"
            rec.end_step("fail", primary_base)
        summary.append(f"{primary_key}: {'UP' if primary_up else 'DOWN'} at {primary_base}")
    rec.set_decisions(
        service_health=service_health,
        primary_service=primary_key,
        primary_base=primary_base,
        primary_health=service_health.get(primary_key, "UP" if primary_up else "DOWN"),
    )

    for sc in scenarios(spec):
        sid = sc.get("id", "?")
        level = (sc.get("verification_level") or "e2e").lower()
        sc_t0 = time.time()
        summary.append(f"Scenario {sid}: level={level}")
        sc_ok = True
        sc_detail: list[str] = []

        if level == "unit":
            rec.begin_step(f"unit_{sid}", f"Unit tests ({sid})")
            filt = sc.get("gradle_tests")
            if not filt:
                rec.end_step("fail", "missing gradle_tests in scenario")
                sc_ok = False
                sc_detail.append("unit: no gradle_tests")
                sc_ms = int((time.time() - sc_t0) * 1000)
                rec.add_scenario(sid, level, "fail", "; ".join(sc_detail), sc_ms)
                results[sid] = {"pass": False, "level": level}
                continue
            rc, out = _run_unit_tests(filt)
            save_unit_evidence(ticket_dir, out)
            summary.append(f"  unit tests rc={rc}")
            sc_ok = rc == 0
            rec.end_step("pass" if sc_ok else "fail", f"gradle rc={rc}")
            sc_detail.append(f"unit rc={rc}")
        elif level in ("integration", "e2e") and primary_up:
            steps = sc.get("steps") or []
            api_ids = [s.get("api_id") or s.get("api") for s in steps if s.get("api_id") or s.get("api")]
            rec.begin_step(f"api_{sid}", f"API calls ({sid})")
            if steps:
                rc = tdd_engine.execute_scenarios(ticket_dir)
                summary.append(f"  api rc={rc}")
                sc_ok = rc == 0 and sc_ok
                rec.end_step("pass" if rc == 0 else "fail", ", ".join(api_ids) or "no api_id")
                sc_detail.append(f"apis={api_ids} rc={rc}")
            else:
                summary.append("  skip api: no steps")
                rec.end_step("skip", "no steps in scenario")
                sc_detail.append("api skipped")
        elif not primary_up:
            summary.append(f"  skip api: {primary_key} down")
            sc_detail.append(f"api skipped ({primary_key} down)")

        db_expect = resolve_db_expect(sc, spec)
        if db_expect:
            rec.begin_step(f"db_{sid}", f"DB check ({sid})")
            audit = audit_settings(spec)
            sql = build_audit_query(crn, spec)
            out = _mysql_query(sql, schema=audit["schema"])
            save_db_evidence(ticket_dir, sid, out)
            row = parse_audit_row(out, spec)
            ok, errs = check_db_row(db_expect, row)
            summary.append(f"  db {'PASS' if ok else 'FAIL'}: {errs}")
            sc_ok = ok and sc_ok
            rec.add_assertion(
                sid,
                "db",
                ok,
                db_expect.get("expect") or db_expect,
                row,
                errs,
            )
            rec.end_step("pass" if ok else "fail", "; ".join(errs) if errs else "row matched")
            sc_detail.append(f"db {'PASS' if ok else 'FAIL'}")
        else:
            sc_detail.append("no db expect")

        sc_ms = int((time.time() - sc_t0) * 1000)
        status = "pass" if sc_ok else "fail"
        rec.add_scenario(sid, level, status, "; ".join(sc_detail), sc_ms)
        results[sid] = {"pass": sc_ok, "level": level}

    rec.begin_step("evidence", "Collect API/log evidence")
    copy_api_responses(ticket_dir)
    log_file = ticket_dir / "log-search.txt"
    if log_file.exists():
        save_log_evidence(ticket_dir, log_file.read_text(encoding="utf-8"))
        rec.end_step("pass", "log-search.txt copied")
    else:
        rec.end_step("skip", "no log-search.txt (run search-logs.sh)")

    publish_report(ticket_dir, spec, summary)
    write_run_manifest(ticket_dir, spec, results)

    overall = all(r.get("pass") for r in results.values()) if results else False
    exit_code = 0 if overall else 1
    summary.append(f"CRN={crn}")

    run_data = rec.finalize(exit_code)
    md_path, _, html_path = publish_run_summary(ticket_dir, run_data)
    update_session(tid, title, results, run_data=run_data)

    print("\n".join(summary))
    print(f"\nRUN_SUMMARY: {md_path}")
    if html_path:
        print(f"REPORT.html:  {html_path}")
    return exit_code


def spec_path_is_ts(ticket_dir: Path) -> bool:
    return (ticket_dir / "ticket-spec.yaml").exists()


if __name__ == "__main__":
    td = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not td:
        print("Usage: run_flow.py <ticket-dir>", file=sys.stderr)
        sys.exit(1)
    sys.exit(run(td))


