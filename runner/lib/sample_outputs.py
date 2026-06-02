"""Regenerate committed sample validate-ticket artifacts (assets/examples/sample-validate-output/)."""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

SAMPLE_TICKET_ID = "sample-gateway-health-check"
# Pinned so `bob refresh-samples` matches on CI (Linux) and developer machines (Windows).
SAMPLE_FROZEN_TS = "2026-06-01T12:00:00"
SAMPLE_FROZEN_TS_EVAL = "2026-06-01 12:00:00"
SAMPLE_FROZEN_DATE = "20260601"
SAMPLE_MANIFEST_COMMIT = "sample-pinned"
# Committed under the bob-the-builder git root (not BOB_HOME live catalogs).
SAMPLE_REL = Path("assets/examples/sample-validate-output")


def sample_repo_root(product_root: Path | None = None) -> Path:
    """Git product root (bob-the-builder/), not .local/bob-the-builder fallback."""
    if product_root is not None:
        return product_root.resolve()
    from host_repo import runner_bootstrap_repo

    return runner_bootstrap_repo().resolve()

# Paths that trigger auto-refresh on verify-product --update / post-commit
REFRESH_TRIGGER_GLOBS = (
    "runner/lib/run_summary.py",
    "runner/lib/run_flow.py",
    "runner/lib/context_assembly.py",
    "runner/lib/eval_regression.py",
    "runner/lib/kafka_verify.py",
    "runner/lib/redis_verify.py",
    "runner/lib/kafka_discovery.py",
    "runner/lib/audit_config.py",
    "runner/lib/postman_export.py",
    "runner/lib/sample_outputs.py",
    "runner/schemas/ticket-spec.schema.yaml",
)


def sample_output_dir(product_root: Path | None = None) -> Path:
    return sample_repo_root(product_root) / SAMPLE_REL


def sample_seed_dir(product_root: Path | None = None) -> Path:
    return sample_repo_root(product_root) / "runner" / "_seed" / "sample-validate-output"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _normalize_bundle_lf(ticket_dir: Path) -> None:
    """Force LF in committed sample bundle (Windows dev + Linux CI)."""
    for path in ticket_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {
            ".md",
            ".html",
            ".json",
            ".sql",
            ".txt",
            ".yaml",
            ".yml",
        }:
            continue
        raw = path.read_bytes()
        if b"\r" not in raw:
            continue
        text = raw.decode("utf-8")
        _write_text(path, text.replace("\r\n", "\n").replace("\r", "\n"))


def _copy_pinned_from_seed(ticket_dir: Path, product_root: Path | None) -> None:
    """Copy machine-independent artifacts (context pack, Postman) from runner/_seed/."""
    seed = sample_seed_dir(product_root)
    for rel in ("CONTEXT_PACK.md", "REDIS_VERIFY.md", "postman"):
        src = seed / rel
        dst = ticket_dir / rel
        if not src.exists():
            raise FileNotFoundError(f"Missing sample seed: {src}")
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def _load_sample_spec(ticket_dir: Path, product_root: Path | None = None) -> dict:
    from _yaml_util import load
    from ticket_spec import load_env_profile_block

    spec_path = ticket_dir / "ticket-spec.yaml"
    if not spec_path.is_file():
        raise FileNotFoundError(
            f"Missing {spec_path} — sample bundle must live in the git repo under {SAMPLE_REL}"
        )
    spec = load(spec_path)
    spec.setdefault("version", 2)
    prof = spec.get("env_profile", "local-dsa")
    tpl_root = sample_repo_root(product_root) / "templates/host-deploy-tdd"
    block = load_env_profile_block(prof, base=tpl_root)
    if not block:
        raise FileNotFoundError(
            f"Sample env profile `{prof}` not found under {tpl_root / 'deploy/tdd'}"
        )
    spec["_env"] = block
    spec["ticket_id"] = (spec.get("ticket") or {}).get("id") or ticket_dir.name
    return spec


def _demo_run_data(spec: dict, ticket_dir: Path) -> dict:
    ticket = spec.get("ticket") or {}
    tid = ticket.get("id", ticket_dir.name)
    now = SAMPLE_FROZEN_TS
    base_crn = f"BOB-SAMPLE-{SAMPLE_FROZEN_DATE}"
    scenario_crns = {"S1": f"{base_crn}-S1", "S2": f"{base_crn}-S2"}

    return {
        "ticket_id": tid,
        "title": ticket.get("title", ""),
        "started_at": now,
        "finished_at": now,
        "duration_seconds": 42.5,
        "overall": "PASS",
        "exit_code": 0,
        "branch": "main",
        "decisions": {
            "branch": "main",
            "crn": base_crn,
            "scenario_crns": scenario_crns,
            "wiremock_status": "UP",
            "wiremock_detail": "127.0.0.1:9090 (sample — not started for doc bundle)",
            "context_pack": str((ticket_dir / "CONTEXT_PACK.md").name),
            "eval_regression_md": str((ticket_dir / "EVAL_REGRESSION.md").name),
            "kafka_verify_commands": True,
            "api_catalog": "BOB_HOME/api-catalog (from discover-apis on host)",
            "stubs_applied": [s.get("ref", "") for s in (spec.get("stubs") or [])],
            "env_profile": spec.get("env_profile", "local-dsa"),
            "primary_service": (spec.get("_env") or {}).get("primary_service", "credit_card_management"),
        },
        "steps": [
            {
                "id": "context_pack",
                "label": "Assemble CONTEXT_PACK",
                "status": "pass",
                "detail": "prefs + stale + hybrid retrieval",
                "duration_ms": 120,
            },
            {
                "id": "wiremock_start",
                "label": "WireMock runtime",
                "status": "pass",
                "detail": "sample stub profile",
                "duration_ms": 800,
            },
            {
                "id": "health_credit_card_management",
                "label": "Health credit_card_management",
                "status": "pass",
                "detail": "http://localhost:8016/cc-mgmt (illustrative)",
                "duration_ms": 200,
            },
            {
                "id": "scenario_S1",
                "label": "Scenario S1",
                "status": "pass",
                "detail": "inquireCardEligibility — API + DB assert",
                "duration_ms": 1500,
            },
            {
                "id": "eval_regression",
                "label": "Eval regression",
                "status": "pass",
                "detail": "No regressions vs baseline",
                "duration_ms": 40,
            },
        ],
        "scenarios": [
            {
                "id": "S1",
                "name": "Happy path — eligibility inquiry",
                "level": "e2e",
                "status": "pass",
                "detail": "API 200; DB expect txn_status=SUCCESS",
                "duration_ms": 1500,
                "apis": ["inquireCardEligibility"],
            },
            {
                "id": "S2",
                "name": "Integration — processor unit scope",
                "level": "integration",
                "status": "pass",
                "detail": "Recorded as pass in sample bundle",
                "duration_ms": 0,
                "apis": [],
            },
        ],
        "assertions": [
            {
                "scenario_id": "S1",
                "kind": "db",
                "passed": True,
                "expected": {"txn_status": "SUCCESS", "txn_result_code": "000"},
                "actual": {"txn_status": "SUCCESS", "txn_result_code": "000"},
                "errors": [],
            }
        ],
        "evidence": {},
        "service_health_md": [
            "",
            "## Service health",
            "",
            "| Service | Status | Detail |",
            "|---------|--------|--------|",
            "| credit_card_management (primary) | UP | http://localhost:8016/cc-mgmt |",
            "| wiremock | UP | :9090 |",
            "",
            "_Sample bundle — illustrative only._",
            "",
        ],
    }


def _demo_kafka_discovery() -> Any:
    from kafka_discovery import KafkaBinding, KafkaDiscoveryResult

    return KafkaDiscoveryResult(
        mode_requested="auto",
        repos_scanned=["novopay-platform-creditcard-management"],
        seed_files=["deploy/application/dist/MessageBroker.xml"],
        bindings=[
            KafkaBinding(
                binding_id="sample-producer",
                role="producer",
                repo="novopay-platform-creditcard-management",
                source="sample_outputs.py (illustrative)",
                topic_template="{tenant}_{environment}_sample_events",
                detail="Demonstrates KAFKA_VERIFY.md shape",
            )
        ],
        bootstrap_properties=[
            {
                "file": "application.properties",
                "bootstrap": "localhost:9092",
            }
        ],
        tenant="dsa",
        environment="dev",
    )


def _write_db_verify(ticket_dir: Path, spec: dict, run_data: dict) -> Path | None:
    from run_flow import _write_db_verify_queries

    base_crn = run_data["decisions"]["crn"]
    return _write_db_verify_queries(
        ticket_dir,
        spec,
        base_crn,
        run_data["decisions"].get("scenario_crns"),
    )


def _write_log_verify(ticket_dir: Path, spec: dict) -> Path:
    patterns = []
    for sc in spec.get("scenarios") or []:
        patterns.extend(sc.get("log_patterns") or [])
    lines = [
        "# Log verification commands (sample)",
        "",
        "Run on the host where application logs are written (`LOGS_DIR` from `bob setup`).",
        "",
        "```bash",
        f"cd \"$LOGS_DIR\"",
    ]
    for p in patterns or ["inquireCardEligibility"]:
        lines.append(f'rg -n "{p}" . --glob "*.log" | head -50')
    lines.extend(["```", ""])
    path = ticket_dir / "LOG_VERIFY_COMMANDS.md"
    _write_text(path, "\n".join(lines) + "\n")
    return path


def _write_evidence_samples(ticket_dir: Path, spec: dict, run_data: dict) -> None:
    ev = ticket_dir / "evidence"
    for sub in ("api", "db", "logs", "unit", "kafka", "redis"):
        (ev / sub).mkdir(parents=True, exist_ok=True)

    s1_crn = run_data["decisions"]["scenario_crns"]["S1"]
    _write_text(
        ev / "api" / "S1-response.json",
        json.dumps(
            {
                "status": "SUCCESS",
                "response_code": "000",
                "client_reference_code": s1_crn,
                "_note": "Synthetic sample — real runs write curl output here",
            },
            indent=2,
        )
        + "\n",
    )
    _write_text(
        ev / "db" / "S1-audit-row.txt",
        f"client_reference_code={s1_crn}\ntxn_status=SUCCESS\ntxn_result_code=000\n",
    )
    _write_text(
        ev / "logs" / "S1-snippet.txt",
        "INFO inquireCardEligibility — sample log line for documentation\n",
    )
    _write_text(
        ev / "kafka" / "capture-dsa_dev_sample_events-sample.jsonl",
        json.dumps({"sample": True, "topic": "dsa_dev_sample_events", "payload": {"status": "ok"}})
        + "\n",
    )
    _write_text(
        ev / "redis" / "capture-sample.json",
        json.dumps(
            {
                "host": "127.0.0.1",
                "port": "6379",
                "db": 2,
                "pattern": "dev_dsa_config_CREDIT-CARD-MANAGEMENT_*",
                "keys": [
                    {
                        "key": "dev_dsa_config_CREDIT-CARD-MANAGEMENT_sample_prop",
                        "type": "string",
                        "ttl": "-1",
                        "value_preview": "(JDK-serialized — sample)",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
    )


def _write_readme(ticket_dir: Path, manifest: dict) -> Path:
    lines = [
        "# Sample validate-ticket output",
        "",
        "This folder is **generated** by `bob refresh-samples` (also runs on `bob verify-product --update` and post-commit).",
        "It shows what Bob produces after a fictional requirement — without needing your machine's services running.",
        "",
        "## Requirement → artifacts",
        "",
        "| You write | Bob generates (this folder) |",
        "|-----------|---------------------------|",
        "| [REQUIREMENT.md](./REQUIREMENT.md) user story | [ticket-spec.yaml](./ticket-spec.yaml), [TEST_PLAN.md](./TEST_PLAN.md) |",
        "| `bob init-ticket` / analyst fills spec | Same + scenarios, stubs, `run.*` flags |",
        "| `bob validate-ticket <id>` on a **host** repo | [REPORT.md](./REPORT.md), [REPORT.html](./REPORT.html), [run-summary.json](./run-summary.json) |",
        "| (same run) | [CONTEXT_PACK.md](./CONTEXT_PACK.md), [EVAL_REGRESSION.md](./EVAL_REGRESSION.md), [KAFKA_VERIFY.md](./KAFKA_VERIFY.md) |",
        "| (same run) | [DB_VERIFY_QUERIES.sql](./DB_VERIFY_QUERIES.sql), [LOG_VERIFY_COMMANDS.md](./LOG_VERIFY_COMMANDS.md), [REDIS_VERIFY.md](./REDIS_VERIFY.md) |",
        "| (same run) | [evidence/](./evidence/) — api, db, logs, kafka, redis |",
        "",
        "## Regenerate",
        "",
        "```bash",
        "cd bob-the-builder",
        "python bob.py refresh-samples",
        "```",
        "",
        f"_Last generated: {manifest.get('generated_at', '')} · Bob {manifest.get('bob_version', '')} · commit `{manifest.get('git_commit', '')}`_",
        "",
        "See [docs/README.md](../../docs/README.md) for full documentation.",
        "",
    ]
    path = ticket_dir / "README.md"
    _write_text(path, "\n".join(lines) + "\n")
    return path


def refresh_sample_outputs(*, product_root: Path | None = None, quiet: bool = False) -> list[Path]:
    """Rewrite sample bundle using current run_summary / eval / kafka writers (pinned for CI)."""
    from eval_regression import capture_baseline, compare_to_baseline, write_eval_regression_md
    from kafka_discovery import write_discovery_artifact
    from kafka_verify import write_kafka_verify_commands
    from run_summary import ensure_test_plan, publish_run_summary

    root = sample_repo_root(product_root)
    os.environ.setdefault("BOB_PRODUCT_ROOT", str(root))
    ticket_dir = sample_output_dir(root)
    ticket_dir.mkdir(parents=True, exist_ok=True)

    spec = _load_sample_spec(ticket_dir, root)
    run_data = _demo_run_data(spec, ticket_dir)
    execution_log = [
        "=== Bob sample-validate-output (synthetic PASS run) ===",
        f"ticket={run_data['ticket_id']}",
        "This bundle is for documentation; run validate-ticket on your host repo for real evidence.",
    ]

    ensure_test_plan(ticket_dir, spec)
    _write_evidence_samples(ticket_dir, spec, run_data)
    _copy_pinned_from_seed(ticket_dir, root)
    run_data["decisions"]["context_pack"] = "CONTEXT_PACK.md"
    run_data["decisions"]["redis_verify_commands"] = "REDIS_VERIFY.md"

    disc = _demo_kafka_discovery()
    write_discovery_artifact(ticket_dir, disc)
    write_kafka_verify_commands(
        ticket_dir,
        spec,
        discovery=disc,
        setup_fixes=["Sample: would run `bob kafka up` when Docker is available"],
        setup_issues=[],
        scenario_results=[
            {
                "id": "K1",
                "pass": True,
                "topic": "dsa_dev_sample_events",
                "detail": ["sample scenario"],
                "evidence": "evidence/kafka/capture-dsa_dev_sample_events-sample.jsonl",
            }
        ],
    )
    _write_db_verify(ticket_dir, spec, run_data)
    _write_log_verify(ticket_dir, spec)

    capture_baseline(ticket_dir, run_data, captured_at=SAMPLE_FROZEN_TS)
    eval_result = compare_to_baseline(ticket_dir, run_data)
    write_eval_regression_md(
        ticket_dir, eval_result, run_data, checked_at=SAMPLE_FROZEN_TS_EVAL
    )

    _write_text(ticket_dir / "execution-summary.txt", "\n".join(execution_log) + "\n")

    publish_run_summary(
        ticket_dir,
        run_data,
        spec=spec,
        execution_log=execution_log,
        relative_paths=True,
    )

    try:
        from builder_cli import VERSION as bob_version
    except Exception:
        bob_version = "?"

    manifest = {
        "generated_at": SAMPLE_FROZEN_TS,
        "bob_version": bob_version,
        "git_commit": SAMPLE_MANIFEST_COMMIT,
        "ticket_id": run_data["ticket_id"],
        "files": sorted(
            str(p.relative_to(ticket_dir)).replace("\\", "/")
            for p in ticket_dir.rglob("*")
            if p.is_file() and p.name != "MANIFEST.json"
        ),
    }
    manifest_path = ticket_dir / "MANIFEST.json"
    _write_text(manifest_path, json.dumps(manifest, indent=2) + "\n")

    _write_readme(ticket_dir, manifest)
    _normalize_bundle_lf(ticket_dir)

    written = [p for p in ticket_dir.rglob("*") if p.is_file()]
    if not quiet:
        print(f"Sample outputs refreshed: {ticket_dir} ({len(written)} files)")
    return written


def should_refresh_samples(changed_paths: list[str] | None = None) -> bool:
    """True when verify-product --update should regenerate samples."""
    if changed_paths is None:
        return True
    normalized = {p.replace("\\", "/") for p in changed_paths}
    for trig in REFRESH_TRIGGER_GLOBS:
        if any(p == trig or p.endswith("/" + trig) for p in normalized):
            return True
    return False
