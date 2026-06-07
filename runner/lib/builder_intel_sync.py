"""Auto-maintain docs/internal/BUILDER_INTEL.md inventory from product-features.yaml + NEXT.md."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

AUTO_START = "<!-- BUILDER_INTEL:AUTO:START -->"
AUTO_END = "<!-- BUILDER_INTEL:AUTO:END -->"
STAMP = "<!-- BUILDER_INTEL:SYNC="

BUILDER_INTEL_REL = "docs/internal/BUILDER_INTEL.md"
FEATURES_REL = "docs/product-features.yaml"
NEXT_REL = "docs/NEXT.md"


def _root(root: Path | None) -> Path:
    if root is not None:
        return root.resolve()
    return Path(__file__).resolve().parents[2]


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit("PyYAML required: pip install pyyaml") from exc
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _cli_command_count(root: Path) -> int:
    cli = root / "runner" / "lib" / "builder_cli.py"
    if not cli.is_file():
        return 0
    text = cli.read_text(encoding="utf-8")
    block = re.search(r"handlers\s*=\s*\{", text)
    if not block:
        return 0
    rest = text[block.start() :]
    end = rest.find("\n    }")
    chunk = rest[: end if end > 0 else 4000]
    return len(set(re.findall(r'"([a-z-]+)":\s*cmd_', chunk)))


def _open_next_items(next_path: Path) -> list[tuple[str, str]]:
    """Return (section, item text) for unchecked - [ ] lines in Now/Next/Later."""
    if not next_path.is_file():
        return []
    items: list[tuple[str, str]] = []
    section = ""
    for line in next_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## Now"):
            section = "Now"
            continue
        if line.startswith("## Next"):
            section = "Next"
            continue
        if line.startswith("## Later"):
            section = "Later"
            continue
        if line.startswith("## Done") or line.startswith("## Adding"):
            section = ""
            continue
        if section and line.strip().startswith("- [ ]"):
            text = re.sub(r"^- \[ \]\s*", "", line.strip())
            items.append((section, text))
    return items


def _head_commit_short(root: Path) -> str:
    try:
        import subprocess

        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if r.returncode == 0 and (r.stdout or "").strip():
            return (r.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "none"


def _fix_links_for_internal_md(text: str) -> str:
    """NEXT.md links are docs-relative; BUILDER_INTEL lives in docs/internal/."""

    def repl(match: re.Match[str]) -> str:
        url = match.group(1).strip()
        if url.startswith(("http://", "https://", "#", "../", "mailto:")):
            return match.group(0)
        if "/" not in url:
            return f"](../{url})"
        return match.group(0)

    return re.sub(r"\]\(([^)#]+)\)", repl, text)


def render_auto_section(root: Path | None = None) -> str:
    root = _root(root)
    features_path = root / FEATURES_REL
    data = _load_yaml(features_path)
    features = data.get("features") or []
    cmd_count = _cli_command_count(root)
    checked = date.today().isoformat()
    commit = _head_commit_short(root)
    open_items = _open_next_items(root / NEXT_REL)

    lines = [
        "## Auto-maintained inventory (do not edit this section)",
        "",
        f"**Synced:** {checked} · commit `{commit}` · "
        f"**{len(features)}** registered features · **{cmd_count}** CLI handler commands.",
        "",
        "Source of truth: [`product-features.yaml`](../product-features.yaml). "
        "Refreshed by `bob verify-product --update` and the post-commit hook.",
        "",
        "| Feature | ID | CLI commands |",
        "|---------|-----|--------------|",
    ]
    for feat in features:
        fid = str(feat.get("id", "?"))
        name = str(feat.get("name", fid))
        cmds = feat.get("commands") or []
        cmd_cell = ", ".join(f"`{c}`" for c in cmds) if cmds else "—"
        lines.append(f"| {name} | `{fid}` | {cmd_cell} |")

    lines.extend(["", "### Planned (open in NEXT.md)", ""])
    if open_items:
        for section, text in open_items:
            safe = _fix_links_for_internal_md(text.replace("|", "\\|"))
            lines.append(f"- **[{section}]** {safe}")
    else:
        lines.append("_No open Now/Next/Later items — see [NEXT.md](../NEXT.md) Done._")

    lines.extend(
        [
            "",
            f"{STAMP}{checked}:{commit} -->",
        ]
    )
    return "\n".join(lines)


def read_sync_stamp(text: str) -> str:
    m = re.search(r"<!-- BUILDER_INTEL:SYNC=([^>]+) -->", text)
    return (m.group(1).strip() if m else "") or ""


def _replace_auto_block(text: str, body: str) -> str:
    block = f"{AUTO_START}\n{body.rstrip()}\n{AUTO_END}"
    if AUTO_START in text and AUTO_END in text:
        pattern = re.escape(AUTO_START) + r".*?" + re.escape(AUTO_END)
        return re.sub(pattern, block, text, count=1, flags=re.DOTALL)
    anchor = "## AI / agent concepts"
    if anchor in text:
        return text.replace(anchor, f"{block}\n\n{anchor}", 1)
    return text.rstrip() + "\n\n" + block + "\n"


def sync_builder_intel(root: Path | None = None, *, write: bool = True) -> tuple[bool, str]:
    """Refresh auto section. Returns (changed, message)."""
    root = _root(root)
    intel_path = root / BUILDER_INTEL_REL
    if not intel_path.is_file():
        return False, f"Missing {BUILDER_INTEL_REL}"

    body = render_auto_section(root)
    old = intel_path.read_text(encoding="utf-8")
    new_stamp = read_sync_stamp(body)
    old_stamp = read_sync_stamp(old)
    new_text = _replace_auto_block(old, body)
    changed = new_text != old

    if write and changed:
        intel_path.write_text(new_text, encoding="utf-8")
    if changed:
        return True, f"Updated {BUILDER_INTEL_REL} (sync {new_stamp})"
    return False, f"{BUILDER_INTEL_REL} auto section already current ({old_stamp or new_stamp})"


def verify_builder_intel_sync(root: Path | None = None) -> tuple[bool, str]:
    """True if on-disk auto section matches generated content."""
    root = _root(root)
    intel_path = root / BUILDER_INTEL_REL
    if not intel_path.is_file():
        return False, f"Missing {BUILDER_INTEL_REL}"
    text = intel_path.read_text(encoding="utf-8")
    if AUTO_START not in text or AUTO_END not in text:
        return False, f"Missing {AUTO_START} markers in {BUILDER_INTEL_REL}"
    expected = render_auto_section(root)
    expected_block = f"{AUTO_START}\n{expected.rstrip()}\n{AUTO_END}"
    pattern = re.escape(AUTO_START) + r".*?" + re.escape(AUTO_END)
    m = re.search(pattern, text, flags=re.DOTALL)
    if not m:
        return False, "Auto section markers found but block unreadable"
    actual_block = m.group(0)
    if actual_block.strip() != expected_block.strip():
        return False, "BUILDER_INTEL auto section stale — run: bob verify-product --update"
    return True, "BUILDER_INTEL auto section in sync"
