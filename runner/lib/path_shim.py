"""One-time: put `bob` on PATH via local/bin shims (first command only)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from bob_home import bob_local_root
from host_repo import runner_bootstrap_repo

MARKER_NAME = ".path-configured"
PATH_BLOCK_START = "# >>> bob-the-builder PATH >>>"
PATH_BLOCK_END = "# <<< bob-the-builder PATH <<<"

BOB_CMD = r"""@echo off
set "BOB_ROOT=%~dp0..\.."
python "%BOB_ROOT%\bob.py" %*
"""

BOB_SH = """#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python "$ROOT/bob.py" "$@"
"""


def _marker_path() -> Path:
    return bob_local_root() / MARKER_NAME


def _bin_dir() -> Path:
    return bob_local_root() / "bin"


def _path_configured() -> bool:
    return _marker_path().is_file()


def _path_contains(bin_dir: Path) -> bool:
    norm = str(bin_dir.resolve()).lower()
    for part in os.environ.get("PATH", "").split(os.pathsep):
        if part and Path(part).resolve().as_posix().lower() == bin_dir.resolve().as_posix().lower():
            return True
    return False


def _install_shims(bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    cmd = bin_dir / "bob.cmd"
    sh = bin_dir / "bob"
    cmd.write_text(BOB_CMD, encoding="utf-8", newline="\r\n")
    sh.write_text(BOB_SH, encoding="utf-8", newline="\n")
    try:
        sh.chmod(0o755)
    except OSError:
        pass


def _append_windows_user_path(bin_dir: Path) -> bool:
    import winreg

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Environment",
        0,
        winreg.KEY_READ | winreg.KEY_WRITE,
    )
    try:
        current, kind = winreg.QueryValueEx(key, "Path")
    except FileNotFoundError:
        current, kind = "", winreg.REG_EXPAND_SZ
    parts = [p for p in current.split(os.pathsep) if p]
    b = str(bin_dir.resolve())
    for p in parts:
        try:
            if Path(p).resolve() == bin_dir.resolve():
                return False
        except OSError:
            continue
    parts.append(b)
    winreg.SetValueEx(key, "Path", 0, kind, os.pathsep.join(parts))
    _broadcast_windows_env_change()
    return True


def _broadcast_windows_env_change() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.user32.SendMessageTimeoutW(  # type: ignore[attr-defined]
            0xFFFF,
            0x001A,
            0,
            "Environment",
            0,
            1000,
            None,
        )
    except OSError:
        pass


def _unix_profile_candidates() -> list[Path]:
    home = Path.home()
    out: list[Path] = []
    for name in (".bashrc", ".zshrc", ".profile"):
        p = home / name
        if p.exists():
            out.append(p)
    if not out:
        out.append(home / ".profile")
    return out


def _update_unix_profile(bin_dir: Path) -> bool:
    line = f'export PATH="{bin_dir.resolve()}:$PATH"'
    block = f"{PATH_BLOCK_START}\n{line}\n{PATH_BLOCK_END}\n"
    changed = False
    for profile in _unix_profile_candidates():
        text = profile.read_text(encoding="utf-8") if profile.exists() else ""
        if PATH_BLOCK_START in text:
            continue
        if not profile.exists():
            profile.write_text(f"# Bob the Builder\n{block}", encoding="utf-8")
        else:
            profile.write_text(text.rstrip() + "\n\n" + block, encoding="utf-8")
        changed = True
        break
    return changed


def ensure_bob_on_path(*, quiet: bool = False) -> None:
    """
  Run once per machine (marker in BOB_LOCAL).
  Writes local/bin/bob(.cmd) and adds that directory to the user PATH.
  """
    if _path_configured():
        return

    product = runner_bootstrap_repo().resolve()
    local = bob_local_root()
    bin_dir = _bin_dir()
    _install_shims(bin_dir)

    added = False
    if sys.platform == "win32":
        try:
            added = _append_windows_user_path(bin_dir)
        except OSError as e:
            if not quiet:
                print(f"Could not update Windows PATH: {e}", file=sys.stderr)
        # Git Bash / MSYS often inherit Windows user Path; also try profile on win32
        if not _path_contains(bin_dir):
            added = _update_unix_profile(bin_dir) or added
    else:
        added = _update_unix_profile(bin_dir)

    _marker_path().write_text(
        f"product={product}\nbin={bin_dir.resolve()}\n",
        encoding="utf-8",
    )

    # Current shell can use `bob` immediately; new terminals pick up persisted PATH.
    b = str(bin_dir.resolve())
    if not _path_contains(bin_dir):
        os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")

    if quiet:
        return
    print()
    print("Bob: added `bob` to your user PATH (one-time).")
    print(f"  Shims: {bin_dir}")
    if added or not _path_contains(bin_dir):
        print("  Open a **new** terminal, then run:  bob help")
    else:
        print("  PATH already contained Bob; use:  bob help")
    print()
