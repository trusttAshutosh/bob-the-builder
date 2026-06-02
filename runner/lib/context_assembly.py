"""Assemble agent context: preferences, stale warnings, hybrid retrieval."""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _yaml_util import load
from bob_home import agent_dir, api_catalog_dir, platform_graph_path
from graph_retrieval import hybrid_query, write_context_slice
from host_repo import host_repo_root
from setup_prefs import load_all_prefs
from ticket_spec import spec_path


@dataclass
class StaleIssue:
    severity: str  # warn | error
    code: str
    message: str
    fix: str = ""


def load_bob_preferences() -> dict[str, str]:
    prefs = load_all_prefs()
    keys = {
        "BUILDER_WORKSPACE_ROOT",
        "BOB_HOME",
        "BOB_LOCAL",
        "BOB_HOST_REPO",
        "LOGS_DIR",
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_USER",
        "REDIS_HOST",
        "REDIS_PORT",
        "BOB_KAFKA_BOOTSTRAP",
        "BOB_OBSIDIAN_VAULT",
    }
    for k in prefs:
        if k.endswith("_BASE"):
            keys.add(k)
    return {k: prefs.get(k) or os.environ.get(k, "") for k in keys if (prefs.get(k) or os.environ.get(k))}


def _parse_graph_updated_at(plat: dict) -> float:
    raw = (plat.get("meta") or {}).get("updated_at", "")
    try:
        return time.mktime(time.strptime(raw, "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, OSError):
        return 0.0


def _newest_orchestration_mtime(repo: Path) -> float:
    orch = repo / "deploy/application/orchestration"
    if not orch.is_dir():
        return 0.0
    latest = 0.0
    for xml in orch.rglob("*.xml"):
        try:
            latest = max(latest, xml.stat().st_mtime)
        except OSError:
            pass
    return latest


def _git_branch(repo: Path) -> str:
    try:
        from tool_bridge import run_tool

        result = run_tool("git.branch", cwd=str(repo))
        if result.ok and result.data:
            return str(result.data).strip()
    except ImportError:
        pass
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return (r.stdout or "").strip()
    except Exception:
        return ""


def detect_stale(spec: dict, ticket_dir: Path) -> list[StaleIssue]:
    issues: list[StaleIssue] = []
    repo = host_repo_root()
    plat_path = platform_graph_path()
    plat = load(plat_path) if plat_path.is_file() else {}
    graph_ts = _parse_graph_updated_at(plat)

    if repo and repo.is_dir():
        orch_ts = _newest_orchestration_mtime(repo)
        if orch_ts > graph_ts + 60:
            issues.append(
                StaleIssue(
                    "warn",
                    "graph_behind_orchestration",
                    "Orchestration XML changed after last platform-graph sync.",
                    "bob sync-graph",
                )
            )

    spec_file = spec_path(ticket_dir)
    if spec_file.is_file() and plat_path.is_file():
        try:
            if spec_file.stat().st_mtime > plat_path.stat().st_mtime + 1:
                issues.append(
                    StaleIssue(
                        "warn",
                        "spec_newer_than_graph",
                        "ticket-spec.yaml is newer than platform-graph.yaml.",
                        "bob sync-graph",
                    )
                )
        except OSError:
            pass

    tid = (spec.get("ticket") or {}).get("id") or ticket_dir.name
    from session_graph import session_path

    sp = session_path()
    if sp.is_file():
        sess = load(sp)
        br = _git_branch(repo) if repo else ""
        saved = (sess.get("branches") or {}).get(br) or {}
        if saved.get("ticket_id") and saved.get("ticket_id") != tid:
            issues.append(
                StaleIssue(
                    "warn",
                    "branch_ticket_mismatch",
                    f"Branch `{br}` session last ticket was `{saved.get('ticket_id')}`, now `{tid}`.",
                    "",
                )
            )
        if br and saved.get("ticket_id") == tid:
            last_branch = next(
                (t.get("branch") for t in (sess.get("tasks") or []) if t.get("ticket_id") == tid),
                "",
            )
            if last_branch and last_branch != br:
                issues.append(
                    StaleIssue(
                        "warn",
                        "ticket_branch_changed",
                        f"Ticket `{tid}` previously run on `{last_branch}`, now on `{br}`.",
                        "",
                    )
                )

    cat = api_catalog_dir() / "apis"
    imp_apis = (spec.get("impacted") or {}).get("gateway_apis") or []
    if imp_apis and cat.is_dir() and not any(cat.glob("*.yaml")):
        issues.append(
            StaleIssue(
                "warn",
                "catalog_empty",
                "API catalog is empty but ticket lists gateway_apis.",
                "bob discover-apis",
            )
        )

    from host_profile import primary_base_env_var, primary_default_base, resolved_primary_base

    base_var = primary_base_env_var(spec)
    prefs = load_bob_preferences()
    if not resolved_primary_base(spec):
        issues.append(
            StaleIssue(
                "error",
                "missing_primary_base",
                f"{base_var} not set and no default_base in deploy/tdd profile.",
                "bob setup",
            )
        )
    elif not prefs.get(base_var) and not os.environ.get(base_var):
        issues.append(
            StaleIssue(
                "warn",
                "primary_base_env_default",
                f"{base_var} not set — validate will use profile default_base ({primary_default_base(spec)}).",
                "bob setup",
            )
        )
    if imp_apis and not prefs.get("LOGS_DIR"):
        issues.append(
            StaleIssue(
                "warn",
                "missing_logs_dir",
                "LOGS_DIR not set — log-search step will be skip-only.",
                "bob setup",
            )
        )

    return issues


def _format_preferences(prefs: dict[str, str]) -> list[str]:
    lines = ["## Your Bob preferences (from user.env)", ""]
    if not prefs:
        lines.append("_No preferences loaded — run `bob setup`._")
        return lines
    for k, v in sorted(prefs.items()):
        if "PASS" in k.upper() and k == "MYSQL_PASS":
            lines.append(f"- **{k}:** (set)")
        else:
            lines.append(f"- **{k}:** `{v}`")
    lines.append("")
    return lines


def _format_stale(issues: list[StaleIssue]) -> list[str]:
    if not issues:
        return ["## Staleness checks", "", "All checks passed (graph, branch, prefs).", ""]
    lines = ["## Staleness checks", ""]
    for i in issues:
        icon = "WARN" if i.severity == "warn" else "FAIL"
        lines.append(f"- **{icon}** `{i.code}`: {i.message}")
        if i.fix:
            lines.append(f"  - Fix: `{i.fix}`")
    lines.append("")
    return lines


def assemble_context_pack(
    spec: dict,
    ticket_dir: Path,
    keywords: str,
    *,
    max_retrieval_lines: int = 100,
) -> tuple[Path, Path, list[StaleIssue]]:
    """
    Write CONTEXT_PACK.md (ticket + agent) and refresh kg-context-last.md.
    Returns (ticket_pack_path, agent_slice_path, stale_issues).
    """
    prefs = load_bob_preferences()
    stale = detect_stale(spec, ticket_dir)
    retrieval = hybrid_query(keywords, spec, max_lines=max_retrieval_lines)
    slice_path = write_context_slice(keywords, spec, max_lines=max_retrieval_lines)

    run_cfg = spec.get("run") or {}
    postman = run_cfg.get("postman") or {}
    lines = [
        "# Bob context pack",
        "",
        f"Ticket: `{(spec.get('ticket') or {}).get('id', ticket_dir.name)}`",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    lines.extend(_format_preferences(prefs))
    lines.extend(_format_stale(stale))

    if postman:
        lines.extend(
            [
                "## Postman defaults (ticket-spec)",
                "",
                f"- local gateway: `{postman.get('local_gateway_base', '')}`",
                f"- QA gateway: `{postman.get('qa_gateway_base', '')}`",
                "",
            ]
        )

    lines.extend(["## Hybrid retrieval (ranked)", "", retrieval])

    pack = ticket_dir / "CONTEXT_PACK.md"
    pack.write_text("\n".join(lines), encoding="utf-8")

    agent_pack = agent_dir() / "context-pack-last.md"
    agent_pack.parent.mkdir(parents=True, exist_ok=True)
    agent_pack.write_text(pack.read_text(encoding="utf-8"), encoding="utf-8")

    return pack, slice_path, stale
