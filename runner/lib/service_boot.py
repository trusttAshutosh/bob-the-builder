"""Start/stop Gradle bootRun for workspace services (health-gated)."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from bob_home import bob_local_root
from host_repo import host_repo_root
from workspace import service_repo_path, workspace_root
from workspace_services import repo_dir_for_service, workspace_service_entry

from _yaml_util import load


def runtime_root() -> Path:
    p = bob_local_root() / ".runtime-services"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _service_dir(service_key: str) -> Path:
    p = runtime_root() / service_key
    p.mkdir(parents=True, exist_ok=True)
    return p


def _pid_file(service_key: str) -> Path:
    return _service_dir(service_key) / "boot.pid"


def _log_file(service_key: str) -> Path:
    return _service_dir(service_key) / "boot.log"


def _base_url(svc_cfg: dict) -> str:
    base_var = svc_cfg.get("base_env_var", "")
    env_base = os.environ.get(base_var, "").strip() if base_var else ""
    return (env_base or svc_cfg.get("default_base", "")).rstrip("/")


def health_up(svc_cfg: dict, *, timeout: float = 5) -> bool:
    base = _base_url(svc_cfg)
    if not base:
        return False
    health_path = svc_cfg.get("health_path", "/actuator/health")
    url = f"{base}{health_path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return False


def _gradle_boot_cmd(repo: Path, boot_cfg: dict) -> list[str]:
    task = boot_cfg.get("task", "bootRun")
    extra = boot_cfg.get("args") or []
    if sys.platform == "win32":
        wrapper = repo / "gradlew.bat"
        if not wrapper.is_file():
            wrapper = repo / "gradlew"
        return [str(wrapper), task, *extra]
    return [str(repo / "gradlew"), task, *extra]


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        r = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return str(pid) in (r.stdout or "")
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _kill_pid(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=30)
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (OSError, ProcessLookupError):
            try:
                os.kill(pid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                pass


def stop_service(service_key: str) -> str:
    pf = _pid_file(service_key)
    if not pf.is_file():
        return f"{service_key}: no pid file"
    try:
        pid = int(pf.read_text(encoding="utf-8").strip())
    except ValueError:
        pf.unlink(missing_ok=True)
        return f"{service_key}: invalid pid file"
    _kill_pid(pid)
    pf.unlink(missing_ok=True)
    return f"{service_key}: stopped (pid {pid})"


def stop_all() -> list[str]:
    lines: list[str] = []
    root = runtime_root()
    if root.is_dir():
        for d in sorted(root.iterdir()):
            if d.is_dir() and (d / "boot.pid").is_file():
                lines.append(stop_service(d.name))
    if not lines:
        lines.append("No Bob-started services running.")
    return lines


def _resolve_repo(service_key: str, svc_cfg: dict) -> Path | None:
    ws_key = svc_cfg.get("workspace_key") or service_key
    repo = service_repo_path(ws_key)
    if repo:
        return repo
    repo_dir = repo_dir_for_service(ws_key) or repo_dir_for_service(service_key)
    root = workspace_root()
    if root and repo_dir:
        p = root / repo_dir
        return p if p.is_dir() else None
    return None


def start_service(
    service_key: str,
    svc_cfg: dict,
    *,
    wait_seconds: int = 180,
    force: bool = False,
    repo: Path | None = None,
) -> tuple[bool, str]:
    if health_up(svc_cfg) and not force:
        return True, f"{service_key}: already UP ({_base_url(svc_cfg)})"

    if repo is None:
        repo = _resolve_repo(service_key, svc_cfg)
    if not repo:
        ws_key = svc_cfg.get("workspace_key") or service_key
        return False, f"{service_key}: repo not found (workspace key `{ws_key}` — edit deploy/tdd/workspace-services.yaml)"

    gradle = repo / ("gradlew.bat" if sys.platform == "win32" else "gradlew")
    if not gradle.is_file():
        return False, f"{service_key}: no Gradle wrapper in {repo}"

    pf = _pid_file(service_key)
    if pf.is_file():
        try:
            old = int(pf.read_text(encoding="utf-8").strip())
            if _process_alive(old):
                if health_up(svc_cfg):
                    return True, f"{service_key}: already running (pid {old})"
                stop_service(service_key)
        except ValueError:
            pf.unlink(missing_ok=True)

    boot_cfg = dict((workspace_service_entry(service_key) or {}).get("boot") or {})
    boot_cfg.update(svc_cfg.get("boot") or {})
    cmd = _gradle_boot_cmd(repo, boot_cfg)
    log = _log_file(service_key)
    boot_env = os.environ.copy()
    for k, v in (boot_cfg.get("env") or {}).items():
        boot_env[str(k)] = str(v)

    log.write_text(f"=== boot {service_key} ===\n{' '.join(cmd)}\n\n", encoding="utf-8")
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    with log.open("a", encoding="utf-8") as logfh:
        proc = subprocess.Popen(
            cmd,
            cwd=str(repo),
            stdout=logfh,
            stderr=subprocess.STDOUT,
            env=boot_env,
            creationflags=creationflags,
        )
    pf.write_text(str(proc.pid), encoding="utf-8")

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if health_up(svc_cfg, timeout=3):
            return True, f"{service_key}: UP ({_base_url(svc_cfg)}) pid={proc.pid} log={log}"
        if proc.poll() is not None:
            tail = log.read_text(encoding="utf-8", errors="replace")[-2000:]
            return False, f"{service_key}: bootRun exited {proc.returncode}\n{tail}"
        time.sleep(3)

    return False, f"{service_key}: timeout after {wait_seconds}s — see {log}"


def services_for_spec(spec: dict) -> list[str]:
    env_block = spec.get("_env") or {}
    services = env_block.get("services") or {}
    if not services:
        return []
    impacted_repos = set((spec.get("impacted") or {}).get("repos") or [])
    keys: list[str] = []
    for key, svc_cfg in services.items():
        if svc_cfg.get("optional") and not os.environ.get(svc_cfg.get("base_env_var", ""), "").strip():
            continue
        ws_key = svc_cfg.get("workspace_key") or key
        repo_dir = repo_dir_for_service(ws_key) or repo_dir_for_service(key)
        if impacted_repos and repo_dir and repo_dir not in impacted_repos:
            if key not in impacted_repos and ws_key not in impacted_repos:
                continue
        keys.append(key)
    primary = env_block.get("primary_service")
    if primary and primary in services and primary not in keys:
        keys.insert(0, primary)
    return keys


def boot_wait_seconds(spec: dict) -> int:
    run = spec.get("run") or {}
    return int(run.get("boot_wait_seconds", 180))


def auto_boot_enabled(spec: dict) -> bool:
    run = spec.get("run") or {}
    if "auto_boot_services" in run:
        return bool(run.get("auto_boot_services"))
    return True


def auto_discover_enabled(spec: dict) -> bool:
    run = spec.get("run") or {}
    if "auto_discover_services" in run:
        return bool(run.get("auto_discover_services"))
    return True


def ensure_services_running(spec: dict, *, force: bool = False) -> dict[str, tuple[bool, str]]:
    from service_discovery import discover_for_session

    wait = boot_wait_seconds(spec)
    outcomes: dict[str, tuple[bool, str]] = {}
    root = workspace_root()
    configs = discover_for_session(spec) if auto_discover_enabled(spec) else []
    if not auto_discover_enabled(spec):
        env_block = spec.get("_env") or {}
        for key in services_for_spec(spec):
            svc_cfg = (env_block.get("services") or {}).get(key) or {}
            ws_key = svc_cfg.get("workspace_key") or key
            rd = repo_dir_for_service(ws_key) or repo_dir_for_service(key)
            if root and rd and (root / rd).is_dir():
                from service_discovery import infer_service_config

                cfg = infer_service_config(root / rd, service_key=key)
                cfg.update(svc_cfg)
                configs.append(cfg)
    for cfg in configs:
        key = str(cfg.get("service_key") or cfg.get("repo_dir") or "service")
        svc_cfg = {
            k: cfg[k]
            for k in ("default_base", "health_path", "boot", "base_env_var", "optional", "workspace_key")
            if k in cfg
        }
        repo_path = None
        if root and cfg.get("repo_dir"):
            candidate = root / str(cfg["repo_dir"])
            if candidate.is_dir():
                repo_path = candidate
        outcomes[key] = start_service(
            key,
            svc_cfg,
            wait_seconds=wait,
            force=force,
            repo=repo_path,
        )
    return outcomes


def ensure_peers(
    spec: dict | None = None,
    *,
    wait_seconds: int = 180,
    force: bool = False,
) -> dict[str, tuple[bool, str]]:
    """Discover peers from code/properties/session and boot anything not healthy."""
    from service_discovery import discover_for_session, register_required_service

    spec = spec or {"run": {"boot_wait_seconds": wait_seconds}, "impacted": {}}
    wait = boot_wait_seconds(spec)
    outcomes: dict[str, tuple[bool, str]] = {}
    root = workspace_root()
    for cfg in discover_for_session(spec):
        hint = cfg.get("repo_dir") or cfg.get("service_key") or ""
        if hint:
            register_required_service(str(hint), reason=cfg.get("reason", "ensure-peers"))
        key = str(cfg.get("service_key") or cfg.get("repo_dir") or "service")
        svc_cfg = {
            k: cfg[k]
            for k in ("default_base", "health_path", "boot", "base_env_var", "optional", "workspace_key")
            if k in cfg
        }
        if health_up(svc_cfg):
            outcomes[key] = (True, f"{key}: already up ({_base_url(svc_cfg)})")
            continue
        repo_path = None
        if root and cfg.get("repo_dir"):
            candidate = root / str(cfg["repo_dir"])
            if candidate.is_dir():
                repo_path = candidate
        outcomes[key] = start_service(
            key,
            svc_cfg,
            wait_seconds=wait,
            force=force,
            repo=repo_path,
        )
    return outcomes


def need_service(
    hint: str,
    *,
    reason: str = "",
    wait_seconds: int = 180,
    force: bool = False,
) -> tuple[bool, str]:
    """Register + boot a service by name (no deploy/tdd entry required)."""
    from service_discovery import find_repo, infer_service_config, register_required_service

    register_required_service(hint, reason=reason or "bob need-service")
    repo = find_repo(hint)
    if not repo:
        return False, f"`{hint}`: no matching repo under BUILDER_WORKSPACE_ROOT"
    cfg = infer_service_config(repo, service_key=hint.replace("-", "_"))
    return start_service(hint, cfg, wait_seconds=wait_seconds, force=force, repo=repo)


def status_report(spec_env: dict | None = None) -> list[str]:
    lines: list[str] = []
    env_block = spec_env or {}
    services = env_block.get("services") or {}
    if not services:
        lines.append("No services in env profile.")
        return lines
    for key, svc_cfg in services.items():
        up = health_up(svc_cfg)
        base = _base_url(svc_cfg) or "(no base URL)"
        pid = ""
        pf = _pid_file(key)
        if pf.is_file():
            pid = f" pid={pf.read_text(encoding='utf-8').strip()}"
        lines.append(f"  {key}: {'UP' if up else 'DOWN'} at {base}{pid}")
    return lines


def load_env_profile(profile: str) -> dict:
    path = host_repo_root() / "deploy/tdd" / f"{profile}.yaml"
    return load(path) if path.is_file() else {}
