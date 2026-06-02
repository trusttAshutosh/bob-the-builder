"""Host + workspace profile: CC/DSA defaults, deploy/tdd overrides, repo inference."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from _yaml_util import load
from host_repo import host_repo_name, host_repo_root
from workspace import workspace_root

_DEFAULTS_PATH = Path(__file__).resolve().parents[1] / "config" / "bob-defaults.yaml"
_ENV_VAR_SAFE = re.compile(r"[^A-Z0-9_]")


@lru_cache(maxsize=1)
def bob_defaults() -> dict[str, Any]:
    if _DEFAULTS_PATH.is_file():
        return dict(load(_DEFAULTS_PATH))
    return {
        "env_profile": "local-dsa",
        "primary_service": "credit_card_management",
        "primary_base_env_var": "CC_BASE",
        "primary_default_base": "http://localhost:8016/cc-mgmt",
        "gateway_v2_segment": "credit_card_management",
        "audit_schema": "dsa_credit_card_mgmt",
    }


def default_env_profile() -> str:
    return str(bob_defaults().get("env_profile") or "local-dsa")


def env_profile_name(spec: dict | None) -> str:
    if spec:
        return str(spec.get("env_profile") or default_env_profile()).strip()
    return default_env_profile()


def env_block(spec: dict | None = None) -> dict[str, Any]:
    if spec and spec.get("_env"):
        return dict(spec["_env"])
    return {}


def _base_env_var_for_service(service_key: str) -> str:
    d = bob_defaults()
    if service_key == d.get("primary_service"):
        return str(d.get("primary_base_env_var") or "CC_BASE")
    token = _ENV_VAR_SAFE.sub("_", service_key.upper())
    return f"{token}_BASE"


def infer_primary_service_key_from_host() -> str:
    from service_discovery import infer_service_config

    host = host_repo_root()
    if host.is_dir():
        return str(infer_service_config(host).get("service_key") or "")
    return ""


def primary_service_key(spec: dict | None = None) -> str:
    block = env_block(spec)
    if block.get("primary_service"):
        return str(block["primary_service"])
    inferred = infer_primary_service_key_from_host()
    if inferred:
        return inferred
    return str(bob_defaults().get("primary_service") or "credit_card_management")


def primary_service_entry(spec: dict | None = None) -> dict[str, Any]:
    key = primary_service_key(spec)
    block = env_block(spec)
    services = block.get("services") or {}
    if isinstance(services.get(key), dict):
        return dict(services[key])

    from service_discovery import infer_service_config

    host = host_repo_root()
    inferred: dict[str, Any] = {}
    if host.is_dir():
        inferred = infer_service_config(host, service_key=key)

    d = bob_defaults()
    return {
        "base_env_var": _base_env_var_for_service(key),
        "default_base": inferred.get("default_base")
        or (
            d.get("primary_default_base")
            if key == d.get("primary_service")
            else f"http://localhost:8080"
        ),
        "health_path": inferred.get("health_path") or "/actuator/health",
        "boot": inferred.get("boot") or {"task": "bootRun"},
    }


def primary_base_env_var(spec: dict | None = None) -> str:
    entry = primary_service_entry(spec)
    return str(entry.get("base_env_var") or _base_env_var_for_service(primary_service_key(spec)))


def primary_default_base(spec: dict | None = None) -> str:
    return str(primary_service_entry(spec).get("default_base") or "").rstrip("/")


def resolved_primary_base(spec: dict | None = None) -> str:
    var = primary_base_env_var(spec)
    env_val = os.environ.get(var, "").strip()
    if env_val:
        return env_val.rstrip("/")
    return primary_default_base(spec)


def gateway_v2_segment(spec: dict | None = None) -> str:
    block = env_block(spec)
    custom = block.get("gateway_v2_segment") or block.get("gateway_service")
    if custom:
        return str(custom)
    key = primary_service_key(spec)
    d = bob_defaults()
    if key == d.get("primary_service"):
        return str(d.get("gateway_v2_segment") or key)
    return key


def host_catalog_service_name() -> str:
    """API catalog `service` field (folder slug under novopay-platform-)."""
    name = host_repo_name()
    if name.startswith("novopay-platform-"):
        return name[len("novopay-platform-") :]
    return name


def audit_schema(spec: dict | None = None) -> str:
    if spec:
        run = spec.get("run") or {}
        if run.get("audit_db"):
            return str(run["audit_db"])
        schemas = (env_block(spec).get("mysql") or {}).get("schemas") or {}
        if schemas.get("audit"):
            return str(schemas["audit"])
    return str(bob_defaults().get("audit_schema") or "dsa_credit_card_mgmt")


def audit_table_defaults() -> dict[str, Any]:
    d = bob_defaults()
    return {
        "table": d.get("audit_table") or "transaction_audit",
        "crn_column": d.get("audit_crn_column") or "client_reference_code",
        "order_by": d.get("audit_order_by") or "updated_on DESC",
        "columns": list(d.get("audit_columns") or []),
    }


def effective_env_block(*, host: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    """Host deploy/tdd profile or synthesized block for setup / prompts."""
    host = host or host_repo_root()
    prof = profile or default_env_profile()
    from ticket_spec import load_env_profile_block

    block = load_env_profile_block(prof, base=host)
    if not block:
        block = synthesize_env_profile(prof, host=host)
    return block


@dataclass(frozen=True)
class ServiceBasePrompt:
    service_key: str
    base_env_var: str
    label: str
    default_base: str
    optional: bool = False


def _service_human_label(service_key: str) -> str:
    return service_key.replace("_", " ")


def service_base_prompts(
    *,
    host: Path | None = None,
    profile: str | None = None,
) -> list[ServiceBasePrompt]:
    """Ordered {SERVICE}_BASE prompts for bob setup from deploy/tdd + product defaults."""
    host = host or host_repo_root()
    block = effective_env_block(host=host, profile=profile)
    primary = str(block.get("primary_service") or bob_defaults().get("primary_service"))
    services: dict[str, Any] = dict(block.get("services") or {})
    out: list[ServiceBasePrompt] = []
    seen: set[str] = set()

    def append(key: str, cfg: dict[str, Any], *, optional: bool | None = None) -> None:
        var = str(cfg.get("base_env_var") or _base_env_var_for_service(key))
        if var in seen:
            return
        seen.add(var)
        default = str(cfg.get("default_base") or "").strip()
        if not default and key == bob_defaults().get("primary_service"):
            default = str(bob_defaults().get("primary_default_base") or "")
        is_opt = bool(cfg.get("optional")) if optional is None else optional
        out.append(
            ServiceBasePrompt(
                service_key=key,
                base_env_var=var,
                label=_service_human_label(key),
                default_base=default,
                optional=is_opt,
            )
        )

    if primary in services:
        append(primary, dict(services[primary]), optional=False)
    else:
        append(
            primary,
            {
                "base_env_var": _base_env_var_for_service(primary),
                "default_base": primary_service_entry({"_env": block}).get("default_base"),
            },
            optional=False,
        )

    for key, cfg in services.items():
        if key == primary:
            continue
        append(key, dict(cfg))

    for peer in bob_defaults().get("setup_optional_peers") or []:
        if not isinstance(peer, dict):
            continue
        var = str(peer.get("base_env_var") or "")
        if not var or var in seen:
            continue
        key = str(peer.get("service_key") or var.replace("_BASE", "").lower())
        append(
            key,
            {
                "base_env_var": var,
                "default_base": peer.get("default_base") or "",
                "optional": True,
            },
            optional=True,
        )

    return out


def service_base_env_vars(*, host: Path | None = None, profile: str | None = None) -> list[str]:
    return [p.base_env_var for p in service_base_prompts(host=host, profile=profile)]


def synthesize_env_profile(profile: str, *, host: Path | None = None) -> dict[str, Any]:
    """When host has no deploy/tdd/<profile>.yaml — infer primary + CC-shaped audit defaults."""
    host = host or host_repo_root()
    from service_discovery import infer_service_config
    from ticket_spec import load_env_profile_block

    block = load_env_profile_block(profile, base=host)
    if block:
        return block

    primary = infer_primary_service_key_from_host() or str(
        bob_defaults().get("primary_service") or "credit_card_management"
    )
    cfg = infer_service_config(host, service_key=primary) if host.is_dir() else {}
    d = bob_defaults()
    base_var = _base_env_var_for_service(primary)
    default_base = cfg.get("default_base") or (
        d.get("primary_default_base")
        if primary == d.get("primary_service")
        else f"http://localhost:8080"
    )
    audit = audit_table_defaults()
    return {
        "header_profile": "dsa-agent-app",
        "primary_service": primary,
        "gateway_v2_segment": primary.replace("-", "_"),
        "services": {
            primary: {
                "base_env_var": base_var,
                "default_base": default_base,
                "health_path": cfg.get("health_path") or "/actuator/health",
                "boot": cfg.get("boot") or {"task": "bootRun"},
            }
        },
        "mysql": {"schemas": {"audit": audit_schema(None)}},
        "audit": audit,
        "_synthesized": True,
        "_profile": profile,
    }


def discover_api_catalog_fields(spec: dict | None = None) -> dict[str, str]:
    """Fields for new api-catalog skeletons from discover-apis."""
    base_env = primary_base_env_var(spec)
    return {
        "service": host_catalog_service_name(),
        "base_env": base_env,
        "default_base": primary_default_base(spec) or str(
            bob_defaults().get("primary_default_base") or ""
        ),
        "gateway_v2_segment": gateway_v2_segment(spec),
    }


def example_host_repo_name() -> str:
    return str(bob_defaults().get("example_host_repo") or host_repo_name())


def print_host_summary() -> None:
    host = host_repo_root()
    ws = workspace_root()
    d = bob_defaults()
    print("Bob host profile")
    print(f"  BOB_HOST_REPO:     {host}")
    print(f"  BUILDER_WORKSPACE_ROOT: {ws or '(unset — run bob setup)'}")
    print(f"  Product defaults:  primary={d.get('primary_service')} env={d.get('env_profile')} base_var={d.get('primary_base_env_var')}")
    print(f"  Inferred primary:  {infer_primary_service_key_from_host() or '(n/a)'}")
    print(f"  Catalog service:   {host_catalog_service_name()}")
    from ticket_spec import env_profile_path

    prof = default_env_profile()
    ep = env_profile_path(prof, base=host)
    if ep:
        print(f"  deploy/tdd profile: {ep.name} ({ep.parent})")
    else:
        print(f"  deploy/tdd profile: (missing env-{prof}.yaml — using synthesized + bob-defaults)")
    repos = []
    if ws:
        from service_discovery import list_workspace_repos

        repos = [p.name for p in list_workspace_repos()]
    if repos:
        print(f"  Workspace repos ({len(repos)}): {', '.join(repos[:8])}{'...' if len(repos) > 8 else ''}")
