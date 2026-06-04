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
from assertions import (  # noqa: E402
    check_api_response,
    check_db_row,
    load_last_api_response,
    resolve_db_expect,
)
from evidence import (  # noqa: E402
    copy_api_responses,
    publish_report,
    save_db_evidence,
    save_log_evidence,
    save_unit_evidence,
    write_run_manifest,
)
from run_summary import RunRecorder, publish_run_summary  # noqa: E402
from session_graph import update as update_session  # noqa: E402
from stub_registry import (  # noqa: E402
    apply_masterdata_sql,
    apply_registry_stubs,
    apply_scenario_wiremock,
    prime_cc_config_cache,
    write_masterdata_sql,
)
from audit_config import (  # noqa: E402
    audit_settings,
    audit_attribute_keys,
    build_audit_attributes_raw_query,
    build_audit_dashboard_query,
    build_audit_query,
    build_scenario_audit_select,
    db_verify_sql_header,
    e2e_scenario_crns,
    parse_audit_row,
    scenario_description,
    validate_union_dashboard_sql,
)
from log_verify import run_log_search_script, write_log_verify_commands  # noqa: E402
from kafka_discovery import discover_kafka_for_ticket  # noqa: E402
from kafka_runtime import (  # noqa: E402
    capture_configured_topics,
    format_kafka_scenario_summary,
    kafka_enabled,
    run_kafka_scenarios,
)
from kafka_setup import format_setup_markdown, prepare_kafka_for_ticket  # noqa: E402
from kafka_verify import write_kafka_verify_commands  # noqa: E402
from redis_verify import (  # noqa: E402
    capture_redis_evidence,
    redis_wanted,
    run_redis_scenarios,
    write_redis_verify_commands,
)
from service_boot import (  # noqa: E402
    auto_boot_enabled,
    boot_wait_seconds,
    health_reachable,
    health_up,
    masterdata_service_keys,
    start_service,
    stop_service,
)


def _bob_progress(msg: str) -> None:
    print(f"Bob: {msg}", flush=True)
from ticket_evidence import validate_evidence_contract  # noqa: E402
from postman_export import export_postman_for_ticket  # noqa: E402
from service_health_report import (  # noqa: E402
    format_markdown_section,
    summarize_boot_outcomes,
    summarize_health_map,
)
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


def _subst_crn(sql: str, crn: str) -> str:
    safe = crn.replace("'", "''")
    return sql.replace("{CRN}", safe)


from mysql_runner import mysql_exec_script, mysql_query  # noqa: E402


def _write_db_verify_queries(
    ticket_dir: Path,
    spec: dict,
    base_crn: str,
    run_scenario_crns: dict[str, str] | None = None,
) -> Path | None:
    scenario_crns = e2e_scenario_crns(spec, base_crn, run_scenario_crns)
    if not scenario_crns:
        return None
    audit = audit_settings(spec)
    dashboard_rows: list[tuple[str, str, str, dict | None]] = []
    attr_keys = audit_attribute_keys(spec)
    lines = list(db_verify_sql_header(base_crn, audit["schema"], attr_keys))
    for sc in scenarios(spec):
        sid = sc.get("id", "?")
        if sid not in scenario_crns:
            continue
        crn = scenario_crns[sid]
        name = sc.get("name", "")
        db_expect = resolve_db_expect(sc, spec)
        dashboard_rows.append((sid, name, crn, db_expect))
    dash = build_audit_dashboard_query(dashboard_rows, spec)
    if dash:
        sql_errors = validate_union_dashboard_sql(dash)
        if sql_errors:
            raise ValueError(
                "DB_VERIFY dashboard SQL invalid (fix Bob audit_config): "
                + "; ".join(sql_errors)
            )
        lines.append(dash + ";")
        lines.append("")
    raw_attrs = build_audit_attributes_raw_query(base_crn, attr_keys)
    if raw_attrs:
        lines.append(raw_attrs)
        lines.append("")
    lines.append("-- Per-scenario detail")
    lines.append("")
    for sc in scenarios(spec):
        sid = sc.get("id", "?")
        if sid not in scenario_crns:
            continue
        crn = scenario_crns[sid]
        name = sc.get("name", "")
        db_expect = resolve_db_expect(sc, spec)
        lines.append(f"-- {scenario_description(sid, name)}")
        lines.append(f"-- CRN: {crn}")
        exp = db_expect.get("expect") or {}
        if exp:
            lines.append(f"-- expect: {exp}")
        if db_expect.get("internal_txn_desc"):
            lines.append(f"-- expect internal_txn_desc: {db_expect['internal_txn_desc']}")
        if db_expect.get("internal_txn_desc_prefix"):
            lines.append(f"-- expect prefix: {db_expect['internal_txn_desc_prefix']}")
        lines.append(build_scenario_audit_select(sid, name, crn, spec, db_expect) + ";")
        lines.append("")
    out = ticket_dir / "DB_VERIFY_QUERIES.sql"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _run_pre_sql(sc: dict, crn: str, spec: dict, ticket_dir: Path) -> tuple[bool, str]:
    sql_text = sc.get("pre_sql") or ""
    pre_file = sc.get("pre_sql_file")
    if pre_file:
        path = ticket_dir / pre_file
        if path.exists():
            sql_text = path.read_text(encoding="utf-8")
        else:
            return False, f"pre_sql_file missing: {pre_file}"
    if not sql_text.strip():
        return True, "no pre_sql"
    audit = audit_settings(spec)
    sql_text = _subst_crn(sql_text, crn)
    rc, out = mysql_exec_script(sql_text, schema=audit["schema"])
    if rc != 0:
        return False, (out or "seed failed")[-400:]
    return True, f"seed ok ({audit['schema']})"


def _run_unit_tests(test_filter: str | list | None) -> tuple[int, str]:
    if not test_filter:
        return 1, "verification_level unit requires scenario.gradle_tests in ticket-spec"
    repo = repo_root()
    if isinstance(test_filter, list):
        test_args = [f"--tests={str(t).strip()}" for t in test_filter if str(t).strip()]
    else:
        test_args = [f"--tests={str(test_filter).strip()}"]
    if not test_args:
        return 1, "gradle_tests empty"
    gradle = repo / ("gradlew.bat" if sys.platform == "win32" else "gradlew")
    if not gradle.is_file():
        gradle = repo / "gradlew"
    cmd = [str(gradle), "test", *test_args, "-q"]
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


def _persist_db_verify(
    ticket_dir: Path,
    spec: dict,
    base_crn: str,
    scenario_crns: dict[str, str],
    rec: RunRecorder | None,
) -> Path | None:
    path = _write_db_verify_queries(ticket_dir, spec, base_crn, scenario_crns or None)
    if path and rec is not None:
        crns = e2e_scenario_crns(spec, base_crn, scenario_crns or None)
        rec.set_decisions(
            base_crn=base_crn,
            scenario_crns=crns,
            db_verify_queries=str(path),
        )
    return path


def run(ticket_dir: Path) -> int:
    spec = load_spec(ticket_dir)
    spec["_ticket_dir"] = str(ticket_dir)
    ticket = spec.get("ticket") or {}
    tid = ticket.get("id", ticket_dir.name)
    title = ticket.get("title", "")

    base_crn = os.environ.get("CRN", f"TDD{int(time.time())}")
    os.environ["CRN"] = base_crn
    scenario_crns: dict[str, str] = {}

    contract_ok, contract_errors = validate_evidence_contract(spec, ticket_dir)
    if not contract_ok:
        print("Bob validate-ticket: evidence contract FAILED", file=sys.stderr)
        for err in contract_errors:
            print(f"  - {err}", file=sys.stderr)
        summary = ["Evidence contract FAILED (ticket not configured for live API + DB proof):"]
        summary.extend(f"  - {e}" for e in contract_errors)
        publish_report(ticket_dir, spec, summary)
        rec = RunRecorder(ticket_dir, spec)
        rec.begin_step("evidence_contract", "Ticket evidence contract")
        rec.end_step("fail", "; ".join(contract_errors))
        db_verify_path = _persist_db_verify(ticket_dir, spec, base_crn, scenario_crns, rec)
        if db_verify_path:
            summary.append(f"DB_VERIFY_QUERIES: {db_verify_path}")
        run_data = rec.finalize(1)
        publish_run_summary(ticket_dir, run_data, spec=spec, execution_log=summary)
        print("\n".join(summary))
        return 1

    rec = RunRecorder(ticket_dir, spec)
    e2e_blockers: list[str] = []
    boot_summary: dict | None = None
    health_summary: dict | None = None
    service_bases: dict[str, str] = {}
    wiremock_status = ""
    wiremock_detail = ""
    run_cfg = spec.get("run") or {}
    require_e2e = not run_cfg.get("allow_unit_only_evidence", False)
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

    summary: list[str] = []
    kw = f"{tid} {title} {(spec.get('impacted') or {}).get('feature', '')}"
    rec.begin_step("context_assembly", "Context pack (prefs + stale + hybrid retrieval)")
    from context_assembly import assemble_context_pack

    pack_path, slice_path, stale_issues = assemble_context_pack(spec, ticket_dir, kw)
    stale_codes = [s.code for s in stale_issues if s.severity == "error"]
    rec.set_decisions(
        context_pack=str(pack_path),
        kg_context_slice=str(slice_path),
        stale_warnings=[s.code for s in stale_issues],
    )
    if stale_codes:
        summary.append(f"  context stale/errors: {', '.join(stale_codes)}")
    rec.end_step("pass" if not stale_codes else "fail", str(pack_path))

    run_graph = (spec.get("run") or {}).get("graph") or {}
    if run_graph.get("sync_obsidian", True):
        rec.begin_step("obsidian_export", "Export knowledge graph to Obsidian vault")
        try:
            from graph_obsidian import sync_obsidian_vault

            vault, ostats = sync_obsidian_vault(include_session=True)
            summary.append(
                f"  obsidian: {vault} ({ostats['apis']} apis, {ostats['tickets']} tickets)"
            )
            rec.set_decisions(obsidian_vault=str(vault), obsidian_export=ostats)
            rec.end_step("pass", str(vault))
        except Exception as ex:
            rec.end_step("fail", str(ex)[:200])
            summary.append(f"  obsidian export failed: {ex}")
    results: dict = {}
    port = wiremock_port(spec)
    stub_refs = spec.get("stubs") or []

    _bob_progress("stub registry + WireMock mappings")
    rec.begin_step("stubs", "Stub registry + WireMock runtime")
    summary.append("Stubs: stub-registry")
    runtime = apply_registry_stubs(ticket_dir, stub_refs, port)
    summary.append(f"WireMock root: {runtime}")
    rec.set_decisions(wiremock_runtime=str(runtime))
    md_sql_path = write_masterdata_sql(ticket_dir, spec, port)
    rec.set_decisions(masterdata_sql=str(md_sql_path))
    rec.end_step("pass", f"{len(stub_refs)} stub ref(s), port {port}")

    run_cfg_early = spec.get("run") or {}
    kafka_scenario_results: list[dict] = []
    kafka_capture_results: list[dict] = []
    redis_prime_msg = ""
    kafka_discovery = discover_kafka_for_ticket(spec, ticket_dir)
    rec.set_decisions(
        kafka_mode=kafka_discovery.mode_requested,
        kafka_bindings=len(kafka_discovery.bindings),
        kafka_resolved_topics=kafka_discovery.resolved_topics(),
    )
    if kafka_enabled(spec, kafka_discovery):
        _bob_progress("discovering Kafka in impacted code + preparing local stack")
        rec.begin_step("kafka_discover", "Discover Kafka producers/consumers in impacted flow")
        summary.append(
            f"  kafka discover: {len(kafka_discovery.bindings)} binding(s), "
            f"topics={', '.join(kafka_discovery.resolved_topics()) or 'none'}"
        )
        rec.end_step("pass" if kafka_discovery.has_kafka else "fail", "; ".join(kafka_discovery.issues[:2]) or "ok")

        rec.begin_step("kafka_setup", "Validate/fix local Kafka (Docker, topics, bootstrap)")
        kafka_setup = prepare_kafka_for_ticket(spec, ticket_dir, discovery=kafka_discovery)
        summary.append(f"  kafka setup: {kafka_setup.message}")
        if kafka_setup.fixes_applied:
            summary.append(f"  kafka fixes: {'; '.join(kafka_setup.fixes_applied[:4])}")
        rec.end_step("pass" if kafka_setup.ok else "fail", kafka_setup.message[:300])
        rec.set_decisions(
            kafka_setup_ok=kafka_setup.ok,
            kafka_setup_fixes=kafka_setup.fixes_applied,
            kafka_setup_issues=kafka_setup.issues_remaining,
        )
        if not kafka_setup.ok and not kafka_setup.skipped:
            e2e_blockers.append(f"Kafka setup failed: {kafka_setup.message[:200]}")
    else:
        rec.begin_step("kafka_discover", "Kafka discovery")
        rec.end_step(
            "skip",
            f"no Kafka in impacted flow (mode={kafka_discovery.mode_requested}, bindings=0)",
        )
        kafka_setup = None

    if run_cfg_early.get("apply_masterdata", True):
        _bob_progress("applying masterdata stub URLs (before CC boot)")
        rec.begin_step("masterdata_apply_preboot", "Apply WireMock URLs before service boot")
        md_pre_ok, md_pre_msg = apply_masterdata_sql(md_sql_path, spec)
        summary.append(f"  masterdata (pre-boot): {md_pre_msg}")
        rec.end_step("pass" if md_pre_ok else "fail", md_pre_msg)
        if not md_pre_ok:
            summary.append("  WARN: masterdata apply failed — CC may still call real HDFC")
        platform_sql = ticket_dir / "sql" / "seed_platform_get_agent_wiremock.sql"
        if platform_sql.is_file():
            rec.begin_step("platform_sql_preboot", "Route getAgentDetails to WireMock (platform_master)")
            plat_schema = os.environ.get("MYSQL_PLATFORM_SCHEMA", "platform_master")
            plat_rc, plat_out = mysql_exec_script(
                platform_sql.read_text(encoding="utf-8"), schema=plat_schema
            )
            plat_ok = plat_rc == 0
            summary.append(f"  platform sql ({plat_schema}): {'ok' if plat_ok else plat_out[:200]}")
            rec.end_step("pass" if plat_ok else "fail", plat_out[:300] if not plat_ok else "getAgentDetails -> 127.0.0.1:9090")

    if auto_boot_enabled(spec):
        from service_boot import ensure_services_running

        from service_boot import primary_service_key

        primary = primary_service_key(spec)
        _bob_progress(
            f"booting services ({primary} first, then peers; first start may take 2-3 min)"
        )
        rec.begin_step("boot_services", "Boot services (host primary + peers)")
        boot_out = ensure_services_running(spec)
        boot_summary = summarize_boot_outcomes(boot_out)
        ok_count = boot_summary["up_count"]
        for row in boot_summary["rows"]:
            summary.append(f"  boot {row['service']}: {row['status']} — {row['detail'][:160]}")
        rec.set_decisions(
            boot_services_up=boot_summary["up"],
            boot_services_down=boot_summary["down"],
            boot_services_detail=boot_summary["detail_short"],
        )
        if not boot_out:
            rec.end_step(
                "skip",
                "no bootable services (set BOB_HOST_REPO to a Gradle repo or fix BUILDER_WORKSPACE_ROOT)",
            )
        elif ok_count == len(boot_out):
            rec.end_step("pass", boot_summary["detail_short"])
        else:
            rec.end_step("fail", boot_summary["detail_short"])
            for key in boot_summary["down"]:
                e2e_blockers.append(f"Boot failed: `{key}` is DOWN")
    else:
        rec.begin_step("boot_services", "Boot Gradle services")
        rec.end_step("skip", "run.auto_boot_services: false")

    _bob_progress("starting WireMock")
    rec.begin_step("wiremock_start", "Start WireMock")
    from wiremock_runtime import start_wiremock

    wm_ok, wm_msg = start_wiremock(Path(runtime), port)
    wiremock_status = "UP" if wm_ok else "DOWN"
    wiremock_detail = wm_msg
    summary.append(f"  wiremock: {wiremock_status} — {wm_msg}")
    rec.end_step("pass" if wm_ok else "fail", f"{wiremock_status} — {wm_msg}")
    if not wm_ok:
        e2e_blockers.append(f"WireMock not available: {wm_msg}")

    import tdd_engine

    crn = base_crn
    rec.set_decisions(crn=crn)
    api_rc = 0

    import urllib.request

    allow_degraded = bool(run_cfg.get("allow_degraded_health", False))
    env_block = spec.get("_env") or {}
    from host_profile import primary_service_key as _primary_key

    primary_key = _primary_key(spec)
    service_health: dict[str, str] = {}
    primary_up = False
    primary_base = ""
    for svc_key, svc_cfg in (env_block.get("services") or {}).items():
        base_var = svc_cfg.get("base_env_var", "")
        env_base = os.environ.get(base_var, "").strip() if base_var else ""
        if svc_cfg.get("optional") and not env_base:
            continue
        base = (env_base or svc_cfg.get("default_base", "")).rstrip("/")
        if not base:
            continue
        rec.begin_step(f"health_{svc_key}", f"Health {svc_key}")
        if health_up(svc_cfg):
            service_health[svc_key] = "UP"
            rec.end_step("pass", base)
            if svc_key == primary_key:
                primary_up = True
                primary_base = base
        elif allow_degraded and health_reachable(svc_cfg):
            service_health[svc_key] = "DEGRADED"
            rec.end_step("pass", f"{base} (actuator not GREEN; APIs may still work)")
            if svc_key == primary_key:
                primary_up = True
                primary_base = base
        else:
            service_health[svc_key] = "DOWN"
            rec.end_step("fail", base)
        summary.append(f"  health {svc_key}: {service_health.get(svc_key, '?')} at {base}")
        service_bases[svc_key] = base
    if not env_block.get("services"):
        from host_profile import primary_base_env_var, primary_default_base

        svc_cfg = {}
        base_var = primary_base_env_var(spec)
        primary_base = os.environ.get(base_var, primary_default_base(spec))
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
        summary.append(f"  health {primary_key}: {'UP' if primary_up else 'DOWN'} at {primary_base}")
        service_bases[primary_key] = primary_base
    health_summary = summarize_health_map(service_health, bases=service_bases)
    if health_summary.get("rows"):
        rec.set_decisions(
            service_health_up=health_summary["up"],
            service_health_down=health_summary["down"],
            service_health_degraded=health_summary.get("degraded") or [],
            service_health_detail=health_summary["summary_line"],
        )
        summary.append(f"  health summary: {health_summary['summary_line']}")
    if not primary_up:
        e2e_blockers.append(
            f"Primary service `{primary_key}` is DOWN at {primary_base or '(unknown)'} — "
            "E2E gateway APIs were not executed."
        )
    rec.set_decisions(
        service_health=service_health,
        primary_service=primary_key,
        primary_base=primary_base,
        primary_health=service_health.get(primary_key, "UP" if primary_up else "DOWN"),
    )

    if run_cfg.get("apply_masterdata", True):
        _bob_progress("masterdata stub URLs (post-health refresh)")
        rec.begin_step("masterdata_apply", "Apply WireMock URLs to DSA masterdata")
        md_ok, md_msg = apply_masterdata_sql(md_sql_path, spec)
        summary.append(f"  masterdata: {md_msg}")
        rec.end_step("pass" if md_ok else "fail", md_msg)
        if not md_ok:
            summary.append("  WARN: masterdata apply failed — CC may still call real HDFC")
        elif run_cfg.get("restart_cc_after_masterdata", True) and primary_up:
            svc_cfg = (env_block.get("services") or {}).get(primary_key) or {}
            wait = boot_wait_seconds(spec)
            md_restart_msg = ""
            for md_key in masterdata_service_keys(spec):
                md_cfg = (env_block.get("services") or {}).get(md_key) or {}
                if not md_cfg:
                    continue
                rec.begin_step("md_restart", "Restart masterdata after stub URLs")
                summary.append(f"  restarting {md_key} so CC can load WireMock URLs...")
                stop_service(md_key)
                md_ok, md_msg = start_service(md_key, md_cfg, wait_seconds=wait, force=True)
                md_restart_msg = md_msg
                summary.append(f"  md_restart: {md_msg}")
                service_health[md_key] = "UP" if md_ok else "DOWN"
                rec.end_step("pass" if md_ok else "fail", md_msg)
                if not md_ok:
                    summary.append("  WARN: masterdata down — CC will use @NovopayConfig UAT defaults")
            rec.begin_step("cc_restart", "Restart CC after masterdata (reload HDFC URLs)")
            summary.append(f"  restarting {primary_key} for fresh masterdata config...")
            stop_service(primary_key)
            cc_ok, cc_msg = start_service(
                primary_key,
                svc_cfg,
                wait_seconds=wait,
                force=True,
            )
            summary.append(f"  cc_restart: {cc_msg}")
            primary_up = cc_ok
            service_health[primary_key] = "UP" if cc_ok else "DOWN"
            detail = cc_msg if not md_restart_msg else f"{md_restart_msg}; {cc_msg}"
            rec.end_step("pass" if cc_ok else "fail", detail)
        if run_cfg.get("apply_masterdata", True) and primary_up:
            rec.begin_step("redis_config_prime", "Prime CC Redis with WireMock URLs")
            prime_ok, prime_msg = prime_cc_config_cache(spec, port)
            redis_prime_msg = prime_msg
            summary.append(f"  redis prime: {prime_msg}")
            rec.end_step("pass" if prime_ok else "fail", prime_msg)
            if not prime_ok:
                summary.append("  WARN: redis prime failed — CC may still call UAT HDFC URLs")
    else:
        rec.begin_step("masterdata_apply", "Apply WireMock URLs to DSA masterdata")
        rec.end_step("skip", "run.apply_masterdata: false")

    unit_ids: set[str] = set()

    unit_list = [s for s in scenarios(spec) if (s.get("verification_level") or "").lower() == "unit"]
    if len(unit_list) > 1 and run_cfg.get("batch_unit_tests", True):
        _bob_progress(f"unit tests (batched {len(unit_list)} scenarios, one Gradle run)")
        all_tests: list[str] = []
        for sc in unit_list:
            for t in sc.get("gradle_tests") or []:
                if str(t).strip() and str(t).strip() not in all_tests:
                    all_tests.append(str(t).strip())
        batch_rc, batch_out = _run_unit_tests(all_tests)
        save_unit_evidence(ticket_dir, batch_out)
        for sc in unit_list:
            sid = sc.get("id", "?")
            sc_ok = batch_rc == 0
            rec.begin_step(f"unit_{sid}", f"Unit tests ({sid})")
            rec.end_step("pass" if sc_ok else "fail", f"batched gradle rc={batch_rc}")
            rec.add_scenario(sid, "unit", "pass" if sc_ok else "fail", f"batched rc={batch_rc}", 0)
            results[sid] = {"pass": sc_ok, "level": "unit"}
            summary.append(f"Scenario {sid}: level=unit batched rc={batch_rc}")
        unit_ids = {str(s.get("id")) for s in unit_list}

    for sc in scenarios(spec):
        sid = sc.get("id", "?")
        if sid in unit_ids:
            continue
        level = (sc.get("verification_level") or "e2e").lower()
        sc_t0 = time.time()
        summary.append(f"Scenario {sid}: level={level}")
        sc_ok = True
        sc_detail: list[str] = []
        scenario_crn = sc.get("crn") or f"{crn}-{sid}"
        if level in ("integration", "e2e"):
            scenario_crns[sid] = scenario_crn

        if level == "unit":
            _bob_progress(f"unit tests {sid}")
            rec.begin_step(f"unit_{sid}", f"Unit tests ({sid})")
            filt = sc.get("gradle_tests")
            if not filt:
                rec.end_step("fail", "missing gradle_tests in scenario")
                sc_ok = False
                sc_detail.append("unit: no gradle_tests")
                sc_ms = int((time.time() - sc_t0) * 1000)
                rec.add_scenario(
                    sid, level, "fail", "; ".join(sc_detail), sc_ms,
                    name=sc.get("name", ""), apis=[],
                )
                results[sid] = {"pass": False, "level": level}
                continue
            rc, out = _run_unit_tests(filt)
            save_unit_evidence(ticket_dir, out)
            summary.append(f"  unit tests rc={rc}")
            sc_ok = rc == 0
            rec.end_step("pass" if sc_ok else "fail", f"gradle rc={rc}")
            sc_detail.append(f"unit rc={rc}")
        elif level in ("integration", "e2e") and primary_up:
            _bob_progress(f"E2E {sid} (seed, API, DB)")
            steps = sc.get("steps") or []
            api_ids = [s.get("api_id") or s.get("api") for s in steps if s.get("api_id") or s.get("api")]
            rec.begin_step(f"pre_sql_{sid}", f"DB seed ({sid})")
            seed_ok, seed_msg = _run_pre_sql(sc, scenario_crn, spec, ticket_dir)
            if seed_ok:
                rec.end_step("pass", f"CRN={scenario_crn}; {seed_msg}")
            else:
                rec.end_step("fail", seed_msg)
                sc_ok = False
                sc_detail.append(f"pre_sql fail: {seed_msg}")
            runtime = apply_scenario_wiremock(ticket_dir, sid, stub_refs, port)
            from wiremock_runtime import start_wiremock

            start_wiremock(runtime, port, reload=True)
            if run_cfg.get("apply_masterdata", True):
                prime_cc_config_cache(spec, port)
            rec.begin_step(f"api_{sid}", f"API calls ({sid})")
            if steps:
                spec_env = spec.get("_env") or {}
                if not spec_env and spec.get("env_profile"):
                    from ticket_spec import load_env_profile_block

                    spec_env = load_env_profile_block(str(spec["env_profile"]))
                rc = tdd_engine.execute_scenario_steps(
                    ticket_dir, sc, spec_env, crn=scenario_crn
                )
                summary.append(f"  api rc={rc} CRN={scenario_crn}")
                sc_ok = rc == 0 and sc_ok
                scenario_api = sc.get("api") or {}
                if rc == 0:
                    for step in steps:
                        aid = step.get("api_id") or step.get("api")
                        if not aid:
                            continue
                        step_api = step.get("api_expect") or {}
                        if not step_api and aid == (api_ids[-1] if api_ids else ""):
                            step_api = scenario_api
                        if not step_api:
                            continue
                        payload = load_last_api_response(ticket_dir, sid, aid)
                        if payload is None:
                            api_ok, api_errs = False, [f"no saved response for {sid}-{aid}"]
                        else:
                            api_ok, api_errs = check_api_response(step_api, payload, aid)
                        summary.append(
                            f"  api assert {aid} {'PASS' if api_ok else 'FAIL'}: {api_errs}"
                        )
                        sc_ok = api_ok and sc_ok
                        rec.add_assertion(
                            sid,
                            f"api:{aid}",
                            api_ok,
                            step_api,
                            {"api_id": aid},
                            api_errs,
                        )
                        sc_detail.append(f"api:{aid} {'PASS' if api_ok else 'FAIL'}")
                rec.end_step("pass" if rc == 0 and sc_ok else "fail", ", ".join(api_ids) or "no api_id")
                sc_detail.append(f"apis={api_ids} rc={rc} crn={scenario_crn}")
                results[sid] = {"pass": sc_ok, "level": level, "api_executed": True}
            else:
                summary.append("  skip api: no steps")
                rec.end_step("skip", "no steps in scenario")
                sc_detail.append("api skipped")
                results[sid] = {"pass": False, "level": level, "api_executed": False}
        elif level in ("integration", "e2e"):
            if sc.get("pre_sql_file") or sc.get("pre_sql"):
                rec.begin_step(f"pre_sql_{sid}", f"DB seed ({sid})")
                seed_ok, seed_msg = _run_pre_sql(sc, scenario_crn, spec, ticket_dir)
                if seed_ok:
                    rec.end_step("pass", f"CRN={scenario_crn}; {seed_msg}")
                else:
                    rec.end_step("fail", seed_msg)
                    sc_ok = False
                    sc_detail.append(f"pre_sql fail: {seed_msg}")
            if not primary_up:
                block_reason = (
                    f"E2E blocked: `{primary_key}` DOWN at {primary_base or 'unknown'} "
                    f"(scenario {sid} APIs not called)"
                )
                e2e_blockers.append(block_reason)
                summary.append(f"  skip api: {primary_key} down")
                rec.begin_step(f"api_{sid}", f"API calls ({sid})")
                rec.end_step("fail", block_reason)
                sc_detail.append(block_reason)
                sc_ok = False
                results[sid] = {
                    "pass": False,
                    "level": level,
                    "api_executed": False,
                    "e2e_blocked": block_reason,
                }
            elif not wm_ok:
                block_reason = f"E2E blocked: WireMock unavailable (scenario {sid} APIs not called)"
                if block_reason not in e2e_blockers:
                    e2e_blockers.append(block_reason)
                rec.begin_step(f"api_{sid}", f"API calls ({sid})")
                rec.end_step("fail", block_reason)
                sc_detail.append(block_reason)
                sc_ok = False
                results[sid] = {
                    "pass": False,
                    "level": level,
                    "api_executed": False,
                    "e2e_blocked": block_reason,
                }

        db_expect = resolve_db_expect(sc, spec)
        if db_expect:
            rec.begin_step(f"db_{sid}", f"DB check ({sid})")
            audit = audit_settings(spec)
            query_crn = crn
            if level in ("integration", "e2e"):
                query_crn = sc.get("crn") or f"{crn}-{sid}"
            sql = build_audit_query(query_crn, spec)
            _rc, out = mysql_query(sql, schema=audit["schema"])
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
            sc_detail.append(f"db {'PASS' if ok else 'FAIL'} crn={query_crn}")
        else:
            sc_detail.append("no db expect")
            if level in ("integration", "e2e") and "transaction_audit" in (spec.get("evidence_required") or []):
                sc_ok = False
                sc_detail.append("e2e missing db: block")

        sc_ms = int((time.time() - sc_t0) * 1000)
        status = "pass" if sc_ok else "fail"
        step_apis = [
            s.get("api_id") or s.get("api")
            for s in (sc.get("steps") or [])
            if s.get("api_id") or s.get("api")
        ]
        rec.add_scenario(
            sid,
            level,
            status,
            "; ".join(sc_detail),
            sc_ms,
            name=sc.get("name", ""),
            apis=step_apis,
        )
        if sid not in results:
            results[sid] = {"pass": sc_ok, "level": level, "api_executed": False}

    if kafka_enabled(spec, kafka_discovery) or (spec.get("kafka_scenarios") or []):
        rec.begin_step("kafka_scenarios", "Kafka fixture scenarios (produce/consume/assert)")
        kafka_scenario_results = run_kafka_scenarios(spec, ticket_dir, kafka_discovery)
        ksum = format_kafka_scenario_summary(kafka_scenario_results)
        summary.append(f"  kafka scenarios: {ksum}")
        k_all_ok = all(r.get("pass") for r in kafka_scenario_results) if kafka_scenario_results else True
        rec.end_step("pass" if k_all_ok else "fail", ksum or "none")
        for r in kafka_scenario_results:
            sid = r.get("id", "K?")
            passed = bool(r.get("pass"))
            results[sid] = {"pass": passed, "level": "kafka", "api_executed": False}
            rec.add_scenario(
                sid,
                "kafka",
                "pass" if passed else "fail",
                "; ".join(str(x) for x in (r.get("detail") or [])),
                0,
                name=r.get("name", ""),
                apis=[],
            )

    kcfg = (spec.get("run") or {}).get("kafka") or {}
    if kafka_enabled(spec, kafka_discovery) and kcfg.get("capture_after_scenarios", True):
        rec.begin_step("kafka_capture", "Capture Kafka topic messages to evidence/")
        kafka_capture_results = capture_configured_topics(spec, ticket_dir, kafka_discovery)
        cap_lines = [
            f"{r.get('topic')}: {r.get('count', 0)} msg ({r.get('detail', '')})"
            for r in kafka_capture_results
        ]
        summary.append(f"  kafka capture: {'; '.join(cap_lines) or 'no topics'}")
        rec.end_step("pass", "; ".join(cap_lines)[:300] if cap_lines else "no messages")

    rec.begin_step("kafka_verify_doc", "Write KAFKA_VERIFY.md")
    kv_path = write_kafka_verify_commands(
        ticket_dir,
        spec,
        discovery=kafka_discovery,
        capture_results=kafka_capture_results,
        scenario_results=kafka_scenario_results,
        setup_fixes=(kafka_setup.fixes_applied if kafka_setup else None),
        setup_issues=(kafka_setup.issues_remaining if kafka_setup else None),
    )
    if kv_path:
        rec.set_decisions(kafka_verify_commands=str(kv_path))
        summary.append(f"  KAFKA_VERIFY: {kv_path}")
    rec.end_step("pass" if kv_path else "skip", str(kv_path) if kv_path else "kafka not enabled")

    redis_capture_results: list[dict] = []
    redis_scenario_results: list[dict] = []
    if redis_wanted(spec):
        rec.begin_step("redis_capture", "Capture Redis keys to evidence/redis/")
        redis_capture_results = capture_redis_evidence(
            ticket_dir, spec, prime_message=redis_prime_msg
        )
        cap_msg = "; ".join(r.get("detail", "") for r in redis_capture_results) or "skipped"
        summary.append(f"  redis capture: {cap_msg}")
        rec.end_step(
            "pass" if any(r.get("ok") for r in redis_capture_results) else "skip",
            cap_msg[:300],
        )
        rec.begin_step("redis_scenarios", "Redis scenario checks (ticket-spec)")
        redis_scenario_results = run_redis_scenarios(
            spec, ticket_dir, capture_results=redis_capture_results
        )
        if redis_scenario_results:
            rsum = ", ".join(
                f"{r.get('id')}:{'PASS' if r.get('pass') else 'FAIL'}" for r in redis_scenario_results
            )
            summary.append(f"  redis scenarios: {rsum}")
            rec.end_step(
                "pass" if all(r.get("pass") for r in redis_scenario_results) else "fail",
                rsum,
            )
        else:
            rec.end_step("skip", "no redis_scenarios")
        rec.begin_step("redis_verify_doc", "Write REDIS_VERIFY.md")
        rv_path = write_redis_verify_commands(
            ticket_dir,
            spec,
            capture_results=redis_capture_results,
            prime_message=redis_prime_msg,
        )
        if rv_path:
            rec.set_decisions(redis_verify_commands=str(rv_path))
            summary.append(f"  REDIS_VERIFY: {rv_path}")
        rec.end_step("pass" if rv_path else "skip", str(rv_path) if rv_path else "redis not requested")

    rec.begin_step("log_verify", "Log verify commands + search")
    log_cmd_path = write_log_verify_commands(ticket_dir, spec, base_crn, scenario_crns)
    log_cmd_msg = str(log_cmd_path) if log_cmd_path else "no E2E scenarios"
    if log_cmd_path:
        rec.set_decisions(log_verify_commands=str(log_cmd_path))
    log_search_ok, log_search_msg = run_log_search_script(ticket_dir)
    if log_search_ok:
        rec.set_decisions(log_search_ran=True)
    summary.append(f"  log verify: {log_cmd_msg}")
    summary.append(f"  log search: {log_search_msg}")
    rec.end_step("pass" if log_cmd_path else "skip", f"{log_cmd_msg}; {log_search_msg}")

    rec.begin_step("evidence", "Collect API / log / Kafka / Redis evidence")
    copy_api_responses(ticket_dir)
    log_file = ticket_dir / "log-search.txt"
    if log_file.exists():
        save_log_evidence(ticket_dir, log_file.read_text(encoding="utf-8"))
        log_ev_msg = "log-search.txt copied"
    else:
        log_ev_msg = "no log-search.txt (set LOGS_DIR in bob setup)"
    kafka_ev = list((ticket_dir / "evidence" / "kafka").glob("*")) if (ticket_dir / "evidence" / "kafka").is_dir() else []
    redis_ev = list((ticket_dir / "evidence" / "redis").glob("*")) if (ticket_dir / "evidence" / "redis").is_dir() else []
    ev_parts = [log_ev_msg]
    if kafka_ev:
        ev_parts.append(f"kafka: {len(kafka_ev)} file(s)")
    if redis_ev:
        ev_parts.append(f"redis: {len(redis_ev)} file(s)")
    rec.end_step("pass" if log_file.exists() or kafka_ev or redis_ev else "skip", "; ".join(ev_parts))

    rec.begin_step("postman_export", "Postman collection export")
    pm_path, pm_msg = export_postman_for_ticket(spec, ticket_dir, wiremock_port=port)
    summary.append(f"  {pm_msg}")
    rec.end_step("pass" if pm_path else "fail", pm_msg)
    if pm_path:
        rec.set_decisions(postman_collection=str(pm_path))

    publish_report(ticket_dir, spec, summary)
    write_run_manifest(ticket_dir, spec, results)

    overall = all(r.get("pass") for r in results.values()) if results else False
    exit_code = 0 if overall else 1

    e2e_levels = ("integration", "e2e")
    planned_e2e = [
        sc
        for sc in scenarios(spec)
        if (sc.get("verification_level") or "e2e").lower() in e2e_levels and (sc.get("steps") or [])
    ]
    not_executed = [
        sid
        for sid, r in results.items()
        if r.get("level") in e2e_levels and not r.get("api_executed")
    ]
    if require_e2e and planned_e2e and not_executed:
        overall = False
        exit_code = 1
        banner = [
            "",
            "=" * 72,
            "E2E NOT EXECUTED — unit/other results do not replace live API + DB proof.",
            "=" * 72,
        ]
        for sid in not_executed:
            reason = results.get(sid, {}).get("e2e_blocked") or "API steps were not run"
            banner.append(f"  - {sid}: {reason}")
        for msg in e2e_blockers:
            if msg not in banner:
                banner.append(f"  - {msg}")
        banner.append("Fix services/WireMock and re-run: bob validate-ticket " + tid)
        banner.append("=" * 72)
        summary = banner + summary
        rec.set_decisions(e2e_blocked=True, e2e_not_executed=not_executed, e2e_blockers=e2e_blockers)
    summary.append(f"CRN(base)={crn}")
    crns_for_summary = e2e_scenario_crns(spec, base_crn, scenario_crns)
    if crns_for_summary:
        summary.append("E2E scenario CRNs (use in SQL):")
        for sid, sc_crn in crns_for_summary.items():
            summary.append(f"  {sid}: {sc_crn}")

    db_verify_path = _persist_db_verify(ticket_dir, spec, base_crn, scenario_crns, rec)
    if db_verify_path:
        summary.append(f"DB_VERIFY_QUERIES: {db_verify_path}")

    rec.set_decisions(
        wiremock_status=wiremock_status,
        wiremock_detail=wiremock_detail,
    )
    run_data = rec.finalize(exit_code)

    rec.begin_step("eval_regression", "Compare run to eval baseline")
    from eval_regression import (
        auto_eval_after_run,
        should_fail_on_regression,
        write_eval_regression_md,
    )

    eval_result = auto_eval_after_run(ticket_dir, run_data, spec)
    eval_path = write_eval_regression_md(ticket_dir, eval_result, run_data)
    rec.set_decisions(eval_regression=eval_result.to_dict(), eval_regression_md=str(eval_path))
    if not eval_result.ok:
        summary.append(f"  eval regression: FAIL — {eval_result.message}")
        if should_fail_on_regression(spec):
            exit_code = 1
            run_data["exit_code"] = 1
            run_data["overall"] = "FAIL"
    else:
        summary.append(f"  eval regression: {eval_result.message}")
    rec.end_step("pass" if eval_result.ok else "fail", eval_result.message[:200])

    kafka_md: list[str] = []
    if kafka_enabled(spec, kafka_discovery) and kafka_setup and not kafka_setup.skipped:
        kafka_md = [format_setup_markdown(kafka_setup)]

    run_data["service_health_md"] = format_markdown_section(
        boot_summary,
        health_summary,
        primary_service=primary_key,
        primary_health=service_health.get(primary_key, "UP" if primary_up else "DOWN"),
        wiremock_status=wiremock_status,
        wiremock_detail=wiremock_detail,
        e2e_blockers=e2e_blockers if require_e2e else None,
    )
    if kafka_md:
        run_data["service_health_md"] = (run_data.get("service_health_md") or []) + kafka_md
    md_path, _, html_path = publish_run_summary(
        ticket_dir, run_data, spec=spec, execution_log=summary
    )
    update_session(tid, title, results, run_data=run_data)

    def _safe_print(text: str) -> None:
        try:
            print(text)
        except UnicodeEncodeError:
            print(text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
                sys.stdout.encoding or "utf-8", errors="replace"
            ))

    for line in run_data.get("service_health_md") or []:
        if line.strip() and line.startswith("##"):
            _safe_print("")
        if line.strip():
            _safe_print(line)
    _safe_print("\n".join(summary))
    _safe_print(f"\nREPORT: {md_path}")
    _safe_print(f"TEST_PLAN: {ticket_dir / 'TEST_PLAN.md'}")
    if html_path:
        print(f"REPORT.html:  {html_path}")
    if pm_path:
        print(f"POSTMAN:      {pm_path}")
        print(f"POSTMAN_ENV:  {ticket_dir / 'postman' / 'local.postman_environment.json'}")
    return exit_code


def spec_path_is_ts(ticket_dir: Path) -> bool:
    return (ticket_dir / "ticket-spec.yaml").exists()


if __name__ == "__main__":
    td = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not td:
        print("Usage: run_flow.py <ticket-dir>", file=sys.stderr)
        sys.exit(1)
    sys.exit(run(td))


