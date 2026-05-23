#!/usr/bin/env python3
"""Bob the Builder CLI — ticket-driven local validation for backend services."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from _yaml_util import repo_root, tdd_root  # noqa: E402
from workspace_env import WORKSPACE_ENV  # noqa: E402

PRODUCT_NAME = "Bob the Builder"
CLI_NAME = "bob-the-builder"
CLI_SHORT = "bob"
VERSION = "1.1.0"
TAGLINE = f"{PRODUCT_NAME} - can we fix it? Yes we can!"

# Canonical command -> handler key (names describe what they do)
CMD_ALIASES: dict[str, str] = {
    # Preferred names
    "setup": "setup",
    "configure": "setup",
    "install": "install",
    "cleanup-workspace": "cleanup-workspace",
    "init-ticket": "init-ticket",
    "validate-ticket": "validate-ticket",
    "verify-ticket": "validate-ticket",
    "discover-apis": "discover-apis",
    "sync-graph": "sync-graph",
    "query-graph": "query-graph",
    "update-graph": "update-graph",
    "ticket-status": "ticket-status",
    "open-report": "open-report",
    "list-tickets": "list-tickets",
    "next": "next",
    "roadmap": "next",
    "backlog": "next",
    "verify-product": "verify-product",
    "help": "help",
    "bobhelp": "help",
    "bob-help": "help",
    "version": "version",
    "s": "setup",
    "i": "init-ticket",
    "r": "validate-ticket",
    "v": "validate-ticket",
    "d": "discover-apis",
    "p": "sync-graph",
    "g": "query-graph",
    "u": "update-graph",
    "st": "ticket-status",
    "o": "open-report",
    "l": "list-tickets",
    "init": "init-ticket",
    "run": "validate-ticket",
    "verify": "validate-ticket",
    "discover": "discover-apis",
    "sync-platform": "sync-graph",
    "query-kg": "query-graph",
    "update-kg": "update-graph",
    "status": "ticket-status",
    "open": "open-report",
    "list": "list-tickets",
    "h": "help",
    "?": "help",
}


def _resolve_cmd(raw: str) -> str:
    c = raw.replace("_", "-").lower()
    return CMD_ALIASES.get(c, c)


def _usage(cmd: str, detail: str) -> None:
    print(f"Usage: {CLI_SHORT} {cmd} {detail}", file=sys.stderr)


def _print_help() -> None:
    print(f"{PRODUCT_NAME} ({CLI_NAME}) v{VERSION}")
    print(TAGLINE)
    print()
    print(f"Usage: {CLI_SHORT} <command> [args]     e.g. python bob.py <command>")
    print()
    print("Commands (name = purpose):")
    print("  setup              First-time: workspace root, MySQL, service URLs")
    print("  install [--force] [--launchers]  Seed assets/local; optional ../bob.py shortcuts")
    print("  cleanup-workspace [--apply]  Merge into bob-the-builder/; remove stale folders")
    print("  init-ticket ID \"Title\" [desc]")
    print("                     Create docs/tdd-runs/<ID>/ + ticket-spec.yaml")
    print("  discover-apis      Scan host orchestration -> BOB_HOME/api-catalog/")
    print("  sync-graph         Refresh platform graph in BOB_HOME")
    print("  validate-ticket ID Run stubs, APIs, DB checks; write evidence/")
    print("  ticket-status ID   Show last run PASS/FAIL + decision trace")
    print("  open-report ID     Print paths to RUN_SUMMARY, REPORT.html")
    print("  list-tickets       List ticket folders in host repo")
    print("  next               Improvement backlog (docs/NEXT.md)")
    print("  verify-product     Check feature registry; --update refreshes NEXT.md sections")
    print("  query-graph [kw]   Context slice for agents -> BOB_LOCAL/agent/")
    print("  update-graph ID [title]  Update session graph")
    print()
    print("Short aliases: s setup | i init-ticket | d discover-apis | r validate-ticket")
    print("               st ticket-status | o open-report | l list-tickets | h help")
    print()
    print(f"Help: {CLI_SHORT} help   (also: {CLI_SHORT} bobhelp, {CLI_SHORT} h, {CLI_SHORT} ?)")
    print()
    print(f"Paths: {WORKSPACE_ENV}, BOB_HOME (assets), BOB_LOCAL (secrets/session)")
    print("Bob never runs git commit or git push.")
    print("Guide: docs/TDD_SYSTEM_DEVELOPER_GUIDE.md")
    print("Backlog: docs/NEXT.md  (bob next)")


def _banner(command: str) -> None:
    print(f"{PRODUCT_NAME} - {command}")


def _ticket_placeholder(args: list[str]) -> str:
    if args and args[0] and "/" not in args[0] and "\\" not in args[0]:
        return args[0]
    return "<ticket-id>"


def _step(label: str, usage: str) -> tuple[str, str]:
    return (label, usage)


def _next_steps(command: str, args: list[str], rc: int) -> list[tuple[str, str]]:
    """Suggested next command(s) after a run (usage lines ready to copy)."""
    if command in ("help", "version"):
        return []

    tid = _ticket_placeholder(args)

    if rc != 0:
        fixes: dict[str, list[tuple[str, str]]] = {
            "setup": [_step("Retry setup", f"{CLI_SHORT} setup")],
            "install": [_step("Fix workspace path first", f"{CLI_SHORT} setup")],
            "init-ticket": [
                _step("Show command help", f'{CLI_SHORT} init-ticket <ticket-id> "Title"'),
            ],
            "validate-ticket": [
                _step("Create ticket folder first", f'{CLI_SHORT} init-ticket {tid} "Title"'),
            ],
            "ticket-status": [_step("List tickets", f"{CLI_SHORT} list-tickets")],
            "open-report": [_step("List tickets", f"{CLI_SHORT} list-tickets")],
            "cleanup-workspace": [_step("Dry run merge plan", f"{CLI_SHORT} cleanup-workspace")],
        }
        return fixes.get(command, [_step("Command help", f"{CLI_SHORT} help")])

    steps: dict[str, list[tuple[str, str]]] = {
        "setup": [
            _step("Seed assets and local folders", f"{CLI_SHORT} install"),
            _step("Optional workspace shortcuts", f"{CLI_SHORT} install --launchers"),
        ],
        "install": [
            _step("Copy host deploy/tdd into a service repo", "see templates/host-deploy-tdd/README.md"),
            _step("Start a ticket (from a host service repo)", f'{CLI_SHORT} init-ticket {tid} "Title"'),
            _step("Migrate old workspace folders", f"{CLI_SHORT} cleanup-workspace --apply"),
        ],
        "cleanup-workspace": (
            [
                _step("Install / refresh product folders", f"{CLI_SHORT} install"),
            ]
            if "--apply" in args or "-f" in args
            else [
                _step("Apply merge and remove stale folders", f"{CLI_SHORT} cleanup-workspace --apply"),
            ]
        ),
        "init-ticket": [
            _step("Agent context (optional)", f"{CLI_SHORT} query-graph {tid}"),
            _step("Refresh API catalog from orchestration", f"{CLI_SHORT} discover-apis"),
            _step("Edit ticket spec, then validate", f"{CLI_SHORT} validate-ticket {tid}"),
        ],
        "query-graph": [
            _step("Create or open a ticket", f'{CLI_SHORT} init-ticket {tid} "Title"'),
            _step("Discover gateway APIs", f"{CLI_SHORT} discover-apis"),
        ],
        "update-graph": [
            _step("Run validation", f"{CLI_SHORT} validate-ticket {tid}"),
        ],
        "discover-apis": [
            _step("Refresh platform graph", f"{CLI_SHORT} sync-graph"),
            _step("Run ticket after editing ticket-spec.yaml", f"{CLI_SHORT} validate-ticket {tid}"),
        ],
        "sync-graph": [
            _step("Discover new APIs (if orchestration changed)", f"{CLI_SHORT} discover-apis"),
            _step("Validate ticket", f"{CLI_SHORT} validate-ticket {tid}"),
        ],
        "validate-ticket": [
            _step("Check PASS/FAIL summary", f"{CLI_SHORT} ticket-status {tid}"),
            _step("Open report paths", f"{CLI_SHORT} open-report {tid}"),
        ],
        "ticket-status": [
            _step("Open HTML / summary paths", f"{CLI_SHORT} open-report {tid}"),
            _step("Re-run after fixes", f"{CLI_SHORT} validate-ticket {tid}"),
        ],
        "open-report": [
            _step("Show run decision trace", f"{CLI_SHORT} ticket-status {tid}"),
            _step("Re-run validation", f"{CLI_SHORT} validate-ticket {tid}"),
        ],
        "list-tickets": [
            _step("New ticket", f'{CLI_SHORT} init-ticket {tid} "Title"'),
            _step("Status for a ticket", f"{CLI_SHORT} ticket-status {tid}"),
        ],
    }
    return steps.get(command, [_step("Full command list", f"{CLI_SHORT} help")])


def _print_next_steps(command: str, args: list[str], rc: int) -> None:
    steps = _next_steps(command, args, rc)
    if not steps:
        return
    print()
    print("--- Next step" + ("s" if len(steps) > 1 else "") + " ---")
    for label, usage in steps:
        print(f"  {label}:")
        print(f"    {usage}")
    print()


def _ticket_dir(arg: str) -> Path:
    from ticket_spec import ticket_dir

    return ticket_dir(arg) if "/" not in arg and "\\" not in arg else Path(arg).parent


def cmd_setup(_: list[str]) -> int:
    _banner("setup")
    from setup_prefs import run_setup_wizard

    return run_setup_wizard(reconfigure=True)


def cmd_install(args: list[str]) -> int:
    _banner("install")
    from install_workspace import install_workspace

    return install_workspace(
        force="--force" in args or "-f" in args,
        workspace_launchers="--launchers" in args,
    )


def cmd_cleanup_workspace(args: list[str]) -> int:
    _banner("cleanup-workspace")
    from cleanup_workspace import cleanup_workspace

    return cleanup_workspace(apply="--apply" in args or "-f" in args)


def cmd_init_ticket(args: list[str]) -> int:
    _banner("init-ticket")
    from bob_home import ensure_bob_home

    ensure_bob_home()
    if len(args) < 2:
        _usage("init-ticket", '<ticket-id> "<title>" [description]')
        return 1
    from ticket_spec import init_spec

    path = init_spec(args[0], args[1], " ".join(args[2:]) if len(args) > 2 else "")
    print(f"Created {path}")
    host_tdd = repo_root() / "deploy" / "tdd"
    if not (host_tdd / "workspace-services.yaml").is_file():
        from host_repo import runner_bootstrap_repo

        tpl = runner_bootstrap_repo() / "templates" / "host-deploy-tdd"
        print()
        print(f"Host glue missing: {host_tdd}/")
        print(f"  Copy template (~2 min): see {tpl / 'README.md'}")
        print(f"  cp {tpl / 'deploy/tdd'}/*.yaml deploy/tdd/")
    from platform_graph import sync as sync_pg

    sync_pg()
    return 0


def cmd_discover_apis(_: list[str]) -> int:
    _banner("discover-apis")
    import tdd_engine

    return tdd_engine.discover_apis()


def cmd_sync_graph(_: list[str]) -> int:
    _banner("sync-graph")
    from bob_home import ensure_bob_home
    from platform_graph import sync

    ensure_bob_home()
    print(f"Platform graph: {sync()}")
    return 0


def cmd_query_graph(args: list[str]) -> int:
    _banner("query-graph")
    from session_graph import query_slice

    print(query_slice(" ".join(args) if args else ""))
    return 0


def cmd_update_graph(args: list[str]) -> int:
    _banner("update-graph")
    from session_graph import update

    update(args[0] if args else "unknown", " ".join(args[1:]) if len(args) > 1 else "")
    print("Session graph updated")
    return 0


def _bash_available() -> bool:
    try:
        return subprocess.run(["bash", "--version"], capture_output=True, timeout=10).returncode == 0
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return False


def _run_ticket_python(ticket_dir: Path) -> int:
    from setup_prefs import load_prefs_into_environ

    load_prefs_into_environ()
    for line in (ticket_dir / "tdd.env").read_text(encoding="utf-8").splitlines() if (ticket_dir / "tdd.env").exists() else []:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ[k.strip()] = v.strip()
    search = tdd_root() / "search-logs.sh"
    if _bash_available() and search.exists():
        subprocess.run(["bash", str(search), str(ticket_dir / "ticket-spec.yaml")], cwd=repo_root(), check=False)
    sys.path.insert(0, str(_LIB))
    from run_flow import run

    return run(ticket_dir)


def cmd_validate_ticket(args: list[str]) -> int:
    _banner("validate-ticket")
    if not args:
        _usage("validate-ticket", "<ticket-id>")
        return 1
    td = _ticket_dir(args[0])
    spec_file = td / "ticket-spec.yaml"
    if not spec_file.exists():
        print(f"Missing {spec_file} — run: {CLI_SHORT} init-ticket {args[0]} \"Title\"", file=sys.stderr)
        return 1
    if sys.platform == "win32" and not _bash_available():
        return _run_ticket_python(td)
    script = tdd_root() / "run-tdd.sh"
    env = os.environ.copy()
    env["BOB_HOST_REPO"] = str(repo_root())
    r = subprocess.run(["bash", str(script), str(spec_file)], cwd=repo_root(), env=env)
    if r.returncode not in (126, 127):
        return r.returncode
    print("bash unavailable — using Python runner", file=sys.stderr)
    return _run_ticket_python(td)


def cmd_list_tickets(_: list[str]) -> int:
    _banner("list-tickets")
    from run_summary import list_tickets

    return list_tickets()


def cmd_ticket_status(args: list[str]) -> int:
    _banner("ticket-status")
    if not args:
        _usage("ticket-status", "<ticket-id>")
        return 1
    from run_summary import print_status

    return print_status(args[0])


def cmd_open_report(args: list[str]) -> int:
    _banner("open-report")
    if not args:
        _usage("open-report", "<ticket-id>")
        return 1
    from run_summary import print_open

    return print_open(args[0])


def cmd_verify_product(args: list[str]) -> int:
    _banner("verify-product")
    script = tdd_root() / "ci" / "verify-product.py"
    cmd = [sys.executable, str(script)]
    if "--update" in args or "-u" in args:
        cmd.append("--update")
    elif "--strict" in args:
        cmd.extend(["--check", "--strict"])
    else:
        cmd.append("--check")
    from bob_home import bob_product_root

    return subprocess.run(cmd, cwd=str(bob_product_root())).returncode


def cmd_version(_: list[str]) -> int:
    print(f"{PRODUCT_NAME} ({CLI_NAME}) v{VERSION}")
    print(TAGLINE)
    return 0


def _next_doc_path() -> Path:
    from bob_home import bob_product_root

    candidates = (
        bob_product_root() / "docs" / "NEXT.md",
        tdd_root().parent / "docs" / "NEXT.md",
    )
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def cmd_next(_: list[str]) -> int:
    path = _next_doc_path()
    if not path.is_file():
        print(f"Missing backlog: {path}", file=sys.stderr)
        print("Create docs/NEXT.md in the bob-the-builder repo.", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    print(f"Improvement backlog: {path}")
    print()
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, OSError, ValueError):
        pass
    print(text, end="" if text.endswith("\n") else "\n")
    return 0


def _load_prefs_early() -> None:
    from host_repo import infer_workspace_root
    from setup_prefs import load_prefs_into_environ
    from workspace_env import set_workspace_env, workspace_env_value

    load_prefs_into_environ()
    if not workspace_env_value():
        inferred = infer_workspace_root()
        if inferred:
            set_workspace_env(str(inferred))
    from bob_home import ensure_bob_home

    ensure_bob_home(quiet=True)


def main() -> int:
    _load_prefs_early()
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        _print_help()
        return 0 if len(sys.argv) >= 2 else 1
    if sys.argv[1] in ("--version", "-V", "version"):
        return cmd_version([])

    cmd = _resolve_cmd(sys.argv[1])
    args = sys.argv[2:]
    handlers = {
        "help": lambda a: (_print_help() or 0),
        "setup": cmd_setup,
        "install": cmd_install,
        "cleanup-workspace": cmd_cleanup_workspace,
        "init-ticket": cmd_init_ticket,
        "discover-apis": cmd_discover_apis,
        "sync-graph": cmd_sync_graph,
        "query-graph": cmd_query_graph,
        "update-graph": cmd_update_graph,
        "validate-ticket": cmd_validate_ticket,
        "list-tickets": cmd_list_tickets,
        "ticket-status": cmd_ticket_status,
        "open-report": cmd_open_report,
        "next": cmd_next,
        "verify-product": cmd_verify_product,
        "version": cmd_version,
    }
    h = handlers.get(cmd)
    if not h:
        print(f"Unknown command: {sys.argv[1]}  (try: {CLI_SHORT} help)", file=sys.stderr)
        _print_help()
        return 1
    rc = h(args)
    if cmd not in ("help", "version", "next", "verify-product"):
        _print_next_steps(cmd, args, rc)
    from path_shim import ensure_bob_on_path

    ensure_bob_on_path(quiet=False)
    return rc


if __name__ == "__main__":
    sys.exit(main())
