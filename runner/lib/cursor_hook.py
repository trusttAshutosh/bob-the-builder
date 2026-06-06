"""Cursor lifecycle hooks - single entry for sessionStart/stop (logic stays in Bob)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from host_repo import infer_workspace_root, runner_bootstrap_repo

BOB_PY_POINTER = Path.home() / ".cursor" / "hooks" / ".bob-py"
HOOK_RUNNER_NAME = "bob-hook-runner.sh"
LEGACY_HOOK_COMMANDS = frozenset(
    {
        "./hooks/orchestrator-hygiene-stop.sh",
        "./hooks/session-chat-hygiene.sh",
    }
)
BOB_HOOK_RUNNER_CMD = f"./hooks/{HOOK_RUNNER_NAME}"


def cursor_hooks_dir() -> Path:
    return Path.home() / ".cursor" / "hooks"


def resolve_bob_py(workspace: Path | None = None) -> Path | None:
    ws = workspace or infer_workspace_root()
    if ws:
        candidate = (ws / "bob-the-builder" / "bob.py").resolve()
        if candidate.is_file():
            return candidate
    for path in (
        Path.home() / "Desktop" / "novopay" / "bob-the-builder" / "bob.py",
        Path.home() / "novopay" / "bob-the-builder" / "bob.py",
        runner_bootstrap_repo().parent / "bob-the-builder" / "bob.py",
    ):
        if path.is_file():
            return path.resolve()
    bootstrap = runner_bootstrap_repo() / "bob.py"
    return bootstrap.resolve() if bootstrap.is_file() else None


def write_bob_py_pointer(bob_py: Path | None = None) -> Path | None:
    path = resolve_bob_py() if bob_py is None else bob_py.resolve()
    if not path or not path.is_file():
        return None
    BOB_PY_POINTER.parent.mkdir(parents=True, exist_ok=True)
    BOB_PY_POINTER.write_text(str(path) + "\n", encoding="utf-8")
    return BOB_PY_POINTER


def read_bob_py_pointer() -> Path | None:
    if not BOB_PY_POINTER.is_file():
        return None
    raw = BOB_PY_POINTER.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_file() else None


def normalize_hooks_payload(data: dict) -> dict:
    hooks = data.setdefault("hooks", {})
    for hook_type, entries in list(hooks.items()):
        if not isinstance(entries, list):
            continue
        hooks[hook_type] = [
            e for e in entries if e.get("command") not in LEGACY_HOOK_COMMANDS
        ]

    session = hooks.setdefault("sessionStart", [])
    if not any(e.get("command") == f"{BOB_HOOK_RUNNER_CMD} session" for e in session):
        session.append({"command": f"{BOB_HOOK_RUNNER_CMD} session"})

    stop = hooks.setdefault("stop", [])
    stop = [
        e
        for e in stop
        if not str(e.get("command", "")).startswith(BOB_HOOK_RUNNER_CMD)
    ]
    stop.append({"command": f"{BOB_HOOK_RUNNER_CMD} stop", "loop_limit": 1})
    hooks["stop"] = stop
    return data


def merge_hooks_json(dest: Path, template_text: str) -> str:
    if dest.is_file():
        try:
            existing = json.loads(dest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {"version": 1, "hooks": {}}
    else:
        existing = {"version": 1, "hooks": {}}
    existing.setdefault("version", 1)
    existing.setdefault("hooks", {})
    template = json.loads(template_text)
    for hook_type, entries in template.get("hooks", {}).items():
        cur = existing["hooks"].setdefault(hook_type, [])
        for entry in entries:
            if not any(e.get("command") == entry.get("command") for e in cur):
                cur.append(entry)
    existing = normalize_hooks_payload(existing)
    return json.dumps(existing, indent=2) + "\n"


def hook_runner_script() -> str:
    return """#!/usr/bin/env bash
# Bob Cursor hook runner - do not edit; logic lives in `bob cursor-hook`.
set -euo pipefail
KIND="${1:-}"
BOB_PY_FILE="${HOME}/.cursor/hooks/.bob-py"
if [ ! -f "$BOB_PY_FILE" ]; then
  exit 0
fi
BOB_PY="$(tr -d '\\r\\n' < "$BOB_PY_FILE")"
if [ -z "$BOB_PY" ] || [ ! -f "$BOB_PY" ]; then
  exit 0
fi
case "$KIND" in
  session)
    python3 "$BOB_PY" cursor-hook session >/dev/null 2>&1 || true
    ;;
  stop)
    export HOOK_STOP_JSON="$(cat)"
    exec python3 "$BOB_PY" cursor-hook stop
    ;;
  *)
    exit 0
    ;;
esac
"""


def deploy_cursor_hooks(workspace: Path | None = None, *, force: bool = False) -> list[Path]:
    """Install single hook runner + pointer; remove legacy hook scripts."""
    written: list[Path] = []
    bob_py = resolve_bob_py(workspace)
    if bob_py:
        ptr = write_bob_py_pointer(bob_py)
        if ptr:
            written.append(ptr)

    hooks_dir = cursor_hooks_dir()
    hooks_dir.mkdir(parents=True, exist_ok=True)
    runner_dest = hooks_dir / HOOK_RUNNER_NAME
    runner_text = hook_runner_script()
    if force or not runner_dest.is_file() or runner_dest.read_text(encoding="utf-8") != runner_text:
        runner_dest.write_text(runner_text, encoding="utf-8")
        try:
            runner_dest.chmod(runner_dest.stat().st_mode | 0o111)
        except OSError:
            pass
        written.append(runner_dest)

    for legacy in ("orchestrator-hygiene-stop.sh", "session-chat-hygiene.sh"):
        legacy_path = hooks_dir / legacy
        if legacy_path.is_file():
            try:
                legacy_path.unlink()
            except OSError:
                pass

    bundle = runner_bootstrap_repo() / "templates" / "onboarding" / "cursor" / "hooks.json"
    hooks_dest = Path.home() / ".cursor" / "hooks.json"
    if bundle.is_file():
        merged = merge_hooks_json(hooks_dest, bundle.read_text(encoding="utf-8"))
        if force or not hooks_dest.is_file() or hooks_dest.read_text(encoding="utf-8") != merged:
            hooks_dest.parent.mkdir(parents=True, exist_ok=True)
            hooks_dest.write_text(merged, encoding="utf-8")
            written.append(hooks_dest)

    return written


def _bob_subcommand_json(argv: list[str]) -> dict:
    bob_py = read_bob_py_pointer() or resolve_bob_py()
    if not bob_py:
        return {}
    proc = subprocess.run(
        [sys.executable, str(bob_py), *argv],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=600,
    )
    out = (proc.stdout or "").strip()
    if not out:
        return {}
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def run_session_hook() -> int:
    bob_py = read_bob_py_pointer() or resolve_bob_py()
    if not bob_py:
        return 0
    subprocess.run(
        [sys.executable, str(bob_py), "chat-hygiene", "--auto", "--hook", "session"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=180,
    )
    subprocess.run(
        [sys.executable, str(bob_py), "memory-budget", "--hook", "session"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=120,
    )
    return 0


def run_stop_hook() -> int:
    if not os.environ.get("HOOK_STOP_JSON", "").strip():
        print("{}")
        return 0

    chat = _bob_subcommand_json(["chat-hygiene", "--hook", "stop", "--learn"])
    meta = _bob_subcommand_json(["meta-review", "--hook", "stop"])
    msgs = [
        str(payload["followup_message"])
        for payload in (chat, meta)
        if isinstance(payload.get("followup_message"), str) and payload["followup_message"].strip()
    ]
    if msgs:
        print(json.dumps({"followup_message": " ".join(msgs)}))
    else:
        print("{}")
    return 0


def run_cursor_hook_cli(args: list[str] | None = None) -> int:
    kind = (args or [""])[0].strip().lower()
    if kind == "session":
        return run_session_hook()
    if kind == "stop":
        return run_stop_hook()
    print("Usage: bob cursor-hook session|stop", file=sys.stderr)
    return 1


def hooks_assess_ok() -> bool | None:
    hooks = Path.home() / ".cursor" / "hooks.json"
    if not hooks.is_file():
        return False
    try:
        data = json.loads(hooks.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    session = data.get("hooks", {}).get("sessionStart") or []
    stop = data.get("hooks", {}).get("stop") or []
    has_session = any(f"{BOB_HOOK_RUNNER_CMD} session" in str(e.get("command", "")) for e in session)
    has_stop = any(f"{BOB_HOOK_RUNNER_CMD} stop" in str(e.get("command", "")) for e in stop)
    return has_session and has_stop
