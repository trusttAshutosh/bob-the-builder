"""Install Bob git hooks into the product repo (.git/hooks — not git config)."""
from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path

from host_repo import runner_bootstrap_repo


def product_root() -> Path:
    return runner_bootstrap_repo().resolve()


def hook_source(name: str) -> Path:
    return product_root() / "runner" / "hooks" / name


def hook_target(name: str) -> Path:
    return product_root() / ".git" / "hooks" / name


def _make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def hooks_installed() -> bool:
    dest = hook_target("post-commit")
    if not dest.is_file():
        return False
    text = dest.read_text(encoding="utf-8", errors="ignore")
    return "Bob —" in text


def install_git_hooks(*, force: bool = False) -> tuple[bool, str]:
    """Copy runner/hooks/* into .git/hooks/. Returns (ok, message)."""
    root = product_root()
    git_dir = root / ".git"
    if not git_dir.is_dir():
        return False, "Not a git repo — skip hook install."

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    src_dir = root / "runner" / "hooks"
    if not src_dir.is_dir():
        return False, f"Missing {src_dir}"

    installed: list[str] = []
    for src in sorted(src_dir.iterdir()):
        if not src.is_file() or src.name.startswith("."):
            continue
        dest = hooks_dir / src.name
        if dest.exists() and not force:
            # Refresh Bob hook if it looks like ours or force=false but content differs
            existing = dest.read_text(encoding="utf-8", errors="ignore")
            new = src.read_text(encoding="utf-8")
            if "Bob —" in existing and existing == new:
                continue
        shutil.copy2(src, dest)
        if sys.platform != "win32" or dest.suffix != ".cmd":
            _make_executable(dest)
        installed.append(src.name)

    if not installed:
        return True, "Git hooks already up to date (post-commit)."
    return True, f"Installed git hooks: {', '.join(installed)}"


def post_commit_refresh_next_md() -> tuple[bool, str]:
    """Run verify-product --update; commit NEXT.md if stale. For tests / manual invoke."""
    import subprocess

    root = product_root()
    script = root / "runner" / "ci" / "verify-product.py"
    if not script.is_file():
        return False, "verify-product.py not found"

    last_msg = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if "[bob]" in (last_msg.stdout or ""):
        return True, "Skipped — last commit is Bob docs refresh."

    r = subprocess.run([sys.executable, str(script), "--update"], cwd=root, check=False)
    if r.returncode != 0:
        return False, "verify-product --update failed"

    diff = subprocess.run(["git", "diff", "--quiet", "docs/NEXT.md"], cwd=root, check=False)
    if diff.returncode == 0:
        return True, "docs/NEXT.md already matches HEAD."

    env = os.environ.copy()
    env["BOB_SKIP_POST_COMMIT"] = "1"
    subprocess.run(["git", "add", "docs/NEXT.md"], cwd=root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "docs: refresh NEXT.md product verify [bob]", "--no-verify"],
        cwd=root,
        env=env,
        check=True,
    )
    return True, "Committed docs/NEXT.md refresh [bob]."
