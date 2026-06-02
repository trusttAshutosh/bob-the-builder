"""Generate Postman Collection v2.1 for a Bob ticket (prerequisites + APIs under test)."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from ticket_spec import scenarios

_TDD_ROOT = Path(__file__).resolve().parents[1]
_DEFAULTS_PATH = _TDD_ROOT / "config" / "postman-url-defaults.yaml"
_VERSION_RE = re.compile(r"^/api/(v\d+)/", re.IGNORECASE)


def _load_yaml(path: Path) -> dict:
    import yaml

    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _load_postman_url_defaults(spec: dict) -> dict:
    defaults = _load_yaml(_DEFAULTS_PATH)
    try:
        from _yaml_util import host_repo_root

        host_path = host_repo_root() / "deploy/tdd/postman-urls.yaml"
        if host_path.exists():
            defaults = _deep_merge(defaults, _load_yaml(host_path))
    except Exception:
        pass
    run = spec.get("run") or {}
    custom = run.get("postman") or spec.get("postman") or {}
    if custom:
        merged = _deep_merge(defaults, custom)
        envs = dict(merged.get("environments") or {})
        for env_name in ("local", "qa", "uat"):
            gw = custom.get(f"{env_name}_gateway_base")
            svc = custom.get(f"{env_name}_service_base")
            if gw or svc:
                block = dict(envs.get(env_name) or {})
                if gw:
                    block["gateway_base"] = gw
                if svc:
                    block["service_base"] = svc
                envs[env_name] = block
        merged["environments"] = envs
        for key in ("wiremock_base", "gateway_path", "request_vars", "feature_defaults"):
            if key in custom:
                merged[key] = custom[key]
        return merged
    return defaults


def _postman_cfg(spec: dict, wiremock_port: int) -> dict[str, Any]:
    run = spec.get("run") or {}
    custom = run.get("postman") or spec.get("postman") or {}
    defaults = _load_postman_url_defaults(spec)
    from host_profile import gateway_v2_segment, primary_service_entry

    svc = primary_service_entry(spec)

    wiremock = (
        custom.get("wiremock_base")
        or defaults.get("wiremock_base")
        or f"http://127.0.0.1:{wiremock_port}"
    ).rstrip("/")

    local_svc = (
        (defaults.get("environments") or {}).get("local", {}).get("service_base")
        or custom.get("service_direct")
        or svc.get("default_base")
        or svc.get("default_base")
        or ""
    ).rstrip("/")

    env_defaults = defaults.get("environments") or {}
    environments: dict[str, dict[str, str]] = {}
    for env_name in ("local", "qa", "uat"):
        block = dict(env_defaults.get(env_name) or {})
        if env_name == "local":
            block.setdefault("service_base", local_svc)
        gw_flat = custom.get(f"{env_name}_gateway_base")
        if gw_flat:
            block["gateway_base"] = gw_flat.rstrip("/")
        if block.get("gateway_base"):
            block["gateway_base"] = str(block["gateway_base"]).rstrip("/")
        if block.get("service_base"):
            block["service_base"] = str(block["service_base"]).rstrip("/")
        if block:
            block.setdefault("wiremock", wiremock)
            environments[env_name] = block

    v2_seg = gateway_v2_segment(spec)
    gateway_path = defaults.get("gateway_path") or {
        "v1": "/api/novopay/v1",
        "v2": f"/api/v2/{v2_seg}",
    }
    req_vars = dict(defaults.get("request_vars") or {})
    req_vars.setdefault("TENANT", "dsa")
    req_vars.setdefault("CLIENT", "dsa_agent_app")
    req_vars.setdefault("MOBILE", "9999999999")
    req_vars.setdefault("DOB", "15-01-1990")
    req_vars.setdefault("AAN", "0000000000000000001")

    return {
        "service_direct": local_svc,
        "wiremock": wiremock,
        "environments": environments,
        "gateway_path": gateway_path,
        "request_vars": req_vars,
        "feature_defaults": defaults.get("feature_defaults") or {},
    }


def _api_http_version(api_id: str) -> str:
    import tdd_engine

    api = tdd_engine.load_api(api_id)
    path = str((api.get("http") or {}).get("path") or "")
    match = _VERSION_RE.match(path)
    if match:
        return match.group(1).lower()
    return "v1"


def _apis_grouped_by_version(api_ids: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for api_id in api_ids:
        ver = _api_http_version(api_id)
        grouped.setdefault(ver, []).append(api_id)
    return grouped


def _test_api_ids(spec: dict) -> list[str]:
    impacted = spec.get("impacted") or {}
    apis: list[str] = list(impacted.get("gateway_apis") or [])
    if not apis:
        for sc in scenarios(spec):
            for step in sc.get("steps") or []:
                aid = step.get("api_id") or step.get("api")
                if aid and aid not in apis:
                    apis.append(aid)
    return apis


def _prerequisite_api_ids(spec: dict, test_apis: list[str]) -> list[str]:
    run = spec.get("run") or {}
    postman = run.get("postman") or spec.get("postman") or {}
    impacted = spec.get("impacted") or {}

    explicit = postman.get("prerequisite_apis")
    if explicit is None:
        explicit = impacted.get("prerequisite_apis")
    if explicit is None:
        feature = impacted.get("feature") or ""
        defaults = _load_postman_url_defaults(spec)
        feature_defaults = (defaults.get("feature_defaults") or {}).get(feature) or {}
        explicit = feature_defaults.get("prerequisite_apis")

    if explicit is not None:
        return [a for a in explicit if a and a not in test_apis]

    loc_apis = {"getLOCOffers", "submitLoanOnCards", "createOrUpdateLoanTransaction"}
    if loc_apis.intersection(test_apis) and "manageLOCTransactionAudit" not in test_apis:
        return ["manageLOCTransactionAudit"]
    return []


def _pm_item(name: str, request: dict, description: str = "") -> dict:
    item: dict[str, Any] = {"name": name, "request": request}
    if description:
        item["description"] = description
    return item


def _postman_placeholder_vars() -> dict[str, str]:
    return {
        "TENANT": "{{TENANT}}",
        "CLIENT": "{{CLIENT}}",
        "CRN": "{{CRN}}",
        "CLIENT_REFERENCE_CODE": "{{CRN}}",
        "MOBILE": "{{MOBILE}}",
        "MOBILE_NO": "{{MOBILE}}",
        "DOB": "{{DOB}}",
        "AAN": "{{AAN}}",
        "STAN": "{{STAN}}",
    }


def _build_service_body(api_id: str, spec_env: dict | None) -> dict:
    import tdd_engine

    _, payload = tdd_engine.build_request_body(
        api_id, _postman_placeholder_vars(), spec_env=spec_env
    )
    headers = payload.get("headers") or {}
    if isinstance(headers, dict):
        headers["stan"] = "{{STAN}}"
        headers["transmission_datetime"] = "{{STAN}}"
        payload["headers"] = headers
    req = payload.get("request") or {}
    if isinstance(req, dict):
        for field in ("client_reference_code", "mobile_no", "dob", "aan"):
            if field in req:
                key = "CRN" if field == "client_reference_code" else field.upper()
                if field == "mobile_no":
                    key = "MOBILE"
                req[field] = f"{{{{{key}}}}}"
        payload["request"] = req
    return payload


def _service_path(mode: str, api_version: str, api_id: str, gateway_path: dict) -> str:
    if mode == "with-gateway":
        prefix = gateway_path.get(api_version) or f"/api/{api_version}"
        if not prefix.startswith("/"):
            prefix = "/" + prefix
        return f"{prefix}/{api_id}"
    return f"/api/{api_version}/{api_id}"


def _service_request(
    api_id: str,
    base_var: str,
    mode: str,
    api_version: str,
    body_payload: dict,
    gateway_path: dict,
    *,
    folder_role: str,
) -> dict:
    path = _service_path(mode, api_version, api_id, gateway_path)
    path_segments = [p for p in path.strip("/").split("/") if p]
    return {
        "method": "POST",
        "header": [{"key": "Content-Type", "value": "application/json"}],
        "body": {
            "mode": "raw",
            "raw": json.dumps(body_payload, indent=2),
        },
        "url": {
            "raw": f"{{{{{base_var}}}}}{path}",
            "host": [f"{{{{{base_var}}}}}"],
            "path": path_segments,
        },
        "description": (
            f"CC `{api_id}` ({api_version}, {mode}). "
            f"Uses shared `{{{{CRN}}}}` - run **prerequisites** first if you see 4000028."
        ),
    }


def _api_items(
    api_ids: list[str],
    base_var: str,
    mode: str,
    api_version: str,
    spec_env: dict | None,
    gateway_path: dict,
    *,
    folder_role: str,
) -> list[dict]:
    items: list[dict] = []
    for api_id in api_ids:
        if _api_http_version(api_id) != api_version:
            continue
        body = _build_service_body(api_id, spec_env)
        req = _service_request(
            api_id,
            base_var,
            mode,
            api_version,
            body,
            gateway_path,
            folder_role=folder_role,
        )
        note = ""
        if api_id == "manageLOCTransactionAudit":
            note = (
                "Creates `transaction_audit` for `{{CRN}}`. "
                "Run before getLOCOffers / submitLoanOnCards."
            )
        items.append(_pm_item(api_id, req, note))
    return items


def _bank_request(name: str, method: str, path: str, body_mode: str = "raw", body: str = "") -> dict:
    req: dict[str, Any] = {
        "method": method,
        "header": [],
        "url": {
            "raw": f"{{{{wiremock_base}}}}{path}",
            "host": ["{{wiremock_base}}"],
            "path": [p for p in path.strip("/").split("/") if p],
        },
        "description": f"HDFC bank stub (WireMock, local) — {name}.",
    }
    if body_mode == "xml":
        req["header"] = [{"key": "Content-Type", "value": "text/xml;charset=utf-8"}]
        req["body"] = {"mode": "raw", "raw": body or "<!-- paste SOAP/XML stub body -->"}
    else:
        req["header"] = [{"key": "Content-Type", "value": "application/json"}]
        req["body"] = {"mode": "raw", "raw": body or "{}"}
    return req


def _bank_items(spec: dict) -> list[dict]:
    impacted = spec.get("impacted") or {}
    ops = list(impacted.get("bank_operations") or [])
    masterdata = spec.get("masterdata") or []
    items: list[dict] = []
    path_by_op = {
        "getCardSummary": "/stub/card-summary",
        "inquireCreditCardProductEligibility": "/stub/product-eligibility",
    }
    for op in ops:
        path = path_by_op.get(op)
        if not path:
            for row in masterdata:
                key = str(row.get("prop_key") or "")
                if op.lower() in key.lower() or "card.summary" in key:
                    path = "/stub/card-summary"
                    break
                if "product.eligibility" in key:
                    path = "/stub/product-eligibility"
                    break
        if not path:
            path = f"/stub/{op}"
        items.append(
            _pm_item(
                op,
                _bank_request(op, "POST", path, body_mode="xml"),
                "Local WireMock only — point masterdata URLs at wiremock_base.",
            )
        )
    if not items:
        items = [
            _pm_item(
                "getCardSummary",
                _bank_request("getCardSummary", "POST", "/stub/card-summary", body_mode="xml"),
            ),
            _pm_item(
                "inquireCreditCardProductEligibility",
                _bank_request(
                    "inquireCreditCardProductEligibility",
                    "POST",
                    "/stub/product-eligibility",
                    body_mode="xml",
                ),
            ),
        ]
    return items


def _mode_folder(
    mode: str,
    env_name: str,
    api_version: str,
    *,
    prerequisite_apis: list[str],
    test_apis: list[str],
    bank_items: list[dict],
    spec_env: dict | None,
    gateway_path: dict,
    include_bank_stubs: bool,
) -> dict:
    base_var = f"{env_name}_gateway_base" if mode == "with-gateway" else f"{env_name}_service_base"
    prereq_children = _api_items(
        prerequisite_apis,
        base_var,
        mode,
        api_version,
        spec_env,
        gateway_path,
        folder_role="prerequisites",
    )
    if include_bank_stubs and bank_items:
        prereq_children.append(
            {
                "name": "bank-api (WireMock)",
                "description": "Optional local stubs; QA/UAT use real HDFC URLs from masterdata.",
                "item": bank_items,
            }
        )

    test_children = _api_items(
        test_apis,
        base_var,
        mode,
        api_version,
        spec_env,
        gateway_path,
        folder_role="apis-under-test",
    )

    return {
        "name": mode,
        "item": [
            {
                "name": "prerequisites",
                "description": (
                    "Run this folder first (Collection Runner: prerequisites → apis-under-test). "
                    "Creates data such as `transaction_audit` for `{{CRN}}`. "
                    "Skipping causes 4000028 (no transaction for reference number)."
                ),
                "item": prereq_children,
            },
            {
                "name": "apis-under-test",
                "description": (
                    "Feature APIs from ticket-spec `impacted.gateway_apis` / scenario steps. "
                    "Use the same `{{CRN}}` as prerequisites."
                ),
                "item": test_children,
            },
        ],
    }


def _env_folder(
    env_name: str,
    api_version: str,
    *,
    include_without_gateway: bool,
    prerequisite_apis: list[str],
    test_apis: list[str],
    bank_items: list[dict],
    spec_env: dict | None,
    gateway_path: dict,
) -> dict | None:
    ver_prereq = [a for a in prerequisite_apis if _api_http_version(a) == api_version]
    ver_test = [a for a in test_apis if _api_http_version(a) == api_version]
    if not ver_prereq and not ver_test:
        return None

    include_bank = env_name == "local"
    modes = [
        _mode_folder(
            "with-gateway",
            env_name,
            api_version,
            prerequisite_apis=ver_prereq,
            test_apis=ver_test,
            bank_items=bank_items,
            spec_env=spec_env,
            gateway_path=gateway_path,
            include_bank_stubs=include_bank,
        )
    ]
    if include_without_gateway:
        modes.append(
            _mode_folder(
                "without-gateway",
                env_name,
                api_version,
                prerequisite_apis=ver_prereq,
                test_apis=ver_test,
                bank_items=bank_items,
                spec_env=spec_env,
                gateway_path=gateway_path,
                include_bank_stubs=include_bank,
            )
        )
    return {"name": env_name, "item": modes}


def _version_roots(
    spec: dict,
    cfg: dict,
    *,
    prerequisite_apis: list[str],
    test_apis: list[str],
    bank_items: list[dict],
    spec_env: dict | None,
) -> list[dict]:
    all_apis = list(dict.fromkeys(prerequisite_apis + test_apis))
    versions = sorted(_apis_grouped_by_version(all_apis).keys())
    gateway_path = cfg["gateway_path"]
    roots: list[dict] = []

    for ver in versions:
        env_folders: list[dict] = []
        for env_name in ("local", "qa", "uat"):
            if env_name not in cfg["environments"]:
                continue
            folder = _env_folder(
                env_name,
                ver,
                include_without_gateway=(env_name == "local"),
                prerequisite_apis=prerequisite_apis,
                test_apis=test_apis,
                bank_items=bank_items,
                spec_env=spec_env,
                gateway_path=gateway_path,
            )
            if folder:
                env_folders.append(folder)
        if env_folders:
            roots.append({"name": ver, "item": env_folders})
    return roots


def _collection_variables(cfg: dict) -> list[dict]:
    crn_seed = f"TDD{int(time.time())}"
    req = cfg["request_vars"]
    vars_list: list[dict] = [
        {"key": "wiremock_base", "value": cfg["wiremock"], "type": "string"},
        {"key": "TENANT", "value": str(req.get("TENANT", "dsa")), "type": "string"},
        {"key": "CLIENT", "value": str(req.get("CLIENT", "dsa_agent_app")), "type": "string"},
        {"key": "CRN", "value": crn_seed, "type": "string"},
        {"key": "MOBILE", "value": str(req.get("MOBILE", "9999999999")), "type": "string"},
        {"key": "DOB", "value": str(req.get("DOB", "15-01-1990")), "type": "string"},
        {"key": "AAN", "value": str(req.get("AAN", "0000000000000000001")), "type": "string"},
        {"key": "STAN", "value": str(int(time.time() * 1000)), "type": "string"},
    ]
    for env_name in ("local", "qa", "uat"):
        block = cfg["environments"].get(env_name) or {}
        if env_name == "local":
            vars_list.append(
                {
                    "key": "local_service_base",
                    "value": block.get("service_base", cfg["service_direct"]),
                    "type": "string",
                }
            )
        gw = block.get("gateway_base")
        if gw:
            vars_list.append(
                {"key": f"{env_name}_gateway_base", "value": gw, "type": "string"}
            )
    return vars_list


def _environment_values(cfg: dict, env_name: str) -> list[dict]:
    crn_seed = f"TDD{int(time.time())}"
    req = cfg["request_vars"]
    block = cfg["environments"].get(env_name) or {}
    values: list[dict] = [
        {"key": "wiremock_base", "value": block.get("wiremock", cfg["wiremock"]), "enabled": True},
        {"key": "TENANT", "value": str(req.get("TENANT", "dsa")), "enabled": True},
        {"key": "CLIENT", "value": str(req.get("CLIENT", "dsa_agent_app")), "enabled": True},
        {"key": "CRN", "value": crn_seed, "enabled": True},
        {"key": "MOBILE", "value": str(req.get("MOBILE", "9999999999")), "enabled": True},
        {"key": "DOB", "value": str(req.get("DOB", "15-01-1990")), "enabled": True},
        {"key": "AAN", "value": str(req.get("AAN", "0000000000000000001")), "enabled": True},
        {"key": "STAN", "value": str(int(time.time() * 1000)), "enabled": True},
    ]
    if env_name == "local":
        values.append(
            {
                "key": "local_service_base",
                "value": block.get("service_base", cfg["service_direct"]),
                "enabled": True,
            }
        )
    for name in ("local", "qa", "uat"):
        gw = (cfg["environments"].get(name) or {}).get("gateway_base")
        if gw:
            values.append({"key": f"{name}_gateway_base", "value": gw, "enabled": True})
    return values


def build_postman_collection(
    spec: dict,
    ticket_dir: Path,
    *,
    wiremock_port: int = 9090,
) -> Path:
    """Write Postman collection + environment files under ticket_dir/postman/."""
    cfg = _postman_cfg(spec, wiremock_port)
    ticket = spec.get("ticket") or {}
    tid = ticket.get("id") or ticket_dir.name
    title = ticket.get("title") or tid
    test_apis = _test_api_ids(spec)
    prerequisite_apis = _prerequisite_api_ids(spec, test_apis)
    spec_env = spec.get("_env")
    bank_items = _bank_items(spec)

    version_roots = _version_roots(
        spec,
        cfg,
        prerequisite_apis=prerequisite_apis,
        test_apis=test_apis,
        bank_items=bank_items,
        spec_env=spec_env,
    )

    prereq_line = ", ".join(prerequisite_apis) if prerequisite_apis else "(none configured)"
    test_line = ", ".join(test_apis) if test_apis else "(none)"

    collection: dict[str, Any] = {
        "info": {
            "name": f"Bob — {title}",
            "description": (
                f"Generated by Bob validate-ticket for `{tid}`.\n\n"
                "## Test suite layout\n"
                "1. **prerequisites** — setup APIs (e.g. `manageLOCTransactionAudit` for `{{CRN}}`).\n"
                "2. **apis-under-test** — ticket feature APIs.\n\n"
                "Run **prerequisites** before **apis-under-test** (Postman Collection Runner on parent folder "
                "runs subfolders in order). Error **4000028** means no `transaction_audit` row for `{{CRN}}`.\n\n"
                f"- Prerequisites: {prereq_line}\n"
                f"- Under test: {test_line}\n"
                "- API version folders (`v1`, `v2`, …) are created only when at least one API uses that version.\n"
                "- **without-gateway** is local only (`local_service_base`).\n"
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": _collection_variables(cfg),
        "item": version_roots,
    }

    out_dir = ticket_dir / "postman"
    out_dir.mkdir(parents=True, exist_ok=True)
    coll_path = out_dir / f"{tid}.postman_collection.json"
    coll_path.write_text(json.dumps(collection, indent=2), encoding="utf-8")

    for env_name in cfg["environments"]:
        env_doc = {
            "name": f"Bob {tid} — {env_name}",
            "values": _environment_values(cfg, env_name),
        }
        (out_dir / f"{env_name}.postman_environment.json").write_text(
            json.dumps(env_doc, indent=2), encoding="utf-8"
        )

    return coll_path


def export_postman_for_ticket(
    spec: dict,
    ticket_dir: Path,
    wiremock_port: int = 9090,
) -> tuple[Path | None, str]:
    try:
        path = build_postman_collection(spec, ticket_dir, wiremock_port=wiremock_port)
        return path, f"Postman collection → {path}"
    except Exception as e:
        return None, f"Postman export failed: {e}"
