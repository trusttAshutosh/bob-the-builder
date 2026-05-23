from __future__ import annotations

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


def apply_registry_stubs(ticket_dir: Path, stub_refs: list, port: int) -> Path:
    runtime = wiremock_runtime_dir() / ticket_dir.name
    if runtime.exists():
        shutil.rmtree(runtime)
    mappings = runtime / "mappings"
    files = runtime / "__files"
    mappings.mkdir(parents=True)
    files.mkdir(parents=True)

    for ref in stub_refs:
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

    ticket_stubs = ticket_dir / "stubs"
    for sub in ("mappings", "__files"):
        s = ticket_stubs / sub
        if s.exists():
            for f in s.iterdir():
                if f.is_file():
                    shutil.copy2(f, (runtime / sub) / f.name)

    os.environ["WIREMOCK_ROOT"] = str(runtime)
    os.environ["WIREMOCK_PORT"] = str(port)
    return runtime


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


def _insert_configuration(key: str, val: str) -> list[str]:
    return [
        f"INSERT INTO configuration (service, prop_key, prop_value, is_deleted, created_on, updated_on, created_by, updated_by)",
        f"VALUES ('CREDIT-CARD-MANAGEMENT', '{key}', '{val}', 0, NOW(), NOW(), 'TDD_STUB', 'TDD_STUB')",
        "ON DUPLICATE KEY UPDATE prop_value=VALUES(prop_value), updated_on=NOW();",
        "",
    ]
