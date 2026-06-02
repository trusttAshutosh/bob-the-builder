from __future__ import annotations

import errno
import json
import os
import shutil
from pathlib import Path

from _yaml_util import load
from bob_home import stub_registry_dir, wiremock_runtime_dir


def registry_root() -> Path:
    return stub_registry_dir()


def resolve_fixture(ref: str) -> tuple[Path, dict]:
    """ref format: bankOperation/fixture-id"""
    op, fid = ref.split("/", 1)
    base = registry_root() / "bank-operations" / op
    path = base / f"{fid}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Stub fixture not found: {ref} ({path})")
    return base, load(path)


def _clear_mappings_and_files(runtime: Path) -> None:
    for sub in ("mappings", "__files"):
        d = runtime / sub
        d.mkdir(parents=True, exist_ok=True)
        for f in d.iterdir():
            if f.is_file():
                f.unlink(missing_ok=True)


def _remove_runtime(runtime: Path) -> None:
    from wiremock_runtime import stop_wiremock

    stop_wiremock(runtime)
    if not runtime.exists():
        return

    def _on_rm_error(func, path, exc_info):
        exc = exc_info[1]
        winerr = getattr(exc, "winerror", None)
        if winerr == 32 or getattr(exc, "errno", None) in (errno.EACCES, 13, 32):
            if os.path.basename(path) == "wiremock.log":
                return
        raise exc

    try:
        shutil.rmtree(runtime, onerror=_on_rm_error)
    except OSError:
        _clear_mappings_and_files(runtime)
        for f in runtime.iterdir():
            if f.is_file() and f.name not in ("wiremock.log", ".wiremock.pid"):
                f.unlink(missing_ok=True)


def _copy_stub_tree(src: Path, mappings: Path, files: Path) -> None:
    for sub, dest in (("mappings", mappings), ("__files", files)):
        s = src / sub
        if not s.is_dir():
            continue
        for f in s.iterdir():
            if f.is_file():
                shutil.copy2(f, dest / f.name)


def apply_scenario_wiremock(
    ticket_dir: Path, scenario_id: str, stub_refs: list, port: int
) -> Path:
    """Rebuild WireMock runtime: ticket stubs + optional stubs/scenarios/<id>/."""
    runtime = wiremock_runtime_dir() / ticket_dir.name
    if runtime.exists():
        _remove_runtime(runtime)
    mappings = runtime / "mappings"
    files = runtime / "__files"
    mappings.mkdir(parents=True, exist_ok=True)
    files.mkdir(parents=True, exist_ok=True)

    ticket_stubs = ticket_dir / "stubs"
    if ticket_stubs.is_dir():
        _copy_stub_tree(ticket_stubs, mappings, files)

    sc_dir = ticket_dir / "stubs" / "scenarios" / scenario_id
    if sc_dir.is_dir():
        _copy_stub_tree(sc_dir, mappings, files)

    for ref in stub_refs or []:
        if isinstance(ref, dict):
            ref = ref.get("ref", "")
        if not ref:
            continue
        op_base, fix = resolve_fixture(ref)
        wm = fix.get("wiremock") or {}
        req = wm.get("request") or {}
        resp = wm.get("response") or {}
        body_file = resp.get("bodyFile")
        if body_file:
            src = op_base / "__files" / body_file
            if src.exists():
                shutil.copy2(src, files / body_file)
        mapping = {
            "request": {
                "method": req.get("method", "POST"),
                "urlPath": req.get("urlPath", f"/stub/{ref.replace('/', '-')}"),
            },
            "response": {
                "status": resp.get("status", 200),
                "headers": resp.get("headers", {"Content-Type": "text/xml;charset=utf-8"}),
            },
        }
        if body_file:
            mapping["response"]["bodyFileName"] = body_file
        elif "body" in resp:
            mapping["response"]["body"] = resp["body"]
        safe = ref.replace("/", "-")
        (mappings / f"{safe}.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")

    os.environ["WIREMOCK_ROOT"] = str(runtime)
    os.environ["WIREMOCK_PORT"] = str(port)
    return runtime


def apply_registry_stubs(ticket_dir: Path, stub_refs: list, port: int) -> Path:
    return apply_scenario_wiremock(ticket_dir, "_boot", stub_refs, port)


def write_masterdata_sql(ticket_dir: Path, spec: dict, port: int) -> Path:
    lines = [
        "USE dsa_masterdata;",
        "",
    ]
    refs = spec.get("stubs") or []
    seen_keys: set[str] = set()
    for row in spec.get("masterdata") or []:
        key = row["prop_key"]
        val = str(row.get("prop_value", "")).replace("{WIREMOCK_PORT}", str(port))
        seen_keys.add(key)
        lines += _insert_configuration(key, val)
    for ref in refs:
        if isinstance(ref, dict):
            ref = ref.get("ref", "")
        if not ref:
            continue
        _, fix = resolve_fixture(ref)
        key = fix.get("masterdata_prop_key")
        if key and key not in seen_keys:
            url_path = (fix.get("wiremock") or {}).get("request", {}).get("urlPath", "")
            val = f"http://localhost:{port}{url_path}"
            lines += _insert_configuration(key, val)
            seen_keys.add(key)
    out = ticket_dir / "masterdata-stub-urls.sql"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def apply_masterdata_sql(sql_path: Path, spec: dict) -> tuple[bool, str]:
    """Apply masterdata-stub-urls.sql so CC reads WireMock URLs (no manual SQL step)."""
    if not sql_path.is_file():
        return False, f"missing {sql_path}"
    env = spec.get("_env") or {}
    schemas = (env.get("mysql") or {}).get("schemas") or {}
    schema = schemas.get("masterdata") or "dsa_masterdata"
    from mysql_runner import mysql_exec_script

    rc, out = mysql_exec_script(sql_path.read_text(encoding="utf-8"), schema=schema)
    if rc != 0:
        return False, (out or "mysql failed")[-500:]
    cleared, clear_msg = clear_cc_config_cache(spec)
    if cleared:
        return True, f"applied {sql_path.name} -> {schema}; {clear_msg}"
    return True, f"applied {sql_path.name} -> {schema}"


def _tenant_redis_db_index(tenant: str) -> int:
    """Resolve tenant redis DB index (dsa=2) from platform_master.tenant_master."""
    from mysql_runner import mysql_query

    rc, out = mysql_query(
        f"SELECT redis_db_index FROM tenant_master WHERE code='{tenant}' LIMIT 1",
        schema="platform_master",
    )
    if rc != 0:
        return int(os.environ.get("TENANT_REDIS_DB", "0"))
    for line in (out or "").splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return int(os.environ.get("TENANT_REDIS_DB", "0"))


def _jdk_serialize_string(value: str) -> bytes:
    """Serialize as JDK String (matches Spring RedisTemplate default serializer)."""
    payload = value.encode("utf-8")
    if len(payload) > 65535:
        raise ValueError("config value too long for JDK UTF serialization")
    return bytes([0xAC, 0xED, 0x00, 0x05, 0x74]) + len(payload).to_bytes(2, "big") + payload


def _cc_config_redis_key(tenant: str, prop_key: str, service: str = "CREDIT-CARD-MANAGEMENT") -> str:
    """Match RedisCacheClient.getTenantSpecificKey(env + tenant + '_' + logicalKey)."""
    env = os.environ.get("NOVOPAY_SERVICE_ENV", "dev").strip().lower() or "dev"
    logical = f"config_{service}_{prop_key}"
    return f"{env}_{tenant}_{logical}"


def prime_cc_config_cache(spec: dict, port: int) -> tuple[bool, str]:
    """Seed Redis NovopayConfig keys so CC uses WireMock URLs without masterdata UP."""
    import subprocess

    tenant = os.environ.get("TENANT", "dsa").strip() or "dsa"
    service = "CREDIT-CARD-MANAGEMENT"
    host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = os.environ.get("REDIS_PORT", "6379")
    redis_db = _tenant_redis_db_index(tenant)
    rows: list[tuple[str, str]] = []
    for row in spec.get("masterdata") or []:
        key = str(row.get("prop_key", "")).strip()
        if not key:
            continue
        val = str(row.get("prop_value", "")).replace("{WIREMOCK_PORT}", str(port))
        rows.append((key, val))
    if not rows:
        return False, "no masterdata rows to prime"
    primed = 0
    for cli in ("redis-cli", "/usr/bin/redis-cli"):
        try:
            for prop_key, prop_val in rows:
                cache_key = _cc_config_redis_key(tenant, prop_key, service)
                payload = _jdk_serialize_string(prop_val)
                r = subprocess.run(
                    [cli, "-h", host, "-p", redis_port, "-n", str(redis_db), "-x", "SET", cache_key],
                    input=payload,
                    capture_output=True,
                    timeout=5,
                )
                if r.returncode == 0:
                    primed += 1
            if primed:
                return True, (
                    f"primed {primed} redis config key(s) db={redis_db} (JDK-serialized) "
                    f"({_cc_config_redis_key(tenant, rows[0][0], service)}…)"
                )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
    return False, "redis-cli unavailable (skipped config prime)"


def clear_cc_config_cache(spec: dict) -> tuple[bool, str]:
    """Drop stale Redis NovopayConfig entries so CC re-fetches from masterdata."""
    import subprocess

    tenant = os.environ.get("TENANT", "dsa").strip() or "dsa"
    service = "CREDIT-CARD-MANAGEMENT"
    env = os.environ.get("NOVOPAY_SERVICE_ENV", "dev").strip().lower() or "dev"
    pattern = f"{env}_{tenant}_config_{service}_*"
    host = os.environ.get("REDIS_HOST", "localhost")
    port = os.environ.get("REDIS_PORT", "6379")
    redis_db = _tenant_redis_db_index(tenant)
    for cli in ("redis-cli", "/usr/bin/redis-cli"):
        try:
            r = subprocess.run(
                [cli, "-h", host, "-p", port, "-n", str(redis_db), "--scan", "--pattern", pattern],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if r.returncode != 0:
                continue
            keys = [k for k in (r.stdout or "").splitlines() if k.strip()]
            if not keys:
                return True, "redis config cache already empty"
            deleted = 0
            for key in keys:
                dr = subprocess.run(
                    [cli, "-h", host, "-p", port, "-n", str(redis_db), "DEL", key],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if dr.returncode == 0:
                    deleted += 1
            return True, f"cleared {deleted} redis config key(s) for {service}"
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
    return False, "redis-cli unavailable (skipped cache clear)"


def _insert_configuration(key: str, val: str) -> list[str]:
    return [
        f"INSERT INTO configuration (service, prop_key, prop_value, is_deleted, created_on, updated_on, created_by, updated_by)",
        f"VALUES ('CREDIT-CARD-MANAGEMENT', '{key}', '{val}', 0, NOW(), NOW(), 'TDD_STUB', 'TDD_STUB')",
        "ON DUPLICATE KEY UPDATE prop_value=VALUES(prop_value), updated_on=NOW();",
        "",
    ]
