"""Zero-habit reminders — Bob tells you (or fixes) what matters before git/CI."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from host_repo import runner_bootstrap_repo


def product_root() -> Path:
    return runner_bootstrap_repo().resolve()


def _git(*args: str, cwd: Path | None = None) -> str:
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=cwd or product_root(),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return (r.stdout or "").strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def is_product_git_repo() -> bool:
    root = product_root()
    return (root / "bob.py").is_file() and (root / ".git").exists()


def head_short() -> str:
    h = _git("rev-parse", "HEAD")
    return h[:7] if h else ""


def next_md_path() -> Path:
    return product_root() / "docs" / "NEXT.md"


def next_stamp() -> str:
    path = next_md_path()
    if not path.is_file():
        return ""
    m = re.search(r"<!-- PRODUCT-VERIFY:COMMIT=([^>]+) -->", path.read_text(encoding="utf-8"))
    return (m.group(1).strip() if m else "") or ""


def next_md_stale() -> bool:
    if not head_short():
        return False
    stamp = next_stamp()
    head = _git("rev-parse", "HEAD")
    if stamp in {head_short(), head}:
        return False
    # Bob auto-docs commit: stamp documents the parent (feature) commit
    subject = _git("log", "-1", "--format=%s")
    if subject and "[bob]" in subject:
        parent = _git("rev-parse", "HEAD^")
        if parent and stamp in {parent[:7], parent}:
            return False
    if not stamp or stamp == "none":
        return True
    return True


def has_uncommitted() -> bool:
    return bool(_git("status", "--porcelain"))


def ahead_of_remote() -> bool:
    upstream = _git("rev-parse", "--abbrev-ref", "@{upstream}")
    if not upstream:
        return bool(head_short())
    behind = _git("rev-list", "--count", f"HEAD..{upstream}")
    ahead = _git("rev-list", "--count", f"{upstream}..HEAD")
    try:
        return int(ahead or "0") > 0
    except ValueError:
        return False


def refresh_next_md() -> bool:
    """Run verify-product --update. Returns True if update ran."""
    script = product_root() / "runner" / "ci" / "verify-product.py"
    if not script.is_file():
        return False
    r = subprocess.run(
        [sys.executable, str(script), "--update"],
        cwd=str(product_root()),
        check=False,
    )
    return r.returncode == 0


def auto_maintain_next_md() -> str | None:
    """Refresh stale NEXT.md during bob commands (pre-commit). Post-commit hook handles git commits."""
    if not is_product_git_repo() or not next_md_stale():
        return None
    from git_hooks import hooks_installed

    if hooks_installed():
        return None
    if not refresh_next_md():
        return "Bob could not refresh docs/NEXT.md — run: python bob.py remind --fix"
    return "Bob refreshed docs/NEXT.md for you — include it in your commit."


def remind_message(*, fix: bool = False) -> tuple[str, int]:
    """
    Single instruction for the user. Returns (message, exit_code).
    fix=True runs refresh when stale.
    """
    if not is_product_git_repo():
        return ("Bob product repo not detected (no .git here).", 1)

    if fix and next_md_stale():
        if refresh_next_md():
            return ("Updated docs/NEXT.md. Commit it with your other changes, then push.", 0)
        return ("Could not update docs/NEXT.md.", 1)

    from git_hooks import hooks_installed

    if next_md_stale() and hooks_installed():
        return (
            "docs/NEXT.md will refresh on your next git commit (Bob post-commit hook).",
            0,
        )

    if next_md_stale():
        return (
            "docs/NEXT.md is behind — run: python bob.py install-hooks (auto after commit) or remind --fix",
            0,
        )

    if has_uncommitted():
        return ("Uncommitted changes — commit when ready; Bob already refreshed NEXT.md if needed.", 0)

    if ahead_of_remote():
        return ("Local commits ready — push when you want.", 0)

    return ("Nothing Bob needs from you right now.", 0)


def print_nudge_after_command(command: str) -> None:
    """At most one extra line after other bob output."""
    if command in ("help", "version", "next", "remind"):
        return
    if command == "verify-product":
        return

    msg = auto_maintain_next_md()
    if msg:
        print()
        print(f"Bob: {msg}")
