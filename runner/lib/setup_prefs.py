"""Bob setup wizard."""
from __future__ import annotations

import getpass
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from _yaml_util import runner_root
from bob_home import bob_assets_root, bob_local_hint, bob_local_root, ensure_bob_home, prefs_path
from host_repo import host_repo_root as resolve_host, infer_workspace_root, runner_bootstrap_repo
from workspace_env import WORKSPACE_ENV, set_workspace_env


def _bootstrap_prefs_path() -> Path:
    """user.env beside bob.py — load before workspace env is known."""
    return runner_bootstrap_repo() / "local" / "user.env"


def _prefs_path() -> Path:
    ensure_bob_home(quiet=True)
    bootstrap = _bootstrap_prefs_path()
    if bootstrap.is_file():
        return bootstrap
    p = prefs_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _global_prefs_paths() -> list[Path]:
    return [Path.home() / ".bob-the-builder.env"]


def load_prefs_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def load_all_prefs() -> dict[str, str]:
    merged: dict[str, str] = {}
    for gp in _global_prefs_paths():
        merged.update(load_prefs_file(gp))
    merged.update(load_prefs_file(_bootstrap_prefs_path()))
    return merged


def apply_prefs_to_environ(prefs: dict[str, str]) -> None:
    for k, v in prefs.items():
        if v:
            os.environ[k] = v
    ws = prefs.get(WORKSPACE_ENV, "").strip()
    if ws:
        set_workspace_env(ws)


def load_prefs_into_environ() -> dict[str, str]:
    prefs = load_all_prefs()
    apply_prefs_to_environ(prefs)
    return prefs


def _prompt(label: str, default: str = "", secret: bool = False) -> str:
    hint = f" [{default}]" if default else ""
    try:
        if secret:
            raw = getpass.getpass(f"{label}{hint}: ")
        else:
            raw = input(f"{label}{hint}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(130)
    raw = raw.strip()
    return raw if raw else default


def _find_mysql() -> str | None:
    if sys.platform == "win32":
        for c in (
            Path(r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"),
            Path(r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe"),
        ):
            if c.exists():
                return str(c)
    try:
        subprocess.run(["mysql", "--version"], capture_output=True, timeout=10, check=True)
        return "mysql"
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None


def _mysql_ping(bin_path: str, prefs: dict[str, str]) -> bool:
    cmd = [
        bin_path,
        f"-h{prefs.get('MYSQL_HOST', '127.0.0.1')}",
        f"-P{prefs.get('MYSQL_PORT', '3306')}",
        f"-u{prefs.get('MYSQL_USER', 'root')}",
        f"-p{prefs.get('MYSQL_PASS', 'root')}",
        "-e",
        "SELECT 1",
    ]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=15).returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _prefs_save_keys(prefs: dict[str, str]) -> list[str]:
    from host_profile import service_base_env_vars

    keys = [
        WORKSPACE_ENV,
        "BOB_HOME",
        "BOB_LOCAL",
        "BOB_RUNNER_ROOT",
        "BOB_LAST_HOST_REPO",
        "LOGS_DIR",
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_USER",
        "MYSQL_PASS",
        "GIT_BASE_BRANCH",
        "GIT_BRANCH_PREFIX",
        "TENANT",
        "CLIENT",
        "TDD_REUSE_CURRENT",
    ]
    host_s = prefs.get("BOB_LAST_HOST_REPO", "").strip()
    host = Path(host_s) if host_s else resolve_host()
    for var in service_base_env_vars(host=host):
        if var not in keys:
            keys.append(var)
    for k in sorted(prefs):
        if k.endswith("_BASE") and k not in keys:
            keys.append(k)
    return keys


def _prefs_defaults() -> dict[str, str]:
    from host_profile import bob_defaults, service_base_prompts

    defaults = {
        "MYSQL_HOST": "127.0.0.1",
        "MYSQL_PORT": "3306",
        "MYSQL_USER": "root",
        "MYSQL_PASS": "root",
        "GIT_BASE_BRANCH": "ddp-prod",
        "GIT_BRANCH_PREFIX": "ddp-fea-",
        "TENANT": "dsa",
        "CLIENT": "dsa_agent_app",
        "TDD_REUSE_CURRENT": "1",
    }
    for prompt in service_base_prompts():
        if prompt.default_base:
            defaults[prompt.base_env_var] = prompt.default_base
    d = bob_defaults()
    defaults.setdefault(str(d.get("primary_base_env_var") or "CC_BASE"), str(d.get("primary_default_base") or ""))
    defaults.setdefault("MD_BASE", "http://localhost:8015/masterdata")
    return defaults


def prompt_service_bases(prefs: dict[str, str], *, host: Path | None = None) -> None:
    """Prompt for each {SERVICE}_BASE from host deploy/tdd (CC/MD remain default peers)."""
    from host_profile import default_env_profile, service_base_prompts
    from ticket_spec import env_profile_path

    host = host or resolve_host()
    prof_path = env_profile_path(default_env_profile(), base=host)
    print()
    if prof_path:
        print(f"Service base URLs (from deploy/tdd/{prof_path.name}):")
    else:
        print("Service base URLs (product defaults + inferred host port):")
    for item in service_base_prompts(host=host):
        current = prefs.get(item.base_env_var, "")
        default = current or item.default_base
        label = f"{item.label} ({item.base_env_var})"
        if item.optional:
            val = _prompt(f"{label} [optional]", default)
            if val.strip():
                prefs[item.base_env_var] = val.strip()
            else:
                prefs.pop(item.base_env_var, None)
        else:
            prefs[item.base_env_var] = _prompt(label, default)


def save_prefs(prefs: dict[str, str]) -> Path:
    ensure_bob_home(quiet=True)
    prefs["BOB_HOME"] = str(bob_assets_root())
    prefs["BOB_LOCAL"] = bob_local_hint()
    path = _prefs_path()
    lines = [
        "# Bob the Builder — machine-local (do not commit)",
        f"# Updated: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    keys = _prefs_save_keys(prefs)
    defaults = _prefs_defaults()
    for k in keys:
        lines.append(f"{k}={prefs.get(k, defaults.get(k, ''))}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def run_setup_wizard(*, reconfigure: bool = True) -> int:
    prefs = load_all_prefs()
    apply_prefs_to_environ(prefs)
    repo = resolve_host()

    print()
    print("=== Bob the Builder — setup ===")
    if _prefs_path().exists() and not reconfigure:
        print(f"Prefs: {_prefs_path()} — run: bob setup")
        return 0

    print("Service git clones live under one parent folder.")
    print(f"Stored as {WORKSPACE_ENV} in BOB_LOCAL/user.env")
    print()

    inferred = infer_workspace_root()
    ws_default = prefs.get(WORKSPACE_ENV) or (str(inferred) if inferred else str(repo.parent))
    prefs[WORKSPACE_ENV] = _prompt("Workspace root (parent of service repos)", ws_default)
    ws = Path(prefs[WORKSPACE_ENV])
    print(f"Workspace: {ws}" + (" (not found yet)" if not ws.is_dir() else ""))

    prefs["LOGS_DIR"] = _prompt("Logs directory", prefs.get("LOGS_DIR") or str(repo))
    prefs["MYSQL_HOST"] = _prompt("MySQL host", prefs.get("MYSQL_HOST", "127.0.0.1"))
    prefs["MYSQL_PORT"] = _prompt("MySQL port", prefs.get("MYSQL_PORT", "3306"))
    prefs["MYSQL_USER"] = _prompt("MySQL user", prefs.get("MYSQL_USER", "root"))

    mysql_bin = _find_mysql()
    if mysql_bin and not _mysql_ping(mysql_bin, prefs):
        prefs["MYSQL_PASS"] = _prompt("MySQL password", prefs.get("MYSQL_PASS", "root"), secret=True)
    elif not mysql_bin:
        prefs["MYSQL_PASS"] = _prompt("MySQL password", prefs.get("MYSQL_PASS", "root"), secret=True)

    prefs["BOB_LAST_HOST_REPO"] = str(repo.resolve())
    apply_prefs_to_environ(prefs)
    prompt_service_bases(prefs, host=repo)

    prefs["GIT_BASE_BRANCH"] = _prompt("Git base branch", prefs.get("GIT_BASE_BRANCH", "ddp-prod"))
    prefs["TENANT"] = _prompt("Tenant code", prefs.get("TENANT", "dsa"))
    prefs["CLIENT"] = _prompt("Client code", prefs.get("CLIENT", "dsa_agent_app"))

    prefs["BOB_RUNNER_ROOT"] = str(runner_root().resolve())
    apply_prefs_to_environ(prefs)
    assets = ensure_bob_home()
    out = save_prefs(prefs)
    print()
    print(f"Saved -> {out}")
    print(f"Host repo: {repo.name}")
    print(f"BOB_HOME: {assets}")
    print(f"BOB_LOCAL: {bob_local_root()}")
    print("Next: bob install   bob init-ticket <id> \"Title\"")
    return 0
