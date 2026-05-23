#!/usr/bin/env python3
"""
Generic TDD engine: API catalog, WireMock stubs per ticket, scenario execution.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


def _repo() -> Path:
    from _yaml_util import host_repo_root

    return host_repo_root()


def _tdd_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _catalog_dir() -> Path:
    from bob_home import api_catalog_dir

    return api_catalog_dir()


def _load_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if yaml:
        return yaml.safe_load(text) or {}
    raise RuntimeError("PyYAML required: pip install pyyaml")


def _dump_yaml(path: Path, data: dict) -> None:
    if not yaml:
        raise RuntimeError("PyYAML required")
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def _subst(obj: Any, vars_map: dict[str, str]) -> Any:
    if isinstance(obj, dict):
        return {k: _subst(v, vars_map) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_subst(x, vars_map) for x in obj]
    if isinstance(obj, str):
        out = obj
        for key, val in vars_map.items():
            out = out.replace("{" + key + "}", val)
        return out
    return obj


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_api(api_id: str) -> dict:
    apis_dir = _catalog_dir() / "apis"
    path = apis_dir / f"{api_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"API not in catalog: {api_id}. Run: bob discover-apis")
    return _load_yaml(path)


def default_vars() -> dict[str, str]:
    return {
        "TENANT": os.environ.get("TENANT", "dsa"),
        "CLIENT": os.environ.get("CLIENT", "dsa_agent_app"),
        "CRN": os.environ.get("CRN", f"TDD{int(time.time())}"),
        "MOBILE": os.environ.get("MOBILE", "9999999999"),
        "DOB": os.environ.get("DOB", "1990-01-15"),
        "AAN": os.environ.get("AAN", "0000000000000000001"),
        "STAN": os.environ.get("STAN", str(int(time.time() * 1000))),
    }


def _header_defaults(api: dict, spec_env: dict | None = None) -> dict:
    profile_id = "dsa-agent-app"
    if spec_env:
        profile_id = spec_env.get("header_profile", profile_id)
    prof_path = _tdd_root() / "config/header-profiles" / f"{profile_id}.yaml"
    if prof_path.exists() and yaml:
        prof = _load_yaml(prof_path)
        return prof.get("headers") or {}
    return api.get("header_defaults") or {}


def load_ticket_data(ticket_dir: Path) -> dict:
    try:
        from ticket_spec import load_spec

        return load_spec(ticket_dir)
    except Exception as e:
        raise FileNotFoundError(f"ticket-spec.yaml required in {ticket_dir}") from e


def build_request_body(
    api_id: str,
    step_vars: dict | None = None,
    overrides: dict | None = None,
    spec_env: dict | None = None,
) -> tuple[str, dict]:
    api = load_api(api_id)
    vars_map = {**default_vars(), **(step_vars or {})}
    vars_map["STAN"] = str(int(time.time() * 1000))

    headers = _subst(_header_defaults(api, spec_env), vars_map)
    api_headers = _subst(api.get("header_defaults") or {}, vars_map)
    headers = {**headers, **api_headers}
    request_body = _subst(api.get("request_defaults") or {}, vars_map)

    ov = overrides or {}
    if "headers" in ov:
        headers = _deep_merge(headers, _subst(ov["headers"], vars_map))
    if "request" in ov:
        request_body = _deep_merge(request_body, _subst(ov["request"], vars_map))

    key = api["envelope"]["request_key"]
    payload = {"headers": headers, "request": {key: request_body}}
    return key, payload


def resolve_url(api_id: str) -> str:
    api = load_api(api_id)
    base_env = api["http"].get("base_env", "CC_BASE")
    base = os.environ.get(base_env, "http://localhost:8016/cc-mgmt").rstrip("/")
    path = api["http"]["path"]
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def discover_apis() -> int:
    from bob_home import ensure_bob_home

    home = ensure_bob_home()
    print(f"API catalog → {home / 'api-catalog'}")
    if not yaml:
        print("Install PyYAML: pip install pyyaml", file=sys.stderr)
        return 1
    repo = _repo()
    orch_dir = repo / "deploy/application/orchestration"
    apis_dir = _catalog_dir() / "apis"
    apis_dir.mkdir(parents=True, exist_ok=True)
    names: set[str] = set()
    for xml in orch_dir.rglob("*.xml"):
        text = xml.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'<Request\s+name="([^"]+)"', text):
            names.add(m.group(1))

    created = 0
    index: dict[str, str] = {}
    for name in sorted(names):
        path = apis_dir / f"{name}.yaml"
        index[name] = f"apis/{name}.yaml"
        if path.exists():
            continue
        tpl = repo / f"deploy/application/templates/request/product/{name}_requestTemplate.json"
        req_defaults: dict = {}
        if tpl.exists():
            tpl_data = json.loads(tpl.read_text(encoding="utf-8"))
            inner = tpl_data.get(name, {})
            for field in inner:
                if field in ("client_reference_code", "mobile_no", "dob", "aan", "stan"):
                    req_defaults[field] = "{" + field.upper() + "}"
                else:
                    req_defaults[field] = ""

        skeleton = {
            "api_id": name,
            "service": "credit-card-management",
            "source": {"orchestration": str(xml.relative_to(repo)).replace("\\", "/")},
            "http": {
                "method": "POST",
                "path": f"/api/v1/{name}",
                "base_env": "CC_BASE",
            },
            "envelope": {"request_key": name},
            "header_defaults": {
                "tenant_code": "{TENANT}",
                "client_code": "{CLIENT}",
                "channel_code": "WEB",
                "function_code": "DEFAULT",
                "function_sub_code": "DEFAULT",
                "run_mode": "REAL",
                "user_id": "LOCAL_QA",
                "stan": "{STAN}",
            },
            "request_defaults": req_defaults or {"client_reference_code": "{CRN}"},
            "notes": "Auto-discovered — fill request_defaults and bank_calls for your ticket.",
        }
        if tpl.exists():
            skeleton["source"]["request_template"] = str(tpl.relative_to(repo)).replace("\\", "/")
        _dump_yaml(path, skeleton)
        created += 1
        print(f"  + catalog: {name}")

    _dump_yaml(_catalog_dir() / "index.yaml", {"apis": index, "updated": time.strftime("%Y-%m-%dT%H:%M:%S")})
    print(f"Discover done: {len(names)} APIs, {created} new skeleton(s)")
    print("  CC reference (optional): assets/examples/novopay-cc/")
    return 0


def apply_stubs(ticket_dir: Path, profile: str | None, port: int) -> Path:
    """Merge stub profile + ticket stubs into runtime WireMock root."""
    from bob_home import wiremock_runtime_dir

    runtime = wiremock_runtime_dir() / ticket_dir.name
    if runtime.exists():
        shutil.rmtree(runtime)
    mappings = runtime / "mappings"
    files = runtime / "__files"
    mappings.mkdir(parents=True)
    files.mkdir(parents=True)

    def copy_tree(src: Path) -> None:
        if not src.exists():
            return
        for sub in ("mappings", "__files"):
            s = src / sub
            if not s.exists():
                continue
            d = runtime / sub
            for f in s.iterdir():
                dest = d / f.name
                if f.is_file():
                    shutil.copy2(f, dest)

    if profile:
        prof = _tdd_root() / "stub-profiles" / profile
        copy_tree(prof)
    ticket_stubs = ticket_dir / "stubs"
    copy_tree(ticket_stubs)

    # Generate mappings from stub-spec.yaml
    spec = ticket_dir / "stub-spec.yaml"
    if spec.exists() and yaml:
        data = _load_yaml(spec)
        for i, stub in enumerate(data.get("stubs") or []):
            sid = stub.get("id", f"generated-{i}")
            req = stub.get("request") or {}
            resp = stub.get("response") or {}
            mapping = {
                "request": {
                    "method": req.get("method", "POST"),
                    "urlPath": req.get("urlPath", req.get("path", f"/stub/{sid}")),
                },
                "response": {
                    "status": resp.get("status", 200),
                    "headers": resp.get("headers", {"Content-Type": "text/xml;charset=utf-8"}),
                },
            }
            if "bodyFile" in resp:
                bf = resp["bodyFile"]
                src = ticket_stubs / "__files" / bf
                if src.exists():
                    shutil.copy2(src, files / bf)
                mapping["response"]["bodyFileName"] = bf
            elif "body" in resp:
                mapping["response"]["body"] = resp["body"]
            (mappings / f"{sid}.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")

    os.environ["WIREMOCK_PORT"] = str(port)
    os.environ["WIREMOCK_ROOT"] = str(runtime)
    return runtime


def write_masterdata_sql(ticket_dir: Path, port: int) -> Path:
    if not yaml:
        return ticket_dir / "masterdata-stub-urls.sql"
    data = load_ticket_data(ticket_dir)
    lines = [
        "USE dsa_masterdata;",
        "",
    ]
    for row in data.get("masterdata") or []:
        key = row["prop_key"]
        val = row.get("prop_value", "").replace("{WIREMOCK_PORT}", str(port))
        lines.append(
            f"INSERT INTO configuration (service, prop_key, prop_value, is_deleted, created_on, updated_on, created_by, updated_by)"
        )
        lines.append(
            f"VALUES ('CREDIT-CARD-MANAGEMENT', '{key}', '{val}', 0, NOW(), NOW(), 'TDD_STUB', 'TDD_STUB')"
        )
        lines.append("ON DUPLICATE KEY UPDATE prop_value=VALUES(prop_value), updated_on=NOW();")
    out = ticket_dir / "masterdata-stub-urls.sql"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def execute_scenarios(ticket_dir: Path) -> int:
    if not yaml:
        print("PyYAML required", file=sys.stderr)
        return 1
    data = load_ticket_data(ticket_dir)
    spec_env = data.get("_env") or {}
    if not spec_env and data.get("env_profile"):
        ep = _repo() / "deploy/tdd" / f"{data['env_profile']}.yaml"
        if ep.exists():
            spec_env = _load_yaml(ep)
    rc = 0
    crn = os.environ.get("CRN", default_vars()["CRN"])
    os.environ["CRN"] = crn

    for scenario in data.get("scenarios") or []:
        sid = scenario.get("id", "?")
        print(f"\n=== Scenario {sid} ===")
        steps = scenario.get("steps")
        if not steps:
            # single api.gateway in step
            gw = (scenario.get("api") or {}).get("gateway")
            if gw:
                steps = [{"api_id": gw, "overrides": scenario.get("overrides") or {}}]
        for step in steps:
            api_id = step.get("api_id") or step.get("api")
            if not api_id:
                continue
            overrides = step.get("overrides") or {}
            step_vars = step.get("vars") or {}
            if isinstance(step_vars, dict):
                step_vars = {k: str(v) for k, v in _subst(step_vars, {**default_vars(), "CRN": crn}).items()}
            url = resolve_url(api_id)
            _, body = build_request_body(api_id, step_vars, overrides, spec_env)
            print(f">> POST {api_id} -> {url}")
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    text = resp.read().decode("utf-8", errors="replace")
                    out = ticket_dir / f"responses/{api_id}-last.json"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(text, encoding="utf-8")
                    ev = ticket_dir / "evidence/api" / f"{api_id}-last.json"
                    ev.parent.mkdir(parents=True, exist_ok=True)
                    ev.write_text(text, encoding="utf-8")
                    print(f"   HTTP {resp.status} (saved {out.relative_to(ticket_dir)})")
            except urllib.error.HTTPError as e:
                text = e.read().decode("utf-8", errors="replace")
                print(f"   HTTP {e.code}: {text[:500]}")
                rc = 1
            except Exception as e:
                print(f"   ERROR: {e}")
                rc = 1
            time.sleep(1)
    print(f"\nCRN={crn}")
    return rc


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: tdd_engine.py discover|build-request|resolve-url|apply-stubs|masterdata-sql|execute <args>")
        return 1
    cmd = sys.argv[1]
    if cmd == "discover":
        return discover_apis()
    if cmd == "build-request":
        api_id = sys.argv[2]
        _, body = build_request_body(api_id)
        print(json.dumps(body, indent=2))
        return 0
    if cmd == "resolve-url":
        print(resolve_url(sys.argv[2]))
        return 0
    if cmd == "apply-stubs":
        ticket = Path(sys.argv[2])
        profile = None
        port = 9090
        rest = sys.argv[3:]
        if rest and not str(rest[0]).isdigit():
            profile = rest[0] or None
            port = int(rest[1]) if len(rest) > 1 else 9090
        elif rest:
            port = int(rest[0])
        root = apply_stubs(ticket, profile, port)
        print(root)
        write_masterdata_sql(ticket, port)
        return 0
    if cmd == "execute":
        return execute_scenarios(Path(sys.argv[2]))
    print(f"Unknown command: {cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
