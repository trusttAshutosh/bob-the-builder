"""Plan which services to boot vs mock for validate-ticket (changed-only default)."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from host_repo import host_repo_root

BOOT_POLICY_CHANGED_ONLY = "changed_only"
BOOT_POLICY_ALL = "all"


@dataclass
class ServiceBootEntry:
    service_key: str
    repo_dir: str
    reason: str
    action: str  # boot | mock | skip
    mock_via: str = ""
    cfg: dict = field(default_factory=dict)


@dataclass
class BootPlan:
    policy: str
    changed_repos: set[str]
    discovered: list[ServiceBootEntry] = field(default_factory=list)
    boot: list[ServiceBootEntry] = field(default_factory=list)
    mock: list[ServiceBootEntry] = field(default_factory=list)
    skip: list[ServiceBootEntry] = field(default_factory=list)

    @property
    def boot_configs(self) -> list[dict]:
        return [e.cfg for e in self.boot]


def boot_policy(spec: dict) -> str:
    run = spec.get("run") or {}
    env_override = (os.environ.get("BOB_BOOT_POLICY") or "").strip().lower()
    if env_override in (BOOT_POLICY_ALL, BOOT_POLICY_CHANGED_ONLY):
        return env_override
    policy = (run.get("boot_policy") or BOOT_POLICY_CHANGED_ONLY).strip().lower()
    if policy in (BOOT_POLICY_ALL, "discover_all", "all"):
        return BOOT_POLICY_ALL
    return BOOT_POLICY_CHANGED_ONLY


def boot_confirm_mode(spec: dict) -> str:
    run = spec.get("run") or {}
    if (run.get("boot_confirm") or "").strip().lower() == "never":
        return "never"
    if os.environ.get("BOB_BOOT_YES") == "1" or os.environ.get("BOB_YES") == "1":
        return "never"
    if "--yes" in (spec.get("_cli_flags") or []):
        return "never"
    if not sys.stdin.isatty():
        return "never"
    return (run.get("boot_confirm") or "prompt").strip().lower()


def changed_repos_for_spec(spec: dict) -> set[str]:
    """Repo folder names with ticket-impacted code (impacted.repos + git diff + host)."""
    imp = spec.get("impacted") or {}
    names = {str(n).strip() for n in (imp.get("repos") or []) if str(n).strip()}

    host = host_repo_root()
    if host:
        names.add(host.name)

    try:
        from kafka_discovery import _git_changed_files, _repos_for_ticket

        for repo in _repos_for_ticket(spec):
            if _git_changed_files(repo):
                names.add(repo.name)
    except ImportError:
        pass

    return names


def repos_requiring_fresh_boot(spec: dict) -> set[str]:
    """Repo folder names that need bootRun restart before proof (git-detected code changes).

    Unlike ``changed_repos_for_spec`` (boot plan), this does **not** always include the host
    repo — only repos with ``.java`` / ``.xml`` / ``.properties`` diffs. When a dependency
    repo (e.g. platform-lib) changed, the host primary is included so composite builds reload.
    """
    try:
        from kafka_discovery import _git_changed_files, _repos_for_ticket
    except ImportError:
        return set()

    host = host_repo_root()
    names: set[str] = set()
    changed_resolved: list[Path] = []
    for repo in _repos_for_ticket(spec):
        if _git_changed_files(repo):
            names.add(repo.name)
            changed_resolved.append(repo.resolve())

    if not changed_resolved or not host:
        return names

    host_res = host.resolve()
    host_dirty = host_res in changed_resolved
    dep_dirty = any(r != host_res for r in changed_resolved)
    if host_dirty or dep_dirty:
        names.add(host.name)
    return names


def _is_masterdata_key(service_key: str) -> bool:
    nk = service_key.replace("-", "_").lower()
    return nk in ("masterdata_management", "masterdata") or "masterdata" in nk


def _optional_unset(cfg: dict, env_block: dict) -> bool:
    key = str(cfg.get("service_key") or "")
    svc = (env_block.get("services") or {}).get(key) or cfg
    base_var = svc.get("base_env_var") or cfg.get("base_env_var") or ""
    if not svc.get("optional"):
        return False
    return not (base_var and os.environ.get(base_var, "").strip())


def _classify_entry(
    cfg: dict,
    *,
    policy: str,
    changed_repos: set[str],
    spec: dict,
) -> ServiceBootEntry:
    from service_boot import masterdata_required_for_spec

    key = str(cfg.get("service_key") or cfg.get("repo_dir") or "service")
    repo_dir = str(cfg.get("repo_dir") or "")
    reason = str(cfg.get("reason") or "")
    env_block = spec.get("_env") or {}

    entry = ServiceBootEntry(
        service_key=key,
        repo_dir=repo_dir,
        reason=reason,
        action="boot",
        cfg=dict(cfg),
    )

    if _optional_unset(cfg, env_block):
        entry.action = "skip"
        entry.mock_via = "optional (base URL not set)"
        return entry

    if policy == BOOT_POLICY_ALL:
        return entry

    repo_changed = repo_dir in changed_repos
    if repo_changed:
        return entry

    if _is_masterdata_key(key) and masterdata_required_for_spec(spec):
        entry.action = "mock"
        entry.mock_via = "WireMock + masterdata SQL / Redis config prime"
        return entry

    entry.action = "mock"
    entry.mock_via = "WireMock or existing instance (unchanged repo)"
    return entry


def build_boot_plan(spec: dict) -> BootPlan:
    """Discover all flow peers, then split boot vs mock under boot_policy."""
    from service_boot import _discover_all_boot_configs

    policy = boot_policy(spec)
    changed = changed_repos_for_spec(spec)
    configs = _discover_all_boot_configs(spec)

    discovered: list[ServiceBootEntry] = []
    boot: list[ServiceBootEntry] = []
    mock: list[ServiceBootEntry] = []
    skip: list[ServiceBootEntry] = []

    for cfg in configs:
        entry = _classify_entry(cfg, policy=policy, changed_repos=changed, spec=spec)
        discovered.append(entry)
        if entry.action == "boot":
            boot.append(entry)
        elif entry.action == "mock":
            mock.append(entry)
        else:
            skip.append(entry)

    return BootPlan(
        policy=policy,
        changed_repos=changed,
        discovered=discovered,
        boot=boot,
        mock=mock,
        skip=skip,
    )


def apply_boot_plan_to_spec(spec: dict, plan: BootPlan) -> None:
    spec["_boot_plan"] = plan


def format_boot_plan(plan: BootPlan) -> str:
    lines = [
        f"Boot policy: {plan.policy} (changed repos: {', '.join(sorted(plan.changed_repos)) or 'none'})",
        f"Discovered {len(plan.discovered)} service(s) for this ticket flow:",
    ]
    for entry in plan.discovered:
        if entry.action == "boot":
            tag = "BOOT"
        elif entry.action == "mock":
            tag = f"MOCK ({entry.mock_via})"
        else:
            tag = f"SKIP ({entry.mock_via or 'optional'})"
        base = entry.cfg.get("default_base") or ""
        lines.append(f"  - {entry.repo_dir or entry.service_key}: {tag}")
        if base:
            lines.append(f"      {base}")
        if entry.reason:
            lines.append(f"      ({entry.reason})")
    if plan.policy == BOOT_POLICY_CHANGED_ONLY:
        lines.append("")
        lines.append(
            "Only changed repos will bootRun. Unchanged peers rely on WireMock / masterdata SQL / "
            "Redis prime / an already-running instance."
        )
    return "\n".join(lines)


def confirm_boot_plan(plan: BootPlan, spec: dict) -> BootPlan | None:
    """Show plan and ask user to proceed (default yes). Type 'all' to boot everything discovered."""
    if boot_confirm_mode(spec) == "never":
        return plan

    print()
    print(format_boot_plan(plan))
    print()
    try:
        raw = input(
            "Proceed with this boot plan? [Y/n] (type 'all' to boot every discovered service): "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    if raw in ("n", "no"):
        print("Bob: boot cancelled by user.")
        return None
    if raw == "all":
        plan.policy = BOOT_POLICY_ALL
        plan.boot = [e for e in plan.discovered if e.action != "skip"]
        plan.mock = []
        for entry in plan.boot:
            entry.action = "boot"
            entry.mock_via = ""
        print("Bob: booting all non-skipped discovered services.")
        return plan
    return plan
