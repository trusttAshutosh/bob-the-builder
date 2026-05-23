"""Load deploy/tdd/workspace-services.yaml from host repo."""
from __future__ import annotations

from _yaml_util import load
from workspace import workspace_services_path


def load_workspace_services() -> dict:
    path = workspace_services_path()
    if not path.is_file():
        return {"services": {}}
    return load(path)


def workspace_service_entry(service_key: str) -> dict:
    data = load_workspace_services()
    services = data.get("services") or {}
    if service_key in services:
        return services[service_key]
    if "primary" in services:
        return services.get("primary") or {}
    return {}


def repo_dir_for_service(service_key: str) -> str:
    svc = workspace_service_entry(service_key)
    return str(svc.get("repo_dir") or "")
