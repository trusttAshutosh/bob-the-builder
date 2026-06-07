"""One-time: put `bob` and flat command shims on PATH via local/bin."""
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

BOB_PS1 = r"""# Bob the Builder — PowerShell entry
$BobRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
& python (Join-Path $BobRoot "bob.py") @args
exit $LASTEXITCODE
"""

BOB_SH = """#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python "$ROOT/bob.py" "$@"
"""

# Short names stay `bob <cmd>` only — they collide with shell builtins (help, install, …).
_SKIP_FLAT = frozenset(
    {
        "help",
        "setup",
        "onboard",
        "plugins",
        "install",
        "remind",
        "kafka",
        "graph",
        "eval",
        "context",
        "host",
        "tools",
        "version",
        "next",
    }
)


def flat_shim_commands() -> list[str]:
    """Hyphenated Bob commands (+ ego-boost) safe to expose as PATH executables."""
    from builder_cli import CMD_ALIASES

    names: set[str] = set()
    for canonical in CMD_ALIASES.values():
        if canonical in _SKIP_FLAT:
            continue
        if "-" in canonical:
            names.add(canonical)
    names.add("ego-boost")
    return sorted(names)


def _marker_path() -> Path:
    return bob_local_root() / MARKER_NAME


def _bin_dir() -> Path:
    return bob_local_root() / "bin"


def _path_configured() -> bool:
    return _marker_path().is_file()


def _path_contains(bin_dir: Path) -> bool:
    norm = str(bin_dir.resolve()).lower()
    for part in os.environ.get("PATH", "").split(os.pathsep):
        if not part:
            continue
        try:
            if Path(part).resolve().as_posix().lower() == bin_dir.resolve().as_posix().lower():
                return True
        except OSError:
            continue
    return False


def _flat_cmd_shim(command: str) -> str:
    return (
        "@echo off\n"
        'set "BOB_ROOT=%~dp0..\\.."\n'
        f'python "%BOB_ROOT%\\bob.py" {command} %*\n'
    )


def _flat_sh_shim(command: str) -> str:
    return (
        "#!/usr/bin/env bash\n"
        'ROOT="$(cd "$(dirname "$0")/../.." && pwd)"\n'
        f'exec python "$ROOT/bob.py" {command} "$@"\n'
    )


def _install_shims(bin_dir: Path) -> list[str]:
    bin_dir.mkdir(parents=True, exist_ok=True)
    cmd = bin_dir / "bob.cmd"
    ps1 = bin_dir / "bob.ps1"
    sh = bin_dir / "bob"
    cmd.write_text(BOB_CMD, encoding="utf-8", newline="\r\n")
    ps1.write_text(BOB_PS1, encoding="utf-8", newline="\n")
    sh.write_text(BOB_SH, encoding="utf-8", newline="\n")
    try:
        sh.chmod(0o755)
    except OSError:
        pass

    installed: list[str] = ["bob", "bob.cmd", "bob.ps1"]
    for name in flat_shim_commands():
        flat_cmd = bin_dir / f"{name}.cmd"
        flat_cmd.write_text(_flat_cmd_shim(name), encoding="utf-8", newline="\r\n")
        installed.append(f"{name}.cmd")
        flat_sh = bin_dir / name
        flat_sh.write_text(_flat_sh_shim(name), encoding="utf-8", newline="\n")
        try:
            flat_sh.chmod(0o755)
        except OSError:
            pass
        installed.append(name)
    return installed


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


def is_path_configured() -> bool:
    return _path_configured()


def prepend_bin_to_process_path(bin_dir: Path) -> None:
    b = str(bin_dir.resolve())
    if not _path_contains(bin_dir):
        os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")


def path_shim_status() -> dict[str, object]:
    bin_dir = _bin_dir()
    product = runner_bootstrap_repo().resolve()
    bob_py = product / "bob.py"
    on_path = _path_contains(bin_dir)
    flat = flat_shim_commands()
    return {
        "product_root": str(product),
        "bob_py": str(bob_py),
        "bob_py_exists": bob_py.is_file(),
        "bin_dir": str(bin_dir.resolve()),
        "bin_dir_exists": bin_dir.is_dir(),
        "marker_exists": _path_configured(),
        "on_path": on_path,
        "flat_shim_count": len(flat),
        "python": sys.executable,
    }


def ensure_bob_on_path(*, quiet: bool = False, force: bool = False) -> None:
    """
    Run once per machine (marker in BOB_LOCAL) unless force=True.
    Writes local/bin/bob(.cmd/.ps1) + flat hyphenated command shims; adds bin to user PATH.
    """
    if force and _marker_path().is_file():
        _marker_path().unlink(missing_ok=True)

    bin_dir = _bin_dir()
    _install_shims(bin_dir)

    if _path_configured() and not force:
        prepend_bin_to_process_path(bin_dir)
        return

    product = runner_bootstrap_repo().resolve()
    local = bob_local_root()
    added = False
    if sys.platform == "win32":
        try:
            added = _append_windows_user_path(bin_dir)
        except OSError as e:
            if not quiet:
                print(f"Could not update Windows PATH: {e}", file=sys.stderr)
        if not _path_contains(bin_dir):
            added = _update_unix_profile(bin_dir) or added
    else:
        added = _update_unix_profile(bin_dir)

    _marker_path().write_text(
        f"product={product}\nbin={bin_dir.resolve()}\n",
        encoding="utf-8",
    )
    prepend_bin_to_process_path(bin_dir)

    if quiet:
        return
    print()
    print("Bob: added commands to your user PATH (one-time).")
    print(f"  Shims: {bin_dir}")
    print(f"  Flat shims: {len(flat_shim_commands())} hyphenated commands (e.g. builder-intel, validate-ticket)")
    print("  Always prefix with bob when unsure:  bob builder-intel --open")
    if added or not _path_contains(bin_dir):
        print("  Open a **new** terminal if `bob` or `builder-intel` is not found yet.")
    else:
        print("  PATH already contained Bob; try:  bob help")
    print()
