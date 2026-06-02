"""Discover Novopay service repos and infer boot/health from application.properties."""
from __future__ import annotations

import re
import time
from pathlib import Path

from _yaml_util import dump, load
from bob_home import agent_dir
from host_repo import host_repo_root
from workspace import workspace_root

LOCALHOST_URL = re.compile(
    r"https?://(?:localhost|127\.0\.0\.1):(\d+)(/[A-Za-z0-9._/-]*)?",
    re.I,
)
SERVER_PORT = re.compile(r"^server\.port\s*=\s*(\d+)\s*$", re.M)
CONTEXT_PATH = re.compile(r"^server\.servlet\.context-path\s*=\s*(/\S*)\s*$", re.M)

# Property key fragments → workspace repo folder hints
SERVICE_HINTS: dict[str, str] = {
    "masterdata": "novopay-platform-masterdata-management",
    "notification": "novopay-platform-notifications",
    "notifications": "novopay-platform-notifications",
    "consent": "novopay-platform-consents",
    "consents": "novopay-platform-consents",
    "api-gateway": "novopay-platform-api-gateway",
    "api_gateway": "novopay-platform-api-gateway",
    "actor": "novopay-platform-actor",
    "authorization": "novopay-platform-authorization",
    "creditcard": "novopay-platform-creditcard-management",
    "credit-card": "novopay-platform-creditcard-management",
}

JAVA_IMPORT_HINTS: dict[str, str] = {
    "in.novopay.infra.notifications": "notification",
    "in.novopay.infra.masterdata": "masterdata",
    "in.novopay.platform.consents": "consents",
    "in.novopay.infra.consent": "consents",
}

CONFIG_PEER = re.compile(
    r"(?:^|[.\s_])(?:novopay\.)?(notifications?|masterdata|consents?)(?:[.\s_]|\.url|\.service|\.base|\.host)",
    re.I,
)


def required_services_path() -> Path:
    p = agent_dir() / "required-services.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_required_services() -> list[dict]:
    path = required_services_path()
    if not path.is_file():
        return []
    data = load(path)
    return list(data.get("services") or [])


def save_required_services(entries: list[dict]) -> Path:
    path = required_services_path()
    dump(path, {"services": entries, "updated": time.strftime("%Y-%m-%dT%H:%M:%S")})
    return path


def register_required_service(hint: str, *, reason: str = "", repo_dir: str = "") -> dict:
    hint = hint.strip()
    entries = load_required_services()
    repo = find_repo(hint) if not repo_dir else workspace_root() / repo_dir if workspace_root() else None
    resolved_dir = repo_dir or (repo.name if repo else "")
    for e in entries:
        if e.get("hint") == hint or (resolved_dir and e.get("repo_dir") == resolved_dir):
            if reason:
                e["reason"] = reason
            save_required_services(entries)
            return e
    entry = {
        "hint": hint,
        "repo_dir": resolved_dir,
        "reason": reason or "registered for current ticket/session",
        "added_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    entries.append(entry)
    save_required_services(entries)
    return entry


def list_workspace_repos() -> list[Path]:
    root = workspace_root()
    if not root:
        return []
    out: list[Path] = []
    for p in sorted(root.iterdir()):
        if not p.is_dir():
            continue
        if (p / ".git").exists() or (p / ".git").is_file():
            out.append(p)
        elif p.name.startswith("novopay-platform-"):
            out.append(p)
    return out


def find_repo(hint: str) -> Path | None:
    hint_l = hint.lower().replace("_", "-").strip()
    root = workspace_root()
    if not root:
        return None
    if (root / hint).is_dir():
        return root / hint
    if hint in SERVICE_HINTS and (root / SERVICE_HINTS[hint]).is_dir():
        return root / SERVICE_HINTS[hint]
    for repo in list_workspace_repos():
        name = repo.name.lower()
        if hint_l == name or hint_l in name:
            return repo
        short = name.replace("novopay-platform-", "")
        if hint_l == short or hint_l in short:
            return repo
    return None


def _read_properties_text(repo: Path) -> str:
    chunks: list[str] = []
    for rel in (
        "src/main/resources/application.properties",
        "src/main/resources/application-local.properties",
        "deploy/application/dist/application.properties",
    ):
        p = repo / rel
        if p.is_file():
            chunks.append(p.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(chunks)


def infer_service_config(repo: Path, *, service_key: str | None = None) -> dict:
    text = _read_properties_text(repo)
    port_m = SERVER_PORT.search(text)
    ctx_m = CONTEXT_PATH.search(text)
    port = port_m.group(1) if port_m else "8080"
    ctx = (ctx_m.group(1) if ctx_m else "").rstrip("/")
    base = f"http://localhost:{port}{ctx}"
    key = service_key or repo.name.replace("novopay-platform-", "").replace("-", "_")
    return {
        "service_key": key,
        "repo_dir": repo.name,
        "default_base": base,
        "health_path": "/actuator/health",
        "boot": {"task": "bootRun", "args": []},
    }


def repo_for_port(port: int) -> Path | None:
    for repo in list_workspace_repos():
        text = _read_properties_text(repo)
        m = SERVER_PORT.search(text)
        if m and int(m.group(1)) == port:
            return repo
    return None


def discover_localhost_peers(host: Path | None = None) -> list[dict]:
    """Find localhost URLs in host properties → map to workspace repos."""
    host = host or host_repo_root()
    found: list[dict] = []
    seen: set[str] = set()
    for pf in host.rglob("*.properties"):
        if "node_modules" in str(pf) or "build" in pf.parts:
            continue
        try:
            text = pf.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for port_s, _path in LOCALHOST_URL.findall(text):
            port = int(port_s)
            repo = repo_for_port(port)
            if not repo or repo.resolve() == host.resolve():
                continue
            key = repo.name
            if key in seen:
                continue
            seen.add(key)
            cfg = infer_service_config(repo)
            cfg["reason"] = f"referenced in {pf.relative_to(host)}"
            found.append(cfg)
        for m in CONFIG_PEER.finditer(text):
            hint = m.group(1).lower()
            if hint.startswith("notification"):
                hint = "notifications"
            repo = find_repo(hint)
            if repo and repo.name not in seen:
                seen.add(repo.name)
                cfg = infer_service_config(repo)
                cfg["reason"] = f"property mentions `{m.group(1)}` in {pf.relative_to(host)}"
                found.append(cfg)
    return found


def discover_from_codebase(host: Path | None = None) -> list[dict]:
    """Infer peer services from host source (Java, properties, YAML) — no deploy/tdd required."""
    host = host or host_repo_root()
    if not host.is_dir():
        return []
    found: list[dict] = []
    seen: set[str] = set()
    scan_roots = (
        host / "src/main/java",
        host / "src/main/resources",
        host / "src/test/java",
    )
    texts: list[tuple[Path, str]] = []
    for root in scan_roots:
        if not root.is_dir():
            continue
        for pf in root.rglob("*"):
            if not pf.is_file():
                continue
            if pf.suffix.lower() not in {".java", ".properties", ".yaml", ".yml", ".xml"}:
                continue
            if "build" in pf.parts or "node_modules" in pf.parts:
                continue
            try:
                texts.append((pf, pf.read_text(encoding="utf-8", errors="ignore")))
            except OSError:
                continue

    def add_repo(repo: Path, *, reason: str) -> None:
        if not repo.is_dir() or repo.resolve() == host.resolve():
            return
        key = repo.name
        if key in seen:
            return
        seen.add(key)
        cfg = infer_service_config(repo)
        cfg["reason"] = reason
        found.append(cfg)

    for pf, text in texts:
        rel = pf.relative_to(host)
        for port_s, _path in LOCALHOST_URL.findall(text):
            port = int(port_s)
            repo = repo_for_port(port)
            if repo:
                add_repo(repo, reason=f"localhost:{port} in {rel}")
        for folder in re.findall(r"novopay-platform-[a-z0-9-]+", text, re.I):
            repo = find_repo(folder)
            if repo:
                add_repo(repo, reason=f"repo mention in {rel}")
        for imp, hint in JAVA_IMPORT_HINTS.items():
            if imp in text:
                repo = find_repo(hint)
                if repo:
                    add_repo(repo, reason=f"Java import `{imp}` in {rel}")
        for m in CONFIG_PEER.finditer(text):
            hint = m.group(1).lower().rstrip("s")  # notifications -> notification
            if hint == "consent":
                hint = "consents"
            repo = find_repo(hint)
            if repo:
                add_repo(repo, reason=f"config/API peer `{m.group(1)}` in {rel}")
    return found


def discover_for_session(spec: dict | None = None) -> list[dict]:
    """Merge env profile, required-services.yaml, host repo, and property scan."""
    out: list[dict] = []
    seen_dirs: set[str] = set()

    def add(cfg: dict) -> None:
        rd = cfg.get("repo_dir") or ""
        if not rd or rd in seen_dirs:
            return
        seen_dirs.add(rd)
        out.append(cfg)

    from service_boot import caller_service_config

    host_cfg = caller_service_config(spec)
    if host_cfg:
        add(host_cfg)

    if spec:
        from service_boot import services_for_spec

        env_block = spec.get("_env") or {}
        for key in services_for_spec(spec):
            svc = (env_block.get("services") or {}).get(key) or {}
            ws_key = svc.get("workspace_key") or key
            from workspace_services import repo_dir_for_service

            rd = repo_dir_for_service(ws_key) or repo_dir_for_service(key)
            if rd:
                root = workspace_root()
                if root and (root / rd).is_dir():
                    cfg = infer_service_config(root / rd, service_key=key)
                    cfg.update({k: v for k, v in svc.items() if k in ("default_base", "health_path", "boot", "base_env_var")})
                    add(cfg)

    for entry in load_required_services():
        hint = entry.get("hint") or entry.get("repo_dir") or ""
        repo = find_repo(entry.get("repo_dir") or hint)
        if repo:
            cfg = infer_service_config(repo, service_key=entry.get("hint") or repo.name)
            cfg["reason"] = entry.get("reason", "required-services.yaml")
            add(cfg)

    for cfg in discover_localhost_peers():
        add(cfg)

    for cfg in discover_from_codebase():
        add(cfg)

    return out
