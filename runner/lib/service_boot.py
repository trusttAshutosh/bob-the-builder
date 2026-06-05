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

from boot_remediation import (
    BOOT_PROFILE_EXTENDED,
    BOOT_PROFILE_STANDARD,
    build_spring_args,
    diagnose_boot_log,
    dist_properties_path,
    escalation_chain,
    repo_has_copy_properties_task,
)


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


def health_reachable(svc_cfg: dict, *, timeout: float = 5) -> bool:
    """Tomcat responding on health URL (even 503) — enough for LOC API E2E when ES is down."""
    base = _base_url(svc_cfg)
    if not base:
        return False
    health_path = svc_cfg.get("health_path", "/actuator/health")
    url = f"{base}{health_path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return False


def _mysql_creds() -> tuple[str, str]:
    user = os.environ.get("MYSQL_USER", "root").strip() or "root"
    pw = os.environ.get("MYSQL_PASS", "root").strip() or "root"
    return user, pw


def _interpolate_boot_value(value: str) -> str:
    user, pw = _mysql_creds()
    return (
        value.replace("{MYSQL_USER}", user)
        .replace("{MYSQL_PASS}", pw)
    )


def _norm_service_key(key: str) -> str:
    return key.replace("-", "_").lower().strip()


def _is_credit_card_service(service_key: str, repo: Path) -> bool:
    key = _norm_service_key(service_key)
    if key in ("credit_card_management", "creditcard_management"):
        return True
    return repo.name == "novopay-platform-creditcard-management"


def _strict_service_entry(service_key: str, svc_cfg: dict) -> dict:
    if svc_cfg.get("repo_dir") or svc_cfg.get("boot"):
        return svc_cfg
    from workspace_services import load_workspace_services

    services = load_workspace_services().get("services") or {}
    ws_key = svc_cfg.get("workspace_key") or service_key
    if ws_key in services:
        return services[ws_key]
    if service_key in services:
        return services[service_key]
    return {}


def _repo_dir_name(service_key: str, svc_cfg: dict) -> str:
    if svc_cfg.get("repo_dir"):
        return str(svc_cfg["repo_dir"])
    entry = _strict_service_entry(service_key, svc_cfg)
    return str(entry.get("repo_dir") or "")


def _caller_repo() -> Path | None:
    """Gradle repo Bob was invoked from (BOB_HOST_REPO / cwd), not a fixed service."""
    host = host_repo_root()
    if host.is_dir() and _gradle_wrapper(host).is_file():
        return host.resolve()
    return None


def _repo_matches_service_key(service_key: str, svc_cfg: dict, repo: Path) -> bool:
    """True when caller repo is the service Bob is trying to boot (not always CC)."""
    if not repo.is_dir() or not _gradle_wrapper(repo).is_file():
        return False
    rd = _repo_dir_name(service_key, svc_cfg)
    if rd and repo.name == Path(rd).name:
        return True
    from service_discovery import infer_service_config

    inferred = infer_service_config(repo)
    inferred_key = _norm_service_key(str(inferred.get("service_key", "")))
    want = _norm_service_key(service_key)
    if inferred_key == want:
        return True
    cc_aliases = {"credit_card_management", "creditcard_management"}
    return want in cc_aliases and inferred_key in cc_aliases


def _kafka_bootstrap_override() -> str:
    return (os.environ.get("BOB_KAFKA_BOOTSTRAP") or "").strip()


def _append_kafka_bootstrap(spring_args: str) -> str:
    kafka = _kafka_bootstrap_override()
    if kafka:
        return spring_args + f" --message.broker.bootstrap.servers={kafka}"
    return spring_args


def _boot_args_from_profile(
    service_key: str,
    repo: Path,
    profile: str,
) -> list[str]:
    user, pw = _mysql_creds()
    include_kafka = _is_credit_card_service(service_key, repo)
    spring_args = build_spring_args(
        repo,
        profile,
        mysql_user=user,
        mysql_pass=pw,
        include_kafka=include_kafka,
    )
    if include_kafka and profile == BOOT_PROFILE_STANDARD:
        spring_args = _append_kafka_bootstrap(spring_args)
    if not spring_args.strip():
        return []
    return [f"--args={spring_args}"]


def _resolve_boot_args(
    service_key: str,
    repo: Path,
    boot_cfg: dict,
    *,
    profile: str = BOOT_PROFILE_STANDARD,
) -> list[str]:
    raw = boot_cfg.get("args")
    if raw:
        return [_interpolate_boot_value(str(arg)) for arg in raw]
    if _novopay_service_needs_standard_boot(repo):
        return _boot_args_from_profile(service_key, repo, profile)
    return []


def _novopay_service_needs_standard_boot(repo: Path) -> bool:
    """Any Novopay Spring service with dist props or typical layout gets Bob boot fixes."""
    if dist_properties_path(repo):
        return True
    if repo.name.startswith("novopay-platform-"):
        return True
    return (repo / "src/main/resources/application.properties").is_file()


def _gradle_wrapper(repo: Path) -> Path:
    if sys.platform == "win32":
        wrapper = repo / "gradlew.bat"
        if wrapper.is_file():
            return wrapper
    return repo / "gradlew"


def _run_pre_tasks(repo: Path, boot_cfg: dict, service_key: str) -> tuple[bool, str]:
    tasks = list(boot_cfg.get("pre_tasks") or [])
    if not tasks and (
        _is_credit_card_service(service_key, repo)
        or repo_has_copy_properties_task(repo)
        or dist_properties_path(repo)
    ):
        tasks = ["copyProperties"]
    if not tasks:
        return True, ""
    wrapper = _gradle_wrapper(repo)
    if not wrapper.is_file():
        return False, f"no Gradle wrapper in {repo}"
    for task in tasks:
        r = subprocess.run(
            [str(wrapper), str(task), "-q"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=180,
        )
        if r.returncode != 0:
            detail = (r.stderr or r.stdout or "").strip()[-1500:]
            return False, f"pre-task `{task}` failed (exit {r.returncode})\n{detail}"
    return True, ""


def _gradle_boot_cmd(
    repo: Path,
    boot_cfg: dict,
    *,
    service_key: str = "",
    profile: str = BOOT_PROFILE_STANDARD,
) -> list[str]:
    task = boot_cfg.get("task", "bootRun")
    extra = _resolve_boot_args(service_key, repo, boot_cfg, profile=profile)
    wrapper = _gradle_wrapper(repo)
    return [str(wrapper), task, *extra]


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
    """
    Resolve repo path for bootRun:
    1) workspace-services map under workspace root
    2) caller repo (where Bob was run) only if it matches service_key
    3) sibling clone discovery (e.g. masterdata when host repo is CC)
    """
    entry = _strict_service_entry(service_key, svc_cfg) or svc_cfg
    ws_key = entry.get("workspace_key") or svc_cfg.get("workspace_key") or service_key
    repo = service_repo_path(ws_key)
    if repo:
        return repo
    repo_dir = _repo_dir_name(service_key, entry)
    root = workspace_root()
    if root and repo_dir:
        p = root / repo_dir
        if p.is_dir():
            return p
    if _norm_service_key(service_key) in ("masterdata_management", "masterdata"):
        from service_discovery import find_repo

        md = find_repo("masterdata")
        if md and md.is_dir():
            return md
    caller = _caller_repo()
    if caller and _repo_matches_service_key(service_key, entry, caller):
        return caller
    return None


def masterdata_service_keys(spec: dict) -> list[str]:
    """Env profile keys for masterdata-management (WireMock URL resolution)."""
    env_block = spec.get("_env") or {}
    services = env_block.get("services") or {}
    keys: list[str] = []
    for key in services:
        nk = _norm_service_key(key)
        if nk in ("masterdata_management", "masterdata") or "masterdata" in nk:
            keys.append(key)
    return keys


def masterdata_required_for_spec(spec: dict) -> bool:
    run = spec.get("run") or {}
    if not run.get("apply_masterdata", True):
        return False
    return bool(spec.get("masterdata")) or bool((spec.get("stubs") or []))


def _boot_once(
    service_key: str,
    svc_cfg: dict,
    repo: Path,
    boot_cfg: dict,
    *,
    wait_seconds: int,
    profile: str,
    log_header: str,
) -> tuple[bool, str, Path]:
    """Single bootRun attempt; returns (ok, message, log_path)."""
    cmd = _gradle_boot_cmd(repo, boot_cfg, service_key=service_key, profile=profile)
    log = _log_file(service_key)
    boot_env = os.environ.copy()
    for k, v in (boot_cfg.get("env") or {}).items():
        boot_env[str(k)] = str(v)

    with log.open("a", encoding="utf-8") as logfh:
        logfh.write(f"\n{log_header}\n{' '.join(cmd)}\n\n")
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
    pf = _pid_file(service_key)
    pf.write_text(str(proc.pid), encoding="utf-8")

    deadline = time.time() + wait_seconds
    last_log = 0.0
    while time.time() < deadline:
        if health_up(svc_cfg, timeout=3):
            return (
                True,
                f"{service_key}: UP ({_base_url(svc_cfg)}) pid={proc.pid} log={log}"
                + (f" [boot profile: {profile}]" if profile != BOOT_PROFILE_STANDARD else ""),
                log,
            )
        if proc.poll() is not None:
            tail = log.read_text(encoding="utf-8", errors="replace")[-4000:]
            return (
                False,
                f"{service_key}: bootRun exited {proc.returncode}\n{tail}",
                log,
            )
        now = time.time()
        if now - last_log >= 15:
            left = int(deadline - now)
            print(f"Bob: waiting for {service_key} actuator health (~{left}s left)...", flush=True)
            last_log = now
        time.sleep(3)

    tail_hint = log.read_text(encoding="utf-8", errors="replace")[-1500:]
    return (
        False,
        f"{service_key}: timeout after {wait_seconds}s — see {log}\n{tail_hint}",
        log,
    )


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
    pre_ok, pre_msg = _run_pre_tasks(repo, boot_cfg, service_key)
    if not pre_ok:
        return False, f"{service_key}: {pre_msg}"

    from application_props_sync import sync_application_properties_from_prefs

    sync_ok, sync_msg = sync_application_properties_from_prefs(repo)
    if not sync_ok:
        return False, f"{service_key}: {sync_msg}"

    log = _log_file(service_key)
    user, _pw = _mysql_creds()
    log.write_text(
        f"=== boot {service_key} (MYSQL_USER={user}) ===\n{sync_msg}\n",
        encoding="utf-8",
    )

    if boot_cfg.get("args"):
        profiles = [BOOT_PROFILE_STANDARD]
    else:
        log_tail = ""
        if log.is_file():
            log_tail = log.read_text(encoding="utf-8", errors="replace")
        profiles = escalation_chain(diagnose_boot_log(log_tail))

    last_msg = ""
    for attempt, profile in enumerate(profiles):
        if attempt > 0:
            print(
                f"Bob: boot remediation for {service_key} — retry with profile `{profile}`",
                flush=True,
            )
            stop_service(service_key)
            pre_ok, pre_msg = _run_pre_tasks(repo, boot_cfg, service_key)
            if not pre_ok:
                return False, f"{service_key}: {pre_msg}"
        header = f"=== attempt {attempt + 1} profile={profile} ==="
        ok, msg, log = _boot_once(
            service_key,
            svc_cfg,
            repo,
            boot_cfg,
            wait_seconds=wait_seconds,
            profile=profile,
            log_header=header,
        )
        last_msg = msg
        if ok:
            return True, msg

    return False, last_msg


def primary_service_key(spec: dict) -> str:
    from host_profile import primary_service_key as _primary

    return _primary(spec)


def _svc_cfg_fields() -> tuple[str, ...]:
    return ("default_base", "health_path", "boot", "base_env_var", "optional", "workspace_key")


def _to_svc_cfg(cfg: dict) -> dict:
    return {k: cfg[k] for k in _svc_cfg_fields() if k in cfg}


def caller_service_config(spec: dict | None = None) -> dict | None:
    """Boot config for BOB_HOST_REPO / cwd Gradle repo (always at least one service)."""
    caller = _caller_repo()
    if not caller:
        return None
    from service_discovery import infer_service_config

    spec = spec or {}
    env_block = spec.get("_env") or {}
    primary = primary_service_key(spec)
    services = env_block.get("services") or {}
    merged_key = primary
    svc_env = dict(services.get(primary) or {})
    if not _repo_matches_service_key(primary, svc_env, caller):
        merged_key = ""
        svc_env = {}
        for key, svc in services.items():
            if _repo_matches_service_key(key, svc, caller):
                merged_key = key
                svc_env = dict(svc)
                break
    inferred = infer_service_config(caller, service_key=merged_key or None)
    if merged_key:
        inferred["service_key"] = merged_key
    inferred.update({k: v for k, v in svc_env.items() if k in _svc_cfg_fields()})
    inferred["repo_dir"] = caller.name
    inferred["reason"] = "host repo (BOB_HOST_REPO / cwd)"
    return inferred


def _discover_all_boot_configs(spec: dict) -> list[dict]:
    """
    Ordered boot targets: primary/caller host first, then profile peers and discovery.
    Caller repo counts as bootable even when peer discovery returns empty.
    """
    by_key: dict[str, dict] = {}

    def merge_cfg(cfg: dict) -> None:
        key = _norm_service_key(str(cfg.get("service_key") or cfg.get("repo_dir") or ""))
        if not key:
            return
        prev = by_key.get(key)
        if prev:
            prev.update({k: v for k, v in cfg.items() if v is not None and v != ""})
        else:
            by_key[key] = dict(cfg)

    env_block = spec.get("_env") or {}
    if auto_discover_enabled(spec):
        from service_discovery import discover_for_session

        for cfg in discover_for_session(spec):
            merge_cfg(cfg)
    else:
        from service_discovery import infer_service_config

        for key in services_for_spec(spec):
            svc = (env_block.get("services") or {}).get(key) or {}
            repo_path = _resolve_repo(key, svc)
            if not repo_path:
                continue
            cfg = infer_service_config(repo_path, service_key=key)
            cfg.update({k: v for k, v in svc.items() if k in _svc_cfg_fields()})
            cfg["repo_dir"] = str(repo_path.name)
            merge_cfg(cfg)

    host_cfg = caller_service_config(spec)
    if host_cfg:
        merge_cfg(host_cfg)

    if not by_key and host_cfg:
        merge_cfg(host_cfg)

    primary = _norm_service_key(primary_service_key(spec))
    cc_aliases = {_norm_service_key(k) for k in ("credit_card_management", "creditcard_management")}
    ordered_keys: list[str] = []
    if masterdata_required_for_spec(spec):
        for md_key in masterdata_service_keys(spec):
            if md_key in by_key and md_key not in ordered_keys:
                ordered_keys.append(md_key)
    if primary in by_key:
        ordered_keys.append(primary)
    elif primary in cc_aliases:
        for alias in cc_aliases:
            if alias in by_key and alias not in ordered_keys:
                ordered_keys.append(alias)
                break
    for key in sorted(by_key.keys()):
        if key not in ordered_keys:
            ordered_keys.append(key)
    return [by_key[k] for k in ordered_keys]


def _collect_boot_configs(spec: dict) -> list[dict]:
    """Boot targets after boot_plan filtering (changed-only default)."""
    plan = spec.get("_boot_plan")
    if plan is not None:
        return plan.boot_configs

    from boot_plan import BOOT_POLICY_ALL, boot_policy, build_boot_plan

    if boot_policy(spec) == BOOT_POLICY_ALL:
        return _discover_all_boot_configs(spec)
    return build_boot_plan(spec).boot_configs


def services_for_spec(spec: dict) -> list[str]:
    env_block = spec.get("_env") or {}
    services = env_block.get("services") or {}
    if not services:
        return []
    impacted_repos = set((spec.get("impacted") or {}).get("repos") or [])
    keys: list[str] = []
    md_keys = set(masterdata_service_keys(spec))
    for key, svc_cfg in services.items():
        optional_skip = (
            svc_cfg.get("optional")
            and not os.environ.get(svc_cfg.get("base_env_var", ""), "").strip()
            and not (masterdata_required_for_spec(spec) and key in md_keys)
        )
        if optional_skip:
            continue
        ws_key = svc_cfg.get("workspace_key") or key
        repo_dir = repo_dir_for_service(ws_key) or repo_dir_for_service(key)
        if impacted_repos and repo_dir and repo_dir not in impacted_repos:
            if key not in impacted_repos and ws_key not in impacted_repos:
                if not (masterdata_required_for_spec(spec) and key in md_keys):
                    continue
        keys.append(key)
    if masterdata_required_for_spec(spec):
        for md_key in masterdata_service_keys(spec):
            if md_key in services and md_key not in keys:
                keys.insert(0, md_key)
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


def _resolve_boot_repo(service_key: str, svc_cfg: dict, cfg: dict) -> Path | None:
    repo_path = _resolve_repo(service_key, svc_cfg)
    if repo_path:
        return repo_path
    root = workspace_root()
    if root and cfg.get("repo_dir"):
        candidate = root / str(cfg["repo_dir"])
        if candidate.is_dir():
            return candidate
    caller = _caller_repo()
    if caller and _repo_matches_service_key(service_key, svc_cfg, caller):
        return caller
    return None


def ensure_services_running(spec: dict, *, force: bool = False) -> dict[str, tuple[bool, str]]:
    wait = boot_wait_seconds(spec)
    outcomes: dict[str, tuple[bool, str]] = {}
    for cfg in _collect_boot_configs(spec):
        key = str(cfg.get("service_key") or cfg.get("repo_dir") or "service")
        svc_cfg = _to_svc_cfg(cfg)
        repo_path = _resolve_boot_repo(key, svc_cfg, cfg)
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
    """Discover peers from code/properties/session and boot anything not healthy (host first)."""
    from service_discovery import register_required_service

    spec = spec or {"run": {"boot_wait_seconds": wait_seconds}, "impacted": {}}
    wait = boot_wait_seconds(spec)
    outcomes: dict[str, tuple[bool, str]] = {}
    for cfg in _collect_boot_configs(spec):
        hint = cfg.get("repo_dir") or cfg.get("service_key") or ""
        if hint:
            register_required_service(str(hint), reason=cfg.get("reason", "ensure-peers"))
        key = str(cfg.get("service_key") or cfg.get("repo_dir") or "service")
        svc_cfg = _to_svc_cfg(cfg)
        if health_up(svc_cfg):
            outcomes[key] = (True, f"{key}: already up ({_base_url(svc_cfg)})")
            continue
        repo_path = _resolve_boot_repo(key, svc_cfg, cfg)
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
    from ticket_spec import load_env_profile_block

    return load_env_profile_block(profile, base=host_repo_root())
