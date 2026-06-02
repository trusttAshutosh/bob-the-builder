"""Export Bob platform + session knowledge graph to an Obsidian vault (wikilinks + graph view)."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from _yaml_util import load
from bob_home import bob_local_root, platform_graph_path
from session_graph import session_path

# Validators duplicated on many APIs — omit as graph nodes to reduce noise.
_SKIP_PROCESSOR_BEANS = frozenset(
    {
        "mandatoryFieldValidator",
        "patternFieldValidator",
        "numberValidator",
        "masterDataNegativeCheckValidator",
        "dummyProcessor",
    }
)


def obsidian_vault_path(override: str | None = None) -> Path:
    raw = (override or os.environ.get("BOB_OBSIDIAN_VAULT") or "").strip()
    if raw:
        p = Path(raw).expanduser()
    else:
        p = bob_local_root() / "obsidian-vault"
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def _slug(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "-", name.strip())
    return s[:120] or "unnamed"


def _wikilink(note_key: str) -> str:
    """Wikilink using vault-relative path (no .md)."""
    return f"[[{note_key.replace(chr(92), '/')}]]"


def _note_path(vault: Path, rel_key: str) -> Path:
    parts = [_slug(p) for p in rel_key.replace("\\", "/").split("/") if p.strip()]
    return vault.joinpath(*parts).with_suffix(".md")


def _write_note(vault: Path, rel_key: str, body: str, frontmatter: dict[str, Any] | None = None) -> Path:
    path = _note_path(vault, rel_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if frontmatter:
        lines.append("---")
        for k, v in frontmatter.items():
            if isinstance(v, list):
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{k}: {v}")
        lines.append("---")
        lines.append("")
    lines.append(body.strip() + "\n")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _load_platform() -> dict:
    p = platform_graph_path()
    return load(p) if p.is_file() else {}


def _export_api_notes(vault: Path, plat: dict) -> int:
    count = 0
    processors = plat.get("processors") or {}
    for api_id, info in sorted((plat.get("gateway_apis") or {}).items()):
        if not isinstance(info, dict):
            continue
        beans = info.get("processor_beans") or []
        linked = [b for b in beans if b in processors and b not in _SKIP_PROCESSOR_BEANS]
        orch = (plat.get("orchestration") or {}).get(api_id) or {}
        lines = [
            f"# API: {api_id}",
            "",
            f"- **Path:** `{info.get('path', '')}`",
            f"- **Orchestration:** `{orch.get('file', '—')}`",
            "",
            "## Processor chain",
            "",
        ]
        if linked:
            for b in linked:
                lines.append(f"- {_wikilink(f'processor/{b}')} (`{b}`)")
        else:
            lines.append("_No dedicated processor beans (validators only)._")
        if info.get("bank_calls"):
            lines.append("")
            lines.append("## Bank calls")
            for bc in info.get("bank_calls") or []:
                lines.append(f"- `{bc}`")
        if info.get("catalog"):
            lines.append("")
            lines.append(f"- **Catalog:** `{info.get('catalog')}`")
        _write_note(
            vault,
            f"api/{api_id}",
            "\n".join(lines),
            frontmatter={"type": "api", "bob_id": api_id},
        )
        count += 1
    return count


def _export_processor_notes(vault: Path, plat: dict) -> int:
    count = 0
    for bean, info in sorted((plat.get("processors") or {}).items()):
        if not isinstance(info, dict):
            continue
        if not bean.endswith("Processor"):
            continue
        cls = info.get("class", "")
        extends = info.get("extends", "")
        lines = [
            f"# Processor: {bean}",
            "",
            f"- **Class:** `{cls}`",
            f"- **Extends:** `{extends or '—'}`",
            f"- **File:** `{info.get('file', '')}`",
            "",
            "## Pattern",
            "",
        ]
        if extends == "AbstractCreditCardManager":
            lines.append("- Transaction audit + API channel (complex flow)")
        elif extends == "AbstractProcessor":
            lines.append("- Simple processor (no full CC manager)")
        _write_note(
            vault,
            f"processor/{bean}",
            "\n".join(lines),
            frontmatter={"type": "processor", "bob_id": bean, "extends": extends},
        )
        count += 1
    return count


def _export_stub_notes(vault: Path, plat: dict) -> int:
    count = 0
    for op, fixtures in sorted((plat.get("bank_operation_stubs") or {}).items()):
        lines = [
            f"# Bank stub: {op}",
            "",
            "## Fixtures",
            "",
        ]
        for fx in fixtures or []:
            lines.append(f"- `{fx}`")
        _write_note(
            vault,
            f"stub/{op}",
            "\n".join(lines),
            frontmatter={"type": "stub", "bob_id": op},
        )
        count += 1
    return count


def _export_session_notes(vault: Path) -> int:
    sp = session_path()
    if not sp.is_file():
        return 0
    sess = load(sp)
    count = 0
    for task in sess.get("tasks") or []:
        tid = task.get("ticket_id")
        if not tid:
            continue
        results = task.get("results") or {}
        dec = task.get("decisions") or {}
        apis = dec.get("apis_from_catalog") or []
        lines = [
            f"# Ticket: {tid}",
            "",
            f"- **Title:** {task.get('title', '')}",
            f"- **Branch:** `{task.get('branch', '')}`",
            f"- **Last run:** {task.get('at', '')}",
            f"- **Overall:** {task.get('overall', '—')}",
            "",
            "## Scenarios",
            "",
        ]
        for sid, res in sorted(results.items()):
            if isinstance(res, dict):
                st = "PASS" if res.get("pass") else "FAIL"
                lines.append(f"- **{sid}** ({res.get('level', '')}): {st}")
        if apis:
            lines.append("")
            lines.append("## APIs")
            lines.append("")
            for api in apis:
                lines.append(f"- {_wikilink(f'api/{api}')}")
        _write_note(
            vault,
            f"ticket/{tid}",
            "\n".join(lines),
            frontmatter={"type": "ticket", "bob_id": tid, "branch": task.get("branch", "")},
        )
        count += 1
    return count


def _export_index(vault: Path, plat: dict, stats: dict[str, int]) -> Path:
    meta = plat.get("meta") or {}
    lines = [
        "# Bob knowledge graph",
        "",
        "Open **Obsidian → Open folder as vault** and select this directory. "
        "Use the **Graph** view (left ribbon) for a live, explorable map.",
        "",
        f"- **Updated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Platform scan:** {meta.get('updated_at', '—')} · repo `{meta.get('repo', '—')}`",
        "",
        "## Counts",
        "",
        f"- APIs: {stats.get('apis', 0)}",
        f"- Processors: {stats.get('processors', 0)}",
        f"- Bank stubs: {stats.get('stubs', 0)}",
        f"- Tickets (session): {stats.get('tickets', 0)}",
        "",
        "## Browse",
        "",
        "- See folder `api/` for gateway APIs",
        "- See folder `processor/` for Java processors",
        "- See folder `stub/` for WireMock bank operations",
        "- See folder `ticket/` for your validate-ticket history",
        "",
        "## Commands",
        "",
        "```bash",
        "bob sync-graph          # refresh platform-graph.yaml",
        "bob graph sync-obsidian # refresh this vault",
        "bob query-graph loc     # refresh agent text slice",
        "```",
        "",
        "Also see `graph-overview.mmd` for Mermaid preview (GitHub / mermaid.live).",
    ]
    return _write_note(vault, "Bob Home", "\n".join(lines), frontmatter={"type": "index"})


def _export_mermaid_overview(vault: Path, plat: dict, *, max_apis: int = 40) -> Path:
    """Subset diagram for paste into mermaid.live or markdown preview."""
    lines = ["flowchart LR", "  subgraph APIs"]
    processors = plat.get("processors") or {}
    n = 0
    for api_id, info in sorted((plat.get("gateway_apis") or {}).items()):
        if n >= max_apis:
            break
        beans = [
            b
            for b in (info.get("processor_beans") or [])
            if b in processors and b not in _SKIP_PROCESSOR_BEANS
        ]
        if not beans:
            continue
        api_node = re.sub(r"[^a-zA-Z0-9_]", "_", api_id)
        lines.append(f"    {api_node}[{api_id}]")
        for b in beans[:3]:
            bnode = re.sub(r"[^a-zA-Z0-9_]", "_", b)
            lines.append(f"    {api_node} --> {bnode}[{b}]")
        n += 1
    lines.append("  end")
    out = vault / "graph-overview.mmd"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def _write_obsidian_graph_settings(vault: Path) -> None:
    obs = vault / ".obsidian"
    obs.mkdir(parents=True, exist_ok=True)
    graph_json = obs / "graph.json"
    if not graph_json.exists():
        graph_json.write_text(
            json.dumps(
                {
                    "collapse-filter": False,
                    "showOrphans": True,
                    "showTags": True,
                    "showArrow": False,
                    "textFadeMultiplier": 0,
                    "nodeSizeMultiplier": 1.2,
                    "lineSizeMultiplier": 1,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


def sync_obsidian_vault(vault_path: str | None = None, *, include_session: bool = True) -> tuple[Path, dict[str, int]]:
    """
    Write / refresh Obsidian vault from platform-graph + session-graph.
    Returns vault path and export counts.
    """
    vault = obsidian_vault_path(vault_path)
    plat = _load_platform()

    stats: dict[str, int] = {}
    stats["apis"] = _export_api_notes(vault, plat)
    stats["processors"] = _export_processor_notes(vault, plat)
    stats["stubs"] = _export_stub_notes(vault, plat)
    stats["tickets"] = _export_session_notes(vault) if include_session else 0
    _export_index(vault, plat, stats)
    _export_mermaid_overview(vault, plat)
    _write_obsidian_graph_settings(vault)

    manifest = {
        "vault": str(vault),
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "platform_meta": plat.get("meta"),
        "counts": stats,
    }
    (vault / "bob-export-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return vault, stats


def print_open_instructions(vault: Path) -> str:
    return (
        f"Obsidian vault: {vault}\n"
        f"  1. Install Obsidian (https://obsidian.md) — free for personal use\n"
        f"  2. Open folder as vault - select: {vault}\n"
        f"  3. Open note 'Bob Home', then click Graph in the left sidebar\n"
        f"  4. Re-run: bob graph sync-obsidian  (after bob sync-graph)\n"
        f"Mermaid subset: {vault / 'graph-overview.mmd'} - paste at https://mermaid.live\n"
    )
