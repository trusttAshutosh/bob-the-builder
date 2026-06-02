"""REDIS_VERIFY.md + evidence/redis/ — parity with LOG_VERIFY and DB_VERIFY."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stub_registry import _cc_config_redis_key, _tenant_redis_db_index


def redis_config(spec: dict) -> dict:
    return (spec.get("run") or {}).get("redis") or {}


def redis_wanted(spec: dict) -> bool:
    """Whether validate-ticket should emit Redis verify + evidence."""
    evidence = set(spec.get("evidence_required") or [])
    if "redis" in evidence:
        return True
    rcfg = redis_config(spec)
    mode = str(rcfg.get("mode", "auto")).lower()
    if mode == "off":
        return False
    if mode == "on":
        return True
    # auto: CC config cache when masterdata/stubs present
    if spec.get("masterdata") or spec.get("stubs"):
        return True
    if (spec.get("impacted") or {}).get("bank_operations"):
        return True
    return bool(rcfg.get("capture_keys") or rcfg.get("scan_pattern"))


def _redis_connection(spec: dict | None = None) -> tuple[str, str, int]:
    host = os.environ.get("REDIS_HOST", "localhost").strip() or "localhost"
    port = os.environ.get("REDIS_PORT", "6379").strip() or "6379"
    tenant = os.environ.get("TENANT", "dsa").strip() or "dsa"
    db = _tenant_redis_db_index(tenant)
    if spec:
        rcfg = redis_config(spec)
        if rcfg.get("host"):
            host = str(rcfg["host"])
        if rcfg.get("port"):
            port = str(rcfg["port"])
        if rcfg.get("db") is not None:
            db = int(rcfg["db"])
    rcfg_db = os.environ.get("TENANT_REDIS_DB", "")
    if rcfg_db.isdigit():
        db = int(rcfg_db)
    return host, port, db


def _redis_cli_base(spec: dict | None = None) -> list[str] | None:
    host, port, db = _redis_connection(spec)
    for cli in ("redis-cli", "/usr/bin/redis-cli"):
        try:
            r = subprocess.run(
                [cli, "-h", host, "-p", port, "PING"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if r.returncode == 0 and "PONG" in (r.stdout or "").upper():
                return [cli, "-h", host, "-p", port, "-n", str(db)]
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            continue
    return None


def _default_scan_pattern(spec: dict) -> str:
    rcfg = redis_config(spec)
    if rcfg.get("scan_pattern"):
        return str(rcfg["scan_pattern"])
    tenant = os.environ.get("TENANT", "dsa").strip() or "dsa"
    env = os.environ.get("NOVOPAY_SERVICE_ENV", "dev").strip().lower() or "dev"
    service = str(rcfg.get("service", "CREDIT-CARD-MANAGEMENT"))
    return f"{env}_{tenant}_config_{service}_*"


def _keys_to_check(spec: dict) -> list[str]:
    rcfg = redis_config(spec)
    explicit = [str(k) for k in (rcfg.get("capture_keys") or []) if k]
    if explicit:
        return explicit
    tenant = os.environ.get("TENANT", "dsa").strip() or "dsa"
    service = str(rcfg.get("service", "CREDIT-CARD-MANAGEMENT"))
    keys: list[str] = []
    for row in spec.get("masterdata") or []:
        pk = str(row.get("prop_key", "")).strip()
        if pk:
            keys.append(_cc_config_redis_key(tenant, pk, service))
    return keys


def _scan_keys(cli_base: list[str], pattern: str) -> list[str]:
    try:
        r = subprocess.run(
            [*cli_base, "--scan", "--pattern", pattern],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            return []
        return [k for k in (r.stdout or "").splitlines() if k.strip()]
    except (subprocess.TimeoutExpired, OSError):
        return []


def _key_type_and_ttl(cli_base: list[str], key: str) -> tuple[str, str]:
    try:
        tr = subprocess.run(
            [*cli_base, "TYPE", key],
            capture_output=True,
            text=True,
            timeout=5,
        )
        ttl_r = subprocess.run(
            [*cli_base, "TTL", key],
            capture_output=True,
            text=True,
            timeout=5,
        )
        typ = (tr.stdout or "").strip() or "?"
        ttl = (ttl_r.stdout or "").strip() or "?"
        return typ, ttl
    except (subprocess.TimeoutExpired, OSError):
        return "?", "?"


def capture_redis_evidence(
    ticket_dir: Path,
    spec: dict,
    *,
    prime_message: str = "",
) -> list[dict[str, Any]]:
    """Snapshot Redis keys into evidence/redis/ (like log-search -> evidence/logs)."""
    out_dir = ticket_dir / "evidence" / "redis"
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    cli_base = _redis_cli_base(spec)
    if not cli_base:
        summary = {
            "ok": False,
            "detail": "redis-cli unavailable — use commands in REDIS_VERIFY.md",
            "keys": [],
            "prime_message": prime_message,
        }
        (out_dir / "capture-summary.json").write_text(
            json.dumps(summary, indent=2) + "\n",
            encoding="utf-8",
        )
        return [{"ok": False, "detail": summary["detail"], "evidence": None}]

    host, port, db = _redis_connection(spec)
    keys = _keys_to_check(spec)
    pattern = _default_scan_pattern(spec)
    if not keys:
        keys = _scan_keys(cli_base, pattern)
    keys = sorted(set(keys))[: int(redis_config(spec).get("max_keys", 50))]

    captured: list[dict[str, Any]] = []
    for key in keys:
        typ, ttl = _key_type_and_ttl(cli_base, key)
        entry: dict[str, Any] = {"key": key, "type": typ, "ttl": ttl}
        try:
            if typ == "string":
                gr = subprocess.run(
                    [*cli_base, "GET", key],
                    capture_output=True,
                    timeout=5,
                )
                raw = gr.stdout or b""
                entry["value_preview"] = (
                    raw[:200].hex() if len(raw) > 80 else raw.decode("utf-8", errors="replace")
                )
                entry["value_bytes"] = len(raw)
            else:
                entry["value_preview"] = f"({typ} — use redis-cli in REDIS_VERIFY.md)"
        except (subprocess.TimeoutExpired, OSError) as exc:
            entry["error"] = str(exc)
        captured.append(entry)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ev_path = out_dir / f"capture-{ts}.json"
    payload = {
        "host": host,
        "port": port,
        "db": db,
        "pattern": pattern,
        "prime_message": prime_message,
        "keys": captured,
    }
    ev_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    (out_dir / "keys-index.txt").write_text(
        "\n".join(f"{e.get('key')}\t{e.get('type')}\t{e.get('ttl')}" for e in captured) + "\n",
        encoding="utf-8",
    )

    ok = bool(captured) or "already empty" in (prime_message or "").lower()
    results.append(
        {
            "ok": ok,
            "detail": f"{len(captured)} key(s) on db={db}",
            "count": len(captured),
            "evidence": str(ev_path),
        }
    )
    return results


def write_redis_verify_commands(
    ticket_dir: Path,
    spec: dict,
    *,
    capture_results: list[dict[str, Any]] | None = None,
    prime_message: str = "",
) -> Path | None:
    if not redis_wanted(spec):
        return None

    host, port, db = _redis_connection(spec)
    pattern = _default_scan_pattern(spec)
    keys = _keys_to_check(spec)
    cli_base = _redis_cli_base(spec)

    lines = [
        "# Redis verification (Bob)",
        "",
        "_Generated by Bob `validate-ticket`. Use after WireMock masterdata / config prime._",
        "",
        f"Ticket: `{spec.get('ticket_id', ticket_dir.name)}`",
        f"**REDIS_HOST:** `{host}` · **port:** `{port}` · **db:** `{db}`",
        f"**Scan pattern:** `{pattern}`",
        "",
    ]
    if prime_message:
        lines += ["## Last run (config prime)", "", f"- {prime_message}", ""]

    if not cli_base:
        lines += [
            "## Setup required",
            "",
            "`redis-cli` not found or Redis not reachable. Install Redis locally and set in `user.env`:",
            "",
            "```",
            "REDIS_HOST=127.0.0.1",
            "REDIS_PORT=6379",
            "```",
            "",
            "CC NovopayConfig cache uses JDK-serialized values — Bob primes via `validate-ticket` when `masterdata[]` is set.",
            "",
        ]
    else:
        cli_show = " ".join(shlex.quote(x) for x in cli_base)
        lines += [
            "## Quick commands",
            "",
            "```bash",
            f"{cli_show} PING",
            f'{cli_show} --scan --pattern "{pattern}"',
            "```",
            "",
        ]

    if keys:
        lines += ["## Expected keys (from ticket masterdata)", ""]
        for k in keys:
            lines.append(f"- `{k}`")
        lines += ["", "## GET commands", "", "```bash"]
        if cli_base:
            cli_show = " ".join(shlex.quote(x) for x in cli_base)
            for k in keys[:20]:
                lines.append(f"{cli_show} GET {shlex.quote(k)}")
        lines.append("```")
        lines.append("")

    lines += [
        "## redis_scenarios (optional in ticket-spec.yaml)",
        "",
        "```yaml",
        "redis_scenarios:",
        "  - id: R1",
        "    name: Config cache present",
        "    pattern: dev_dsa_config_CREDIT-CARD-MANAGEMENT_*",
        "    min_keys: 1",
        "```",
        "",
    ]

    ev_dir = ticket_dir / "evidence" / "redis"
    if ev_dir.is_dir() and any(ev_dir.iterdir()):
        lines += ["## Captured evidence", "", "| File |", "|------|"]
        for f in sorted(ev_dir.iterdir()):
            if f.is_file():
                rel = f.relative_to(ticket_dir).as_posix()
                lines.append(f"| [{f.name}](./{rel}) |")
        lines.append("")

    if capture_results:
        lines += ["## Capture results (last run)", ""]
        for row in capture_results:
            lines.append(
                f"- {row.get('detail', '')} — evidence: `{row.get('evidence') or '—'}`"
            )
        lines.append("")

    lines += [
        "## Related",
        "",
        "- Host template: `deploy/tdd/INFRA_FOR_BOB.md` (Redis + platform_master)",
        "- Product doc: `bob-the-builder/docs/REDIS_FOR_BOB.md`",
        "",
    ]

    path = ticket_dir / "REDIS_VERIFY.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_redis_scenarios(
    spec: dict,
    ticket_dir: Path,
    *,
    capture_results: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Optional ticket-spec redis_scenarios[] assertions."""
    scenarios = spec.get("redis_scenarios") or []
    if not scenarios:
        return []

    cli_base = _redis_cli_base(spec)
    out: list[dict[str, Any]] = []
    key_count = 0
    if capture_results:
        for row in capture_results:
            key_count = max(key_count, int(row.get("count") or 0))

    for sc in scenarios:
        sid = sc.get("id", "?")
        pattern = str(sc.get("pattern") or _default_scan_pattern(spec))
        min_keys = int(sc.get("min_keys", 1))
        passed = True
        detail: list[str] = []
        found = 0
        if cli_base:
            found = len(_scan_keys(cli_base, pattern))
        elif key_count:
            found = key_count
        if found < min_keys:
            passed = False
            detail.append(f"expected >= {min_keys} keys matching `{pattern}`, found {found}")
        else:
            detail.append(f"{found} key(s) for `{pattern}`")
        out.append(
            {
                "id": sid,
                "name": sc.get("name", ""),
                "pass": passed,
                "detail": detail,
                "pattern": pattern,
            }
        )
    return out
