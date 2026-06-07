#!/usr/bin/env python3
"""Bob the Builder CLI — ticket-driven local validation for backend services."""
from __future__ import annotations

import json
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
    "onboard": "onboard",
    "bootstrap": "onboard",
    "plugins": "plugins",
    "cursor-plugins": "plugins",
    "meta-review": "meta-review",
    "meta_review": "meta-review",
    "metareview": "meta-review",
    "context-audit": "context-audit",
    "context_audit": "context-audit",
    "contextaudit": "context-audit",
    "memory-budget": "memory-budget",
    "memory_budget": "memory-budget",
    "memorybudget": "memory-budget",
    "chat-hygiene": "chat-hygiene",
    "chat_hygiene": "chat-hygiene",
    "chathygiene": "chat-hygiene",
    "archive-chats": "chat-hygiene",
    "prune-overhead": "prune-overhead",
    "prune_overhead": "prune-overhead",
    "pruneoverhead": "prune-overhead",
    "mcp-audit": "mcp-audit",
    "mcp_audit": "mcp-audit",
    "mcpaudit": "mcp-audit",
    "cursor-hook": "cursor-hook",
    "cursor_hook": "cursor-hook",
    "cursorhook": "cursor-hook",
    "install": "install",
    "install-hooks": "install-hooks",
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
    "verify-docs": "verify-docs",
    "verify-all": "verify-all",
    "verify-fresh-install": "verify-fresh-install",
    "contract-diff": "contract-diff",
    "approve-contract-change": "approve-contract-change",
    "verify-contract-governance": "verify-contract-governance",
    "fresh-install": "verify-fresh-install",
    "start-services": "start-services",
    "boot-services": "start-services",
    "need-service": "need-service",
    "ensure-service": "need-service",
    "discover-services": "discover-services",
    "ensure-peers": "ensure-peers",
    "peers": "ensure-peers",
    "stop-services": "stop-services",
    "services-status": "services-status",
    "kafka": "kafka",
    "graph": "graph",
    "eval": "eval",
    "context": "context",
    "remind": "remind",
    "help": "help",
    "bobhelp": "help",
    "bob-help": "help",
    "version": "version",
    "host": "host",
    "whoami": "host",
    "refresh-samples": "refresh-samples",
    "refresh-examples": "refresh-samples",
    "tools": "tools",
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
    print("  setup              Reconfigure prefs only (onboard runs this on first use)")
    print("  onboard [--dry-run] [--yes] [--smoke]  ONE command: setup + install + Cursor kit + AGENTS.md")
    print("  plugins            Recommended Cursor marketplace plugins (manual install)")
    print("  meta-review [--dry-run] [--days N]  Usage audit -> docs/META_REVIEW.md (monthly; stop hook auto-runs)")
    print("  context-audit [--dry-run]           Cursor context % audit -> docs/CONTEXT_USAGE_AUDIT.md")
    print("  memory-budget [--dry-run] [--json]  Working memory budget -> docs/MEMORY_BUDGET.md")
    print("  chat-hygiene [--dry-run] [--auto]  Archive stale/overflow Cursor chats (never delete)")
    print("  mcp-audit [--dry-run] [--json]       MCP + plugin keep/disable audit -> docs/MCP_AUDIT.md")
    print("  prune-overhead [--dry-run|--apply]   Apply squad policy (after mcp-audit)")
    print("  host               Show BOB_HOST_REPO, workspace clones, deploy/tdd profile")
    print("  refresh-samples    Regenerate assets/examples/sample-validate-output/ (doc bundle)")
    print("  install [--force] [--launchers]  Seed assets/local; install post-commit hook")
    print("  install-hooks [--force]  Install git post-commit hook (auto NEXT.md refresh)")
    print("  cleanup-workspace [--apply]  Merge into bob-the-builder/; remove stale folders")
    print("  init-ticket ID \"Title\" [desc]")
    print("                     Create docs/tdd-runs/<ID>/ + ticket-spec.yaml")
    print("  discover-apis      Scan host orchestration -> BOB_HOME/api-catalog/")
    print("  sync-graph         Refresh platform graph in BOB_HOME")
    print("  validate-ticket ID Run stubs, APIs, DB checks; write evidence/")
    print("  ticket-status ID   Show last run PASS/FAIL + decision trace")
    print("  open-report ID     Print paths to GATE_SUMMARY.md, REPORT.md, REPORT.html, run-summary.json")
    print("  list-tickets       List ticket folders in host repo")
    print("  next [--edit|-e]   Bob product backlog (bob-the-builder/docs/NEXT.md); --edit opens in $EDITOR")
    print("  verify-product     Check feature registry; --update refreshes NEXT.md sections")
    print("  verify-docs        Check docs vs doc-invariants.yaml + CLI (wrong/incomplete product docs)")
    print("  verify-all         Run verify-product, verify-docs, verify-contract-governance")
    print("  verify-contract-governance  Block contract weakening without human approval record")
    print("  contract-diff [--vs REF]    Show contract weakenings vs base (default: main)")
    print("  approve-contract-change --reason \"...\"  Record human approval (type APPROVE)")
    print("  verify-fresh-install  Clean install + non-CC discover-apis (CI fixture; see docs/FRESH_INSTALL_VERIFY.md)")
    print("  remind [--fix]     One-line status; --fix refreshes docs/NEXT.md for you")
    print("  start-services [--ticket ID | --profile NAME] [service-key...]")
    print("                     Gradle bootRun for workspace services (health wait)")
    print("  need-service NAME  Register + bootRun by repo hint (notifications, consents, …)")
    print("  ensure-peers       Scan host code/properties; boot any peer not already up")
    print("  discover-services [--boot]  List peers (properties + code + session registry)")
    print("  stop-services      Stop Bob-started bootRun processes")
    print("  services-status [--profile NAME]  Health + pid for env profile services")
    print("  kafka up|down|status|topics|discover|setup|consume|produce")
    print("                     Flow-aware Kafka (scan impacted code); test --ticket ID")
    print("  graph sync-obsidian [--vault PATH] | graph open")
    print("                     Export KG to Obsidian vault (live graph view)")
    print("  eval baseline|check|update <ticket-id>")
    print("                     Scenario regression vs eval-baseline.json")
    print("  context --ticket ID   CONTEXT_PACK.md (prefs + stale + hybrid KG)")
    print("  tools list|run|backend  Tool bridge (local default; optional MCP)")
    print("  query-graph [kw] [--ticket ID]  Hybrid retrieval -> kg-context-last.md")
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
    print("Bob product backlog: bob-the-builder/docs/NEXT.md  (bob next)")
    print("Doc contract: docs/doc-invariants.yaml  (bob verify-docs)")
    print("You do not memorize workflows — use bob remind, or ask Cursor to commit/push.")


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
            _step("Full dev bootstrap", f"{CLI_SHORT} onboard"),
        ],
        "onboard": [
            _step("Read teammate KT", "bob-the-builder/docs/KT_CURSOR_AND_BOB.md"),
            _step("Smoke validate (optional)", f"{CLI_SHORT} validate-ticket sample-gateway-health-check"),
            _step("Start a real ticket", f'{CLI_SHORT} init-ticket {tid} "Title"'),
        ],
        "meta-review": [
            _step("Open written report", "bob-the-builder/docs/META_REVIEW.md"),
            _step("Context detail", f"{CLI_SHORT} context-audit"),
            _step("Preview without write", f"{CLI_SHORT} meta-review --dry-run"),
        ],
        "context-audit": [
            _step("Open written report", "bob-the-builder/docs/CONTEXT_USAGE_AUDIT.md"),
            _step("Archive hot chats", f"{CLI_SHORT} chat-hygiene --auto"),
            _step("Preview without write", f"{CLI_SHORT} context-audit --dry-run"),
        ],
        "memory-budget": [
            _step("Open written report", "bob-the-builder/docs/MEMORY_BUDGET.md"),
            _step("Per-chat detail", f"{CLI_SHORT} context-audit"),
            _step("Trim MCP overhead", f"{CLI_SHORT} prune-overhead --dry-run"),
        ],
        "mcp-audit": [
            _step("Open written report", "bob-the-builder/docs/MCP_AUDIT.md"),
            _step("Apply policy", f"{CLI_SHORT} prune-overhead --apply"),
            _step("Preview without write", f"{CLI_SHORT} mcp-audit --dry-run"),
        ],
        "prune-overhead": [
            _step("Audit first", f"{CLI_SHORT} mcp-audit"),
            _step("Preview only", f"{CLI_SHORT} prune-overhead --dry-run"),
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
            _step("Boot services if needed (or auto during validate)", f"{CLI_SHORT} start-services --ticket {tid}"),
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


def cmd_onboard(args: list[str]) -> int:
    _banner("onboard")
    from onboard import run_onboard

    return run_onboard(args)


def cmd_plugins(_: list[str]) -> int:
    _banner("plugins")
    from cursor_plugins import run_plugins_flow
    from host_repo import infer_workspace_root, runner_bootstrap_repo

    ws = infer_workspace_root() or runner_bootstrap_repo().resolve().parent
    run_plugins_flow(ws, prominent=True, pause_if_missing=False)
    return 0


def cmd_meta_review(args: list[str]) -> int:
    _banner("meta-review")
    from meta_review import run_meta_review

    return run_meta_review(args)


def cmd_context_audit(args: list[str]) -> int:
    _banner("context-audit")
    from context_audit import run_context_audit

    return run_context_audit(args)


def cmd_memory_budget(args: list[str]) -> int:
    _banner("memory-budget")
    from memory_budget import run_memory_budget

    return run_memory_budget(args)


def cmd_chat_hygiene(args: list[str]) -> int:
    _banner("chat-hygiene")
    from chat_hygiene import run_chat_hygiene_cli

    return run_chat_hygiene_cli(args)


def cmd_prune_overhead(args: list[str]) -> int:
    _banner("prune-overhead")
    from prune_cursor_overhead import run_prune_cursor_overhead

    return run_prune_cursor_overhead(args)


def cmd_mcp_audit(args: list[str]) -> int:
    _banner("mcp-audit")
    from cursor_overhead import run_mcp_audit

    return run_mcp_audit(args)


def cmd_cursor_hook(args: list[str]) -> int:
    from cursor_hook import run_cursor_hook_cli

    return run_cursor_hook_cli(args)


def cmd_install(args: list[str]) -> int:
    _banner("install")
    from install_workspace import install_workspace

    return install_workspace(
        force="--force" in args or "-f" in args,
        workspace_launchers="--launchers" in args,
    )


def cmd_install_hooks(args: list[str]) -> int:
    _banner("install-hooks")
    from git_hooks import install_git_hooks

    ok, msg = install_git_hooks(force="--force" in args or "-f" in args)
    print(msg)
    if ok:
        print("After each git commit, Bob refreshes docs/NEXT.md (extra commit tagged [bob]).")
    return 0 if ok else 1


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
    from graph_obsidian import print_open_instructions, sync_obsidian_vault
    from platform_graph import sync

    ensure_bob_home()
    pg = sync()
    print(f"Platform graph: {pg}")
    vault, stats = sync_obsidian_vault()
    print(f"Obsidian vault: {vault}")
    print(f"  exported: {stats['apis']} APIs, {stats['processors']} processors, {stats['tickets']} tickets")
    print(print_open_instructions(vault))
    return 0


def _parse_ticket_arg(args: list[str]) -> tuple[str | None, list[str]]:
    ticket_id: str | None = None
    rest: list[str] = []
    i = 0
    while i < len(args):
        if args[i] in ("--ticket", "-t") and i + 1 < len(args):
            ticket_id = args[i + 1]
            i += 2
            continue
        rest.append(args[i])
        i += 1
    return ticket_id, rest


def cmd_query_graph(args: list[str]) -> int:
    _banner("query-graph")
    from session_graph import query_slice
    from ticket_spec import load_spec, ticket_dir

    ticket_id, rest = _parse_ticket_arg(args)
    spec = None
    if ticket_id:
        spec = load_spec(ticket_dir(ticket_id))
    kw = " ".join(rest) if rest else (ticket_id or "loan")
    text = query_slice(kw, spec=spec)
    print(text)
    return 0


def cmd_context(args: list[str]) -> int:
    _banner("context")
    from context_assembly import assemble_context_pack
    from ticket_spec import load_spec, ticket_dir

    ticket_id, rest = _parse_ticket_arg(args)
    if not ticket_id:
        _usage("context", "--ticket <ticket-id> [keywords]")
        return 1
    td = ticket_dir(ticket_id)
    spec = load_spec(td)
    kw = " ".join(rest) or f"{ticket_id} {(spec.get('impacted') or {}).get('feature', '')}"
    pack, slice_path, stale = assemble_context_pack(spec, td, kw)
    print(f"CONTEXT_PACK: {pack}")
    print(f"kg-context-last: {slice_path}")
    if stale:
        print("Stale/issues:")
        for s in stale:
            print(f"  [{s.severity}] {s.code}: {s.message}")
    return 0


def cmd_eval(args: list[str]) -> int:
    _banner("eval")
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage:")
        print(f"  {CLI_SHORT} eval baseline <ticket-id>")
        print(f"  {CLI_SHORT} eval check <ticket-id>")
        print(f"  {CLI_SHORT} eval update <ticket-id>")
        return 0
    sub = args[0].lower()
    ticket_id = args[1] if len(args) > 1 else None
    if not ticket_id:
        _usage("eval", "baseline|check|update <ticket-id>")
        return 1
    import json

    from eval_regression import (
        capture_baseline,
        compare_to_baseline,
        write_eval_regression_md,
    )
    from ticket_spec import ticket_dir

    td = ticket_dir(ticket_id)
    rs = td / "run-summary.json"
    if not rs.is_file():
        print(f"Missing {rs} — run: bob validate-ticket {ticket_id}", file=sys.stderr)
        return 1
    run_data = json.loads(rs.read_text(encoding="utf-8"))

    if sub == "baseline":
        path = capture_baseline(td, run_data)
        print(f"Baseline written: {path}")
        return 0
    if sub == "update":
        path = capture_baseline(td, run_data)
        print(f"Baseline updated: {path}")
        return 0
    if sub == "check":
        result = compare_to_baseline(td, run_data)
        write_eval_regression_md(td, result, run_data)
        print(result.message)
        if result.regressions:
            print("Regressions:")
            for r in result.regressions:
                print(f"  - {r}")
        return 0 if result.ok else 1
    print(f"Unknown eval subcommand: {sub}", file=sys.stderr)
    return 1


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


def _run_ticket_python(ticket_dir: Path, cli_flags: list[str] | None = None) -> int:
    from setup_prefs import load_prefs_into_environ

    load_prefs_into_environ()
    os.environ["BOB_HOST_REPO"] = str(repo_root())
    if "--yes" in (cli_flags or []) or "-y" in (cli_flags or []):
        os.environ["BOB_BOOT_YES"] = "1"
    if "--boot-all" in (cli_flags or []):
        os.environ["BOB_BOOT_POLICY"] = "all"
    for line in (ticket_dir / "tdd.env").read_text(encoding="utf-8").splitlines() if (ticket_dir / "tdd.env").exists() else []:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ[k.strip()] = v.strip()
    if sys.platform != "win32":
        search = tdd_root() / "search-logs.sh"
        if _bash_available() and search.exists():
            subprocess.run(["bash", str(search), str(ticket_dir / "ticket-spec.yaml")], cwd=repo_root(), check=False)
    sys.path.insert(0, str(_LIB))
    from run_flow import run

    spec_flags = cli_flags or []
    # Pass CLI flags into run() via ticket-spec load path
    os.environ["BOB_VALIDATE_CLI_FLAGS"] = ",".join(spec_flags)
    return run(ticket_dir, cli_flags=spec_flags)


def cmd_validate_ticket(args: list[str]) -> int:
    _banner("validate-ticket")
    if not args:
        _usage("validate-ticket", "<ticket-id> [--yes] [--boot-all]")
        return 1
    ticket_id = args[0]
    cli_flags = [a for a in args[1:] if a.startswith("-")]
    td = _ticket_dir(ticket_id)
    spec_file = td / "ticket-spec.yaml"
    if not spec_file.exists():
        print(f"Missing {spec_file} — run: {CLI_SHORT} init-ticket {args[0]} \"Title\"", file=sys.stderr)
        return 1
    # Windows: always use Python runner (no bash/WSL required for WireMock, MySQL, APIs).
    if sys.platform == "win32":
        return _run_ticket_python(td, cli_flags=cli_flags)
    script = tdd_root() / "run-tdd.sh"
    env = os.environ.copy()
    env["BOB_HOST_REPO"] = str(repo_root())
    if "--yes" in cli_flags or "-y" in cli_flags:
        env["BOB_BOOT_YES"] = "1"
    if "--boot-all" in cli_flags:
        env["BOB_BOOT_POLICY"] = "all"
    r = subprocess.run(["bash", str(script), str(spec_file)], cwd=repo_root(), env=env)
    if r.returncode not in (126, 127):
        return r.returncode
    print("bash unavailable — using Python runner", file=sys.stderr)
    return _run_ticket_python(td, cli_flags=cli_flags)


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


def cmd_refresh_samples(_: list[str]) -> int:
    _banner("refresh-samples")
    from sample_outputs import refresh_sample_outputs

    refresh_sample_outputs()
    return 0


def cmd_tools(args: list[str]) -> int:
    _banner("tools")
    from tool_bridge import backend_label, list_tool_specs, resolve_backend, run_tool

    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage:")
        print(f"  {CLI_SHORT} tools list              Registered tools + backend")
        print(f"  {CLI_SHORT} tools backend           Show BOB_TOOL_BACKEND")
        print(f"  {CLI_SHORT} tools run <tool-id> [--key value ...]")
        print()
        print("Backends: local (default) | mcp | auto")
        print("Env: BOB_TOOL_BACKEND=local")
        return 0

    sub = args[0].lower()
    rest = args[1:]

    if sub == "backend":
        print(f"BOB_TOOL_BACKEND={backend_label()} (resolved: {resolve_backend().value})")
        return 0

    if sub == "list":
        print(f"Backend: {backend_label()}")
        print()
        for spec in list_tool_specs():
            mcp = f" -> mcp:{spec.mcp_server}/{spec.mcp_tool}" if spec.mcp_tool else ""
            print(f"  {spec.tool_id}")
            print(f"    local: {spec.local_handler}{mcp}")
            if spec.description:
                print(f"    {spec.description}")
        return 0

    if sub == "run":
        if not rest:
            print("Usage: bob tools run <tool-id> [--key value ...]", file=sys.stderr)
            return 1
        tool_id = rest[0]
        kwargs: dict[str, str] = {}
        i = 1
        while i < len(rest):
            if rest[i] == "--" and i + 1 < len(rest):
                key = rest[i + 1].lstrip("-")
                if i + 2 < len(rest) and not rest[i + 2].startswith("-"):
                    kwargs[key] = rest[i + 2]
                    i += 3
                else:
                    i += 2
            elif rest[i].startswith("--") and i + 1 < len(rest):
                kwargs[rest[i][2:]] = rest[i + 1]
                i += 2
            else:
                i += 1
        if tool_id == "mysql.query" and "sql" not in kwargs and i < len(rest):
            kwargs["sql"] = rest[-1]
        result = run_tool(tool_id, **kwargs)
        if result.backend:
            print(f"[{result.backend}]")
        if result.ok:
            print(result.text() or json.dumps(result.data))
            return 0
        print(result.error or result.stderr or "tool failed", file=sys.stderr)
        return 1

    print(f"Unknown tools subcommand: {sub}", file=sys.stderr)
    return 1


def cmd_verify_product(args: list[str]) -> int:
    _banner("verify-product")
    script = tdd_root() / "ci" / "verify-product.py"
    cmd = [sys.executable, str(script)]
    if "--update" in args or "-u" in args or "--fix" in args:
        cmd.append("--update")
    elif "--strict" in args:
        cmd.extend(["--check", "--strict"])
    else:
        cmd.append("--check")
    from bob_home import bob_product_root

    return subprocess.run(cmd, cwd=str(bob_product_root())).returncode


def cmd_verify_docs(args: list[str]) -> int:
    _banner("verify-docs")
    script = tdd_root() / "ci" / "verify-docs.py"
    cmd = [sys.executable, str(script), "--check"]
    from bob_home import bob_product_root

    return subprocess.run(cmd, cwd=str(bob_product_root())).returncode


def cmd_verify_all(args: list[str]) -> int:
    _banner("verify-all")
    rc_product = cmd_verify_product(args)
    rc_docs = cmd_verify_docs(args)
    rc_gov = cmd_verify_contract_governance(args)
    return rc_product or rc_docs or rc_gov


def cmd_verify_contract_governance(args: list[str]) -> int:
    _banner("verify-contract-governance")
    if "--staged" in args:
        from contract_governance import verify_staged_commit

        rc, msg = verify_staged_commit()
        print(msg)
        return rc
    script = tdd_root() / "ci" / "verify-contract-governance.py"
    cmd = [sys.executable, str(script), "--check"]
    if "--base" in args:
        i = args.index("--base")
        if i + 1 < len(args):
            cmd.extend(["--base", args[i + 1]])
    from bob_home import bob_product_root

    return subprocess.run(cmd, cwd=str(bob_product_root())).returncode


def cmd_contract_diff(args: list[str]) -> int:
    _banner("contract-diff")
    from contract_governance import diff_contracts, format_contract_diff_report, product_root, resolve_base_ref

    root = product_root()
    vs = None
    if "--vs" in args:
        i = args.index("--vs")
        if i + 1 < len(args):
            vs = args[i + 1]
    head = "WORKTREE" if "--worktree" in args else "HEAD"
    base = resolve_base_ref(root, vs)
    diff = diff_contracts(root, base_ref=base, head_ref=head)
    print(format_contract_diff_report(diff))
    return 1 if diff.weakened else 0


def cmd_approve_contract_change(args: list[str]) -> int:
    _banner("approve-contract-change")
    import getpass

    try:
        import yaml
    except ImportError:
        print("PyYAML required.", file=sys.stderr)
        return 1

    from contract_governance import (
        diff_contracts,
        format_contract_diff_report,
        product_root,
        write_approval,
    )

    if os.environ.get("CI", "").lower() in ("1", "true", "yes"):
        print("Cannot record contract approval in CI — run locally after review.", file=sys.stderr)
        return 1

    reason = ""
    if "--reason" in args:
        i = args.index("--reason")
        if i + 1 < len(args):
            reason = args[i + 1].strip()
    if len(reason) < 20:
        print('Required: --reason "..." (at least 20 characters explaining impact).', file=sys.stderr)
        return 1

    root = product_root()
    diff = diff_contracts(root, base_ref="HEAD", head_ref="WORKTREE")
    if not diff.weakened:
        print("No contract weakening vs HEAD — approval not needed.")
        return 0

    print(format_contract_diff_report(diff))
    print()

    gov_path = root / "docs" / "contract-governance.yaml"
    gov = yaml.safe_load(gov_path.read_text(encoding="utf-8")) if gov_path.is_file() else {}
    token = str((gov or {}).get("approve_token") or "APPROVE")
    if "--yes" in args or "-y" in args:
        print(
            "Refusing --yes on approve-contract-change. Type the token interactively after review.",
            file=sys.stderr,
        )
        return 1

    try:
        typed = input(f"Type {token} to record intentional contract weakening: ").strip()
    except EOFError:
        print("Interactive approval required.", file=sys.stderr)
        return 1
    if typed != token:
        print("Approval aborted — token mismatch.", file=sys.stderr)
        return 1

    approver = ""
    if "--approver" in args:
        i = args.index("--approver")
        if i + 1 < len(args):
            approver = args[i + 1].strip()
    if not approver:
        approver = getpass.getuser() or os.environ.get("USER", "") or os.environ.get("USERNAME", "human")

    out_path = write_approval(root, reason=reason, approver=approver, diff=diff)
    rel = out_path.relative_to(root)
    print(f"Recorded approval: {rel}")
    print("Stage and commit this file together with your contract changes.")
    return 0


def cmd_verify_fresh_install(args: list[str]) -> int:
    _banner("verify-fresh-install")
    from fresh_install_verify import main as verify_main

    argv = ["verify-fresh-install"]
    if "--quiet" in args or "-q" in args:
        argv.append("--quiet")
    return verify_main(argv)


def cmd_remind(args: list[str]) -> int:
    _banner("remind")
    from product_reminder import remind_message

    fix = "--fix" in args or "-f" in args
    msg, code = remind_message(fix=fix)
    print(msg)
    return code


def _parse_profile_ticket_args(args: list[str]) -> tuple[str | None, str | None, list[str], bool]:
    profile: str | None = None
    ticket_id: str | None = None
    force = "--force" in args or "-f" in args
    rest: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--profile", "-p") and i + 1 < len(args):
            profile = args[i + 1]
            i += 2
            continue
        if a in ("--ticket", "-t") and i + 1 < len(args):
            ticket_id = args[i + 1]
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        rest.append(a)
        i += 1
    return profile, ticket_id, rest, force


def cmd_start_services(args: list[str]) -> int:
    _banner("start-services")
    from setup_prefs import load_prefs_into_environ
    from service_boot import boot_wait_seconds, ensure_services_running, load_env_profile, start_service
    from ticket_spec import load_spec, ticket_dir

    load_prefs_into_environ()
    profile, ticket_id, keys, force = _parse_profile_ticket_args(args)
    if ticket_id:
        spec = load_spec(ticket_dir(ticket_id))
    else:
        from host_repo import host_repo_root

        prof = profile or "local-dsa"
        env_path = host_repo_root() / "deploy/tdd" / f"{prof}.yaml"
        if not env_path.is_file():
            print(f"Missing {env_path} — copy templates/host-deploy-tdd/", file=sys.stderr)
            return 1
        spec = {"env_profile": prof, "_env": load_env_profile(prof), "run": {"boot_wait_seconds": 180}, "impacted": {}}
    wait = boot_wait_seconds(spec)
    env_block = spec.get("_env") or {}
    rc = 0
    if keys:
        for key in keys:
            svc_cfg = (env_block.get("services") or {}).get(key) or {}
            ok, msg = start_service(key, svc_cfg, wait_seconds=wait, force=force)
            print(msg)
            if not ok:
                rc = 1
    else:
        for key, (ok, msg) in ensure_services_running(spec, force=force).items():
            print(msg)
            if not ok:
                rc = 1
    return rc


def cmd_need_service(args: list[str]) -> int:
    _banner("need-service")
    from setup_prefs import load_prefs_into_environ
    from service_boot import need_service

    load_prefs_into_environ()
    if not args or args[0].startswith("-"):
        _usage("need-service", '<hint> [--reason "why"] [--force]')
        return 1
    hint = args[0]
    reason = ""
    force = "--force" in args
    if "--reason" in args:
        i = args.index("--reason")
        if i + 1 < len(args):
            reason = args[i + 1]
    ok, msg = need_service(hint, reason=reason, force=force)
    print(msg)
    return 0 if ok else 1


def cmd_discover_services(args: list[str]) -> int:
    _banner("discover-services")
    from setup_prefs import load_prefs_into_environ
    from service_boot import ensure_services_running
    from service_discovery import discover_for_session, register_required_service
    from ticket_spec import load_spec, ticket_dir

    load_prefs_into_environ()
    spec: dict = {"run": {"boot_wait_seconds": 180}, "impacted": {}}
    profile, ticket_id, _, force = _parse_profile_ticket_args(args)
    if ticket_id:
        spec = load_spec(ticket_dir(ticket_id))
    elif profile:
        from service_boot import load_env_profile

        spec = {"env_profile": profile, "_env": load_env_profile(profile), "run": {"boot_wait_seconds": 180}, "impacted": {}}

    found = discover_for_session(spec)
    if not found:
        from service_boot import caller_service_config

        host_only = caller_service_config(spec)
        if host_only:
            found = [host_only]
            print("No extra peers; host repo is bootable:")
        else:
            print(
                "No services discovered (set BOB_HOST_REPO to a Gradle repo, "
                "BUILDER_WORKSPACE_ROOT, or required-services.yaml)."
            )
            return 0
    print(f"Discovered {len(found)} service(s) for flow:")
    for cfg in found:
        reason = cfg.get("reason", "")
        print(f"  - {cfg.get('repo_dir')}: {cfg.get('default_base')}  ({reason})")

    from boot_plan import build_boot_plan, format_boot_plan

    plan = build_boot_plan(spec)
    print()
    print(format_boot_plan(plan))
    for cfg in found:
        register_required_service(cfg.get("repo_dir") or cfg.get("service_key", ""), reason=cfg.get("reason", ""))

    if "--boot" in args or "-b" in args:
        print()
        rc = 0
        for ok, msg in ensure_services_running(spec, force=force).values():
            print(msg)
            if not ok:
                rc = 1
        return rc
    print()
    print("Boot changed only: python bob.py discover-services --boot")
    print("Boot all discovered: BOB_BOOT_POLICY=all python bob.py discover-services --boot")
    return 0


def cmd_graph(args: list[str]) -> int:
    _banner("graph")
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage:")
        print(f"  {CLI_SHORT} graph sync-obsidian [--vault PATH]")
        print(f"  {CLI_SHORT} graph open [--vault PATH]")
        return 0
    sub = args[0].lower()
    vault_path: str | None = None
    i = 1
    while i < len(args):
        if args[i] in ("--vault", "-v") and i + 1 < len(args):
            vault_path = args[i + 1]
            i += 2
            continue
        i += 1
    from graph_obsidian import obsidian_vault_path, print_open_instructions, sync_obsidian_vault

    if sub in ("open", "path"):
        vault = obsidian_vault_path(vault_path)
        print(print_open_instructions(vault))
        return 0 if vault.is_dir() else 1
    if sub in ("sync-obsidian", "sync", "export", "obsidian"):
        vault, stats = sync_obsidian_vault(vault_path)
        print(f"Obsidian vault: {vault}")
        print(
            f"Exported: {stats['apis']} APIs, {stats['processors']} processors, "
            f"{stats['stubs']} stubs, {stats['tickets']} tickets"
        )
        print(print_open_instructions(vault))
        return 0
    print(f"Unknown graph subcommand: {sub}", file=sys.stderr)
    return cmd_graph(["help"])


def cmd_kafka(args: list[str]) -> int:
    _banner("kafka")
    from setup_prefs import load_prefs_into_environ
    from ticket_spec import load_spec, ticket_dir

    load_prefs_into_environ()
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage:")
        print(f"  {CLI_SHORT} kafka up")
        print(f"  {CLI_SHORT} kafka down")
        print(f"  {CLI_SHORT} kafka status")
        print(f"  {CLI_SHORT} kafka topics")
        print(f"  {CLI_SHORT} kafka consume <topic> [--max N] [--timeout SEC]")
        print(f"  {CLI_SHORT} kafka produce <topic> <fixture.json> [--key PARTITION_KEY]")
        print(f"  {CLI_SHORT} kafka discover --ticket <ticket-id>")
        print(f"  {CLI_SHORT} kafka setup --ticket <ticket-id>")
        print(f"  {CLI_SHORT} kafka test --ticket <ticket-id>")
        return 0

    sub = args[0].lower()
    rest = args[1:]

    from kafka_runtime import (
        apply_kafka_boot_env,
        consume_topic,
        ensure_topic,
        kafka_down,
        kafka_health,
        kafka_up,
        list_topics,
        produce_json,
        run_kafka_scenarios,
    )

    if sub == "up":
        ok, msg = kafka_up()
        if ok:
            apply_kafka_boot_env(None)
        print(msg)
        return 0 if ok else 1
    if sub == "down":
        ok, msg = kafka_down()
        print(msg)
        return 0 if ok else 1
    if sub in ("status", "health"):
        ok, msg = kafka_health()
        print(msg)
        return 0 if ok else 1
    if sub == "topics":
        ok, topics, msg = list_topics()
        print(msg)
        for t in topics:
            print(f"  {t}")
        return 0 if ok else 1
    if sub == "consume":
        if len(rest) < 1:
            _usage("kafka consume", "<topic> [--max N] [--timeout SEC]")
            return 1
        topic = rest[0]
        max_m = 20
        timeout = 15.0
        i = 1
        while i < len(rest):
            if rest[i] == "--max" and i + 1 < len(rest):
                max_m = int(rest[i + 1])
                i += 2
                continue
            if rest[i] == "--timeout" and i + 1 < len(rest):
                timeout = float(rest[i + 1])
                i += 2
                continue
            i += 1
        ok, msgs, detail = consume_topic(topic, max_messages=max_m, timeout_sec=timeout)
        print(detail)
        for m in msgs:
            print(json.dumps(m, indent=2, ensure_ascii=False))
        return 0 if ok else 1
    if sub == "produce":
        if len(rest) < 2:
            _usage("kafka produce", "<topic> <fixture.json> [--key KEY]")
            return 1
        topic = rest[0]
        fixture = rest[1]
        key = None
        if "--key" in rest:
            ki = rest.index("--key")
            if ki + 1 < len(rest):
                key = rest[ki + 1]
        from kafka_runtime import _resolve_fixture_path

        path = _resolve_fixture_path(fixture, None)
        payload = json.loads(path.read_text(encoding="utf-8"))
        ensure_topic(topic)
        ok, msg = produce_json(topic, payload, partition_key=key)
        print(msg)
        return 0 if ok else 1
    def _parse_ticket_id(rest_args: list[str]) -> str | None:
        i = 0
        while i < len(rest_args):
            if rest_args[i] in ("--ticket", "-t") and i + 1 < len(rest_args):
                return rest_args[i + 1]
            i += 1
        return None

    if sub in ("discover", "setup"):
        ticket_id = _parse_ticket_id(rest)
        if not ticket_id:
            _usage(f"kafka {sub}", "--ticket <ticket-id>")
            return 1
        from kafka_discovery import discover_kafka_for_ticket, write_discovery_artifact
        from kafka_setup import prepare_kafka_for_ticket

        spec = load_spec(ticket_dir(ticket_id))
        td = ticket_dir(ticket_id)
        disc = discover_kafka_for_ticket(spec, td)
        art = write_discovery_artifact(td, disc)
        print(f"Bindings: {len(disc.bindings)} | Topics: {', '.join(disc.resolved_topics()) or 'none'}")
        print(f"Wrote {art}")
        for b in disc.bindings:
            t = b.resolved_topic(disc.tenant, disc.environment)
            print(f"  [{b.role}] {t or '—'}  {b.source}  — {b.detail[:60]}")
        if disc.issues:
            print("Issues:")
            for issue in disc.issues:
                print(f"  - {issue}")
        if sub == "setup":
            setup = prepare_kafka_for_ticket(spec, td, discovery=disc)
            print(setup.message)
            for f in setup.fixes_applied:
                print(f"  fix: {f}")
            for issue in setup.issues_remaining:
                print(f"  issue: {issue}")
            return 0 if setup.ok or setup.skipped else 1
        return 0

    if sub == "test":
        ticket_id = _parse_ticket_id(rest)
        if not ticket_id:
            _usage("kafka test", "--ticket <ticket-id>")
            return 1
        from kafka_discovery import discover_kafka_for_ticket

        spec = load_spec(ticket_dir(ticket_id))
        td = ticket_dir(ticket_id)
        disc = discover_kafka_for_ticket(spec, td)
        results = run_kafka_scenarios(spec, td, disc)
        if not results:
            print("No kafka_scenarios in ticket-spec.yaml")
            return 1
        rc = 0
        for r in results:
            st = "PASS" if r.get("pass") else "FAIL"
            print(f"{r.get('id')}: {st} — {'; '.join(r.get('detail') or [])}")
            if not r.get("pass"):
                rc = 1
        return rc

    print(f"Unknown kafka subcommand: {sub}", file=sys.stderr)
    return cmd_kafka(["help"])


def cmd_ensure_peers(args: list[str]) -> int:
    _banner("ensure-peers")
    from setup_prefs import load_prefs_into_environ
    from service_boot import ensure_peers, load_env_profile
    from ticket_spec import load_spec, ticket_dir

    load_prefs_into_environ()
    spec: dict = {"run": {"boot_wait_seconds": 180}, "impacted": {}}
    profile, ticket_id, _, force = _parse_profile_ticket_args(args)
    if ticket_id:
        spec = load_spec(ticket_dir(ticket_id))
    elif profile:
        spec = {
            "env_profile": profile,
            "_env": load_env_profile(profile),
            "run": {"boot_wait_seconds": 180},
            "impacted": {},
        }
    outcomes = ensure_peers(spec, force=force)
    if not outcomes:
        from service_boot import caller_service_config

        if caller_service_config(spec):
            print("Host repo is bootable but nothing was started (all healthy or boot failed).")
        else:
            print(
                "No bootable services (set BOB_HOST_REPO / BUILDER_WORKSPACE_ROOT "
                "or run discover-services)."
            )
        return 0
    rc = 0
    for ok, msg in outcomes.values():
        print(msg)
        if not ok:
            rc = 1
    return rc


def cmd_stop_services(_: list[str]) -> int:
    _banner("stop-services")
    from service_boot import stop_all

    for line in stop_all():
        print(line)
    return 0


def cmd_services_status(args: list[str]) -> int:
    _banner("services-status")
    from setup_prefs import load_prefs_into_environ
    from service_boot import load_env_profile, status_report

    load_prefs_into_environ()
    profile, ticket_id, _, _ = _parse_profile_ticket_args(args)
    if ticket_id:
        from ticket_spec import load_spec, ticket_dir

        spec = load_spec(ticket_dir(ticket_id))
        env_block = spec.get("_env") or {}
    else:
        prof = profile or "local-dsa"
        env_block = load_env_profile(prof)
    print(f"Profile: {profile or ticket_id or 'local-dsa'}")
    for line in status_report(env_block):
        print(line)
    return 0


def cmd_host(_: list[str]) -> int:
    from host_profile import print_host_summary

    print_host_summary()
    return 0


def cmd_version(_: list[str]) -> int:
    print(f"{PRODUCT_NAME} ({CLI_NAME}) v{VERSION}")
    print(TAGLINE)
    return 0


def _next_doc_path() -> Path:
    from bob_home import bob_product_root

    return bob_product_root() / "docs" / "NEXT.md"


def _resolve_editor_argv() -> list[str]:
    import shlex
    import shutil

    for key in ("VISUAL", "EDITOR"):
        raw = os.environ.get(key, "").strip()
        if raw:
            return shlex.split(raw, posix=(os.name != "nt"))
    if os.name == "nt":
        return ["notepad"]
    for fallback in ("nano", "vi"):
        if shutil.which(fallback):
            return [fallback]
    return ["vi"]


def _open_path_in_editor(path: Path) -> int:
    editor = _resolve_editor_argv()
    try:
        proc = subprocess.run([*editor, str(path)], check=False)
        return proc.returncode
    except FileNotFoundError:
        print(f"Editor not found: {editor[0]}", file=sys.stderr)
        print("Set EDITOR or VISUAL (e.g. export EDITOR=nano).", file=sys.stderr)
        return 1


def cmd_next(args: list[str]) -> int:
    path = _next_doc_path()
    if not path.is_file():
        print(f"Missing backlog: {path}", file=sys.stderr)
        print("Create docs/NEXT.md in the bob-the-builder repo.", file=sys.stderr)
        return 1
    if "--edit" in args or "-e" in args:
        print(f"Opening backlog in editor: {path}")
        return _open_path_in_editor(path)
    text = path.read_text(encoding="utf-8")
    print(f"Bob product backlog: {path}")
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
        "onboard": cmd_onboard,
        "plugins": cmd_plugins,
        "meta-review": cmd_meta_review,
        "context-audit": cmd_context_audit,
        "memory-budget": cmd_memory_budget,
        "chat-hygiene": cmd_chat_hygiene,
        "prune-overhead": cmd_prune_overhead,
        "mcp-audit": cmd_mcp_audit,
        "cursor-hook": cmd_cursor_hook,
        "install": cmd_install,
        "install-hooks": cmd_install_hooks,
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
        "verify-docs": cmd_verify_docs,
        "verify-all": cmd_verify_all,
        "verify-contract-governance": cmd_verify_contract_governance,
        "contract-diff": cmd_contract_diff,
        "approve-contract-change": cmd_approve_contract_change,
        "verify-fresh-install": cmd_verify_fresh_install,
        "remind": cmd_remind,
        "start-services": cmd_start_services,
        "need-service": cmd_need_service,
        "discover-services": cmd_discover_services,
        "ensure-peers": cmd_ensure_peers,
        "stop-services": cmd_stop_services,
        "services-status": cmd_services_status,
        "kafka": cmd_kafka,
        "graph": cmd_graph,
        "eval": cmd_eval,
        "context": cmd_context,
        "host": cmd_host,
        "refresh-samples": cmd_refresh_samples,
        "tools": cmd_tools,
        "version": cmd_version,
    }
    h = handlers.get(cmd)
    if not h:
        print(f"Unknown command: {sys.argv[1]}  (try: {CLI_SHORT} help)", file=sys.stderr)
        _print_help()
        return 1
    rc = h(args)
    if cmd not in (
        "help",
        "version",
        "next",
        "verify-product",
        "verify-docs",
        "verify-all",
        "verify-contract-governance",
        "contract-diff",
        "approve-contract-change",
        "verify-fresh-install",
        "remind",
        "plugins",
        "meta-review",
        "context-audit",
        "chat-hygiene",
        "prune-overhead",
        "mcp-audit",
        "cursor-hook",
    ):
        _print_next_steps(cmd, args, rc)
    from product_reminder import print_nudge_after_command

    print_nudge_after_command(cmd)
    from path_shim import ensure_bob_on_path

    ensure_bob_on_path(quiet=False)
    return rc


if __name__ == "__main__":
    sys.exit(main())
