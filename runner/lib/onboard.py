"""bob onboard — one-command developer bootstrap (Bob + Cursor templates)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from host_repo import infer_workspace_root, runner_bootstrap_repo

ONBOARDING_DIR = "templates/onboarding"

WORKSPACE_FOLDERS: list[tuple[str, str]] = [
    (".", "novopay (root)"),
    ("bob-the-builder", "bob-the-builder"),
    ("novopay-platform-creditcard-management", "credit-card-management"),
    ("novopay-platform-lib", "platform-lib"),
    ("novopay-platform-api-gateway", "api-gateway"),
    ("novopay-platform-actor", "actor"),
]


@dataclass(frozen=True)
class PlannedWrite:
    label: str
    dest: Path
    action: str
    reason: str = ""


def template_root() -> Path:
    root = runner_bootstrap_repo() / ONBOARDING_DIR
    if not root.is_dir():
        raise FileNotFoundError(f"Missing onboarding bundle: {root}")
    return root


def resolve_workspace_root() -> Path:
    ws = infer_workspace_root()
    if ws:
        return ws
    return runner_bootstrap_repo().resolve().parent


def substitute(text: str, workspace: Path) -> str:
    ws = str(workspace.resolve())
    return (
        text.replace("{{WORKSPACE_ROOT}}", ws)
        .replace("{{WORKSPACE_NAME}}", workspace.name)
    )


def render_workspace_json(workspace: Path) -> str:
    folders: list[dict[str, str]] = []
    for rel, name in WORKSPACE_FOLDERS:
        sub = workspace if rel == "." else workspace / rel
        if sub.is_dir():
            folders.append({"name": name, "path": rel})
    doc = {
        "folders": folders,
        "settings": {"files.autoSave": "afterDelay"},
    }
    return json.dumps(doc, indent=2) + "\n"


def cursor_home() -> Path:
    return Path.home() / ".cursor"


def check_prerequisites() -> list[tuple[str, str, str]]:
    """Return (name, status ok|warn|fail, detail)."""
    rows: list[tuple[str, str, str]] = []
    rows.append(("Python", "ok", sys.executable))
    git = shutil.which("git")
    rows.append(("Git", "ok" if git else "fail", git or "not found"))
    java = shutil.which("java")
    rows.append(("JDK", "ok" if java else "warn", java or "optional until Gradle bootRun"))
    mysql = shutil.which("mysql") or shutil.which("mysql.exe")
    rows.append(
        (
            "MySQL client",
            "ok" if mysql else "warn",
            mysql or "optional until validate-ticket",
        )
    )
    return rows


def prefs_exist() -> bool:
    from setup_prefs import _bootstrap_prefs_path, load_all_prefs
    from workspace_env import WORKSPACE_ENV

    prefs = load_all_prefs()
    return bool(prefs.get(WORKSPACE_ENV, "").strip()) or _bootstrap_prefs_path().is_file()


def plan_writes(workspace: Path, *, force: bool = False) -> list[PlannedWrite]:
    plans: list[PlannedWrite] = []

    rule_dest = cursor_home() / "rules" / "novopay-orchestrator.mdc"
    if rule_dest.is_file() and not force:
        plans.append(PlannedWrite("Cursor orchestrator rule", rule_dest, "skip", "exists"))
    else:
        plans.append(PlannedWrite("Cursor orchestrator rule", rule_dest, "write"))

    plans.append(PlannedWrite("Cursor hooks.json", cursor_home() / "hooks.json", "merge"))
    plans.append(
        PlannedWrite(
            "Cursor hook runner (single silent script)",
            cursor_home() / "hooks" / "bob-hook-runner.sh",
            "write",
        )
    )
    plans.append(PlannedWrite("Bob path pointer", cursor_home() / "hooks" / ".bob-py", "write"))

    ws_file = workspace / "novopay.code-workspace"
    if ws_file.is_file() and not force:
        plans.append(PlannedWrite("Multi-root workspace file", ws_file, "skip", "exists"))
    else:
        plans.append(PlannedWrite("Multi-root workspace file", ws_file, "write"))

    agents = workspace / "AGENTS.md"
    if agents.is_file() and not force:
        plans.append(PlannedWrite("Workspace AGENTS.md stub", agents, "skip", "exists"))
    else:
        plans.append(PlannedWrite("Workspace AGENTS.md stub", agents, "write"))

    plans.append(PlannedWrite("Bob setup wizard", Path("(interactive)"), "command"))
    plans.append(PlannedWrite("Bob install + git hooks", Path("(bob install)"), "command"))
    return plans


def merge_hooks_json(dest: Path, template_text: str) -> str:
    from cursor_hook import merge_hooks_json as _merge

    return _merge(dest, template_text)


def print_plan(
    workspace: Path,
    prereqs: list[tuple[str, str, str]],
    plans: list[PlannedWrite],
    *,
    dry_run: bool,
) -> None:
    print("=== bob onboard ===")
    print(f"Workspace root: {workspace}")
    if dry_run:
        print("(dry-run - no changes will be made)")
    print()
    print("Prerequisites:")
    for name, status, detail in prereqs:
        mark = {"ok": "OK", "warn": "WARN", "fail": "FAIL"}.get(status, "?")
        print(f"  [{mark}] {name}: {detail}")
    print()
    print("Planned actions:")
    for p in plans:
        suffix = f" ({p.reason})" if p.reason else ""
        print(f"  - {p.label}: {p.action}{suffix} -> {p.dest}")
    from cursor_plugins import print_plugin_notice

    print_plugin_notice(prominent=False, workspace=workspace)


def confirm_apply(*, yes: bool, dry_run: bool) -> bool:
    if dry_run:
        return False
    if yes:
        return True
    try:
        raw = input("Apply onboarding changes? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return raw in ("y", "yes")


def apply_templates(workspace: Path, *, force: bool = False) -> None:
    bundle = template_root()
    sub = substitute

    rule_src = bundle / "cursor" / "novopay-orchestrator.mdc"
    rule_dest = cursor_home() / "rules" / "novopay-orchestrator.mdc"
    if force or not rule_dest.is_file():
        rule_dest.parent.mkdir(parents=True, exist_ok=True)
        rule_dest.write_text(sub(rule_src.read_text(encoding="utf-8"), workspace), encoding="utf-8")
        print(f"Wrote {rule_dest}")

    from cursor_hook import deploy_cursor_hooks

    for path in deploy_cursor_hooks(workspace, force=force):
        if path.name == "hooks.json":
            print(f"Merged {path}")
        else:
            print(f"Wrote {path}")
    hooks_dir = cursor_home() / "hooks"
    for legacy in ("orchestrator-hygiene-stop.sh", "session-chat-hygiene.sh"):
        if not (hooks_dir / legacy).is_file():
            print(f"Removed legacy hook {legacy}")

    ws_dest = workspace / "novopay.code-workspace"
    if force or not ws_dest.is_file():
        ws_dest.write_text(render_workspace_json(workspace), encoding="utf-8")
        print(f"Wrote {ws_dest}")

    agents_dest = workspace / "AGENTS.md"
    if force or not agents_dest.is_file():
        stub = (bundle / "novopay" / "AGENTS.md.stub").read_text(encoding="utf-8")
        agents_dest.write_text(sub(stub, workspace), encoding="utf-8")
        print(f"Wrote {agents_dest}")

    from cursor_plugins import deploy_workspace_plugin_doc

    ws_doc = deploy_workspace_plugin_doc(workspace, force=force)
    if ws_doc:
        print(f"Wrote {ws_doc}")


def open_cursor_workspace(workspace: Path) -> None:
    ws_file = workspace / "novopay.code-workspace"
    if not ws_file.is_file():
        return
    exe = shutil.which("cursor") or shutil.which("code")
    if not exe:
        print(f"Open manually: {ws_file}")
        return
    subprocess.Popen(
        [exe, str(ws_file)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"Launched: {exe} {ws_file}")


def run_smoke_validate() -> int:
    bob_py = runner_bootstrap_repo() / "bob.py"
    print("Smoke: validate-ticket sample-gateway-health-check")
    proc = subprocess.run(
        [sys.executable, str(bob_py), "validate-ticket", "sample-gateway-health-check"],
        check=False,
    )
    return proc.returncode


def run_onboard(args: list[str]) -> int:
    dry_run = "--dry-run" in args
    yes = "--yes" in args or "-y" in args
    skip_setup = "--skip-setup" in args
    skip_smoke = "--skip-smoke" in args
    run_smoke = "--smoke" in args
    force = "--force" in args or "-f" in args
    no_launchers = "--no-launchers" in args
    reconfigure = "--reconfigure" in args
    no_cursor = "--skip-cursor-open" in args

    prereqs = check_prerequisites()
    if any(status == "fail" for _, status, _ in prereqs):
        print("Fix failed prerequisites before onboarding.", file=sys.stderr)
        return 1

    workspace = resolve_workspace_root()
    print_plan(workspace, prereqs, plan_writes(workspace, force=force), dry_run=dry_run)

    if dry_run:
        return 0

    if not confirm_apply(yes=yes, dry_run=dry_run):
        print("Onboarding cancelled.")
        return 1

    if not skip_setup:
        from setup_prefs import run_setup_wizard

        rc = run_setup_wizard(reconfigure=reconfigure or not prefs_exist())
        if rc != 0:
            return rc
    else:
        from setup_prefs import load_prefs_into_environ

        load_prefs_into_environ()

    from git_hooks import install_git_hooks
    from install_workspace import install_workspace

    rc = install_workspace(force=force, workspace_launchers=not no_launchers)
    if rc != 0:
        return rc
    ok, msg = install_git_hooks(force=force)
    print(msg)
    if not ok:
        return 1

    apply_templates(workspace, force=force)

    if not no_cursor:
        open_cursor_workspace(workspace)

    if run_smoke:
        return run_smoke_validate()

    if not skip_smoke:
        try:
            raw = input("Run smoke validate-ticket now? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            raw = ""
        if raw in ("y", "yes"):
            return run_smoke_validate()

    from cursor_plugins import print_plugin_notice

    print()
    print("Onboarding complete. Read: bob-the-builder/docs/KT_CURSOR_AND_BOB.md")
    print_plugin_notice(prominent=True, workspace=workspace)
    return 0
