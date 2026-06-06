"""Recommended Cursor marketplace plugins for the Novopay + Bob workflow."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from host_repo import runner_bootstrap_repo


@dataclass(frozen=True)
class RecommendedPlugin:
    name: str
    marketplace_search: str
    tier: str  # recommended | optional
    summary: str
    helps_with: tuple[str, ...]


RECOMMENDED_PLUGINS: tuple[RecommendedPlugin, ...] = (
    RecommendedPlugin(
        name="Superpowers",
        marketplace_search="superpowers",
        tier="recommended",
        summary="Plan and prove discipline before and after Bob runs.",
        helps_with=(
            "Gate 1 Plan: /brainstorming and /writing-plans before you code",
            "Gate 3 Prove: /verification-before-completion after bob validate-ticket",
            "Complements .cursor/skills/ticket-breakdown-planning (Jira-ready breakdown)",
        ),
    ),
    RecommendedPlugin(
        name="Cursor Team Kit",
        marketplace_search="cursor team kit",
        tier="recommended",
        summary="Review, CI, and ship skills for Gate 4 and PR hygiene.",
        helps_with=(
            "Gate 4 Ship: /review-and-ship, /new-branch-and-pr, /make-pr-easy-to-review",
            "CI loops: /fix-ci and /loop-on-ci when checks fail",
            "Quality pass: /thermo-nuclear-code-quality-review before large diffs",
        ),
    ),
    RecommendedPlugin(
        name="Continual Learning",
        marketplace_search="continual learning",
        tier="recommended",
        summary="Keeps AGENTS.md in sync so Bob sessions do not re-learn prefs every chat.",
        helps_with=(
            "Updates novopay/AGENTS.md on agent stop (Learned sections)",
            "Works with weekly /workflow-from-chats hygiene from the orchestrator stop hook",
            "Pairs with ~/.cursor/rules/novopay-orchestrator.mdc (hard rules stay separate)",
        ),
    ),
    RecommendedPlugin(
        name="Postman",
        marketplace_search="postman",
        tier="optional",
        summary="Only if you use Postman Cloud; Bob already writes local collections per ticket.",
        helps_with=(
            "Optional cloud sync for collections Bob generates under docs/tdd-runs/<id>/postman/",
            "Not required for bob validate-ticket or local TDD",
        ),
    ),
)

DOC_REL = "docs/CURSOR_PLUGINS.md"
WORKSPACE_DOC_REL = ".cursor/CURSOR_PLUGINS.md"


def product_doc_path() -> Path:
    return runner_bootstrap_repo() / DOC_REL


def _header_lines(*, prominent: bool) -> list[str]:
    if prominent:
        bar = "=" * 78
        return [
            bar,
            "ACTION NEEDED - Cursor marketplace (Bob cannot install these for you)",
            bar,
            "",
            "Install the plugins below so Cursor agents can use the skills and workflows",
            "this squad documents in the Bob repo. Bob, rules, and .cursor/skills/ work without",
            "them; plugins add structured plan, review, CI, and durable memory on top.",
            "",
            "How: Cursor > Extensions (marketplace) > search each name below > Install.",
            "",
        ]
    return [
        "Recommended Cursor plugins (install manually in marketplace):",
        "Bob works without them; they unlock plan/review/CI/memory workflows in this repo.",
        "",
    ]


def format_plugin_notice(*, prominent: bool = False, workspace: Path | None = None) -> str:
    lines = _header_lines(prominent=prominent)
    for plug in RECOMMENDED_PLUGINS:
        tier = "RECOMMENDED" if plug.tier == "recommended" else "OPTIONAL"
        lines.append(f"  [{tier}] {plug.name}")
        lines.append(f"           Search: \"{plug.marketplace_search}\"")
        lines.append(f"           {plug.summary}")
        for item in plug.helps_with:
            lines.append(f"           - {item}")
        lines.append("")

    bob_doc = product_doc_path()
    lines.append(f"Full reference: {bob_doc}")
    if workspace:
        ws_doc = workspace / WORKSPACE_DOC_REL
        lines.append(f"Workspace copy: {ws_doc}")
    lines.append("Re-show anytime: bob plugins")
    if prominent:
        lines.append("=" * 78)
    return "\n".join(lines)


def print_plugin_notice(*, prominent: bool = False, workspace: Path | None = None) -> None:
    print()
    print(format_plugin_notice(prominent=prominent, workspace=workspace))
    print()


def plugin_doc_markdown() -> str:
    lines = [
        "# Cursor plugins for Novopay + Bob",
        "",
        "Bob cannot install Cursor marketplace plugins for you. Install these once per",
        "machine so agents can use the skills and slash-commands referenced in this repo.",
        "",
        "Bob, `novopay-orchestrator.mdc`, and `.cursor/skills/` work without plugins.",
        "Plugins add structured **Plan**, **review/CI**, and **memory** on top of Bob proof.",
        "",
        "## How to install",
        "",
        "1. Open **Cursor** > **Extensions** (marketplace).",
        "2. Search each plugin name below.",
        "3. Click **Install**.",
        "4. Reload Cursor if prompted.",
        "",
        "Re-show this list in terminal: `bob plugins`",
        "",
        "## Recommended",
        "",
    ]
    for plug in RECOMMENDED_PLUGINS:
        if plug.tier != "recommended":
            continue
        lines.append(f"### {plug.name}")
        lines.append("")
        lines.append(f"**Marketplace search:** `{plug.marketplace_search}`")
        lines.append("")
        lines.append(plug.summary)
        lines.append("")
        lines.append("**Helps with workflows in this repo:**")
        for item in plug.helps_with:
            lines.append(f"- {item}")
        lines.append("")

    lines.extend(["## Optional", ""])
    for plug in RECOMMENDED_PLUGINS:
        if plug.tier != "optional":
            continue
        lines.append(f"### {plug.name}")
        lines.append("")
        lines.append(f"**Marketplace search:** `{plug.marketplace_search}`")
        lines.append("")
        lines.append(plug.summary)
        lines.append("")
        for item in plug.helps_with:
            lines.append(f"- {item}")
        lines.append("")

    lines.extend(
        [
            "## Novopay skills (no plugin required)",
            "",
            "Canonical skills live at `.cursor/skills/`:",
            "",
            "| Skill | Use when |",
            "|-------|----------|",
            "| `ticket-breakdown-planning` | Jira-ready breakdown, epic vs story |",
            "| `cc-backend-test-generation` | CC unit/journey tests |",
            "| `generate-test-plan-change-flow-based` | QA test plans with API + DB matrices |",
            "",
            "See also: [KT_CURSOR_AND_BOB.md](../docs/KT_CURSOR_AND_BOB.md)",
        ]
    )
    return "\n".join(lines) + "\n"


def ensure_product_doc() -> Path:
    path = product_doc_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = plugin_doc_markdown()
    if not path.is_file() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
    return path


def deploy_workspace_plugin_doc(workspace: Path, *, force: bool = False) -> Path | None:
    ensure_product_doc()
    dest = workspace / WORKSPACE_DOC_REL
    if dest.is_file() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(plugin_doc_markdown(), encoding="utf-8")
    return dest


def recommended_plugin_status() -> list[tuple[RecommendedPlugin, bool]]:
    """Return (plugin, installed?) for each recommended-tier plugin."""
    from cursor_overhead import discover_plugins

    by_name = {record.name: record for record in discover_plugins()}
    rows: list[tuple[RecommendedPlugin, bool]] = []
    for plug in RECOMMENDED_PLUGINS:
        if plug.tier != "recommended":
            continue
        record = by_name.get(plug.name)
        rows.append((plug, bool(record and record.installed)))
    return rows


def format_plugin_status_summary() -> tuple[list[str], list[str]]:
    lines = ["Cursor plugin status (marketplace - install manually if MISSING):"]
    missing: list[str] = []
    for plug, installed in recommended_plugin_status():
        mark = "OK" if installed else "MISSING"
        lines.append(f"  [{mark}] {plug.name}  (search: \"{plug.marketplace_search}\")")
        if not installed:
            missing.append(plug.name)
    if not missing:
        lines.append("  All recommended plugins detected on this machine.")
    return lines, missing


def run_plugins_flow(
    workspace: Path | None = None,
    *,
    prominent: bool = True,
    pause_if_missing: bool = False,
) -> list[str]:
    """Same work as `bob plugins`: docs, status, install guide. Returns missing plugin names."""
    ensure_product_doc()
    if workspace is not None:
        deploy_workspace_plugin_doc(workspace, force=False)

    status_lines, missing = format_plugin_status_summary()
    print()
    print("=== bob plugins (integrated) ===")
    for line in status_lines:
        print(line)
    print_plugin_notice(prominent=prominent, workspace=workspace)

    if pause_if_missing and missing:
        print("Cursor should be open. Install MISSING plugins from the marketplace list above.")
        try:
            input("Press Enter when done (or Ctrl+C to skip): ")
        except (EOFError, KeyboardInterrupt):
            print()
            print("(Skipped plugin wait - run `bob plugins` later to re-check.)")

    return missing
