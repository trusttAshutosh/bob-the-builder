"""Cursor chat sidebar hygiene - archive stale/overflow composers (never delete)."""
from __future__ import annotations

import argparse
import glob
import json
import os
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from host_repo import infer_workspace_root, runner_bootstrap_repo

COMPOSER_KEYS = (
    "composer.composerHeaders",
    "composer.composerData",
    "cursor/composer.composerData",
)
DEFAULT_MAX_ACTIVE = 8
DEFAULT_STALE_DAYS = 7
LEARN_INTERVAL_DAYS = 7
STATE_REL = Path(".cursor/hooks/state/chat-hygiene.json")
MS_PER_DAY = 86_400_000


@dataclass(frozen=True)
class ComposerEntry:
    composer_id: str
    name: str
    is_archived: bool
    is_pinned: bool
    is_draft: bool
    is_subagent: bool
    last_activity_ms: int
    raw: dict[str, Any] = field(repr=False)


@dataclass(frozen=True)
class ArchiveTarget:
    composer_id: str
    name: str
    reason: str


@dataclass
class ComposerStore:
    db_path: Path
    key: str
    payload: dict[str, Any]
    composers: list[dict[str, Any]]


def state_path() -> Path:
    return Path.home() / STATE_REL


def cursor_user_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Cursor" / "User"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "Cursor" / "User"


def global_state_db() -> Path:
    return cursor_user_dir() / "globalStorage" / "state.vscdb"


def iter_workspace_state_dbs() -> list[Path]:
    root = cursor_user_dir() / "workspaceStorage"
    if not root.is_dir():
        return []
    return sorted(Path(p) for p in glob.glob(str(root / "*" / "state.vscdb")))


def _read_json_value(conn: sqlite3.Connection, key: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT value FROM ItemTable WHERE key = ?", (key,)).fetchone()
    if not row:
        return None
    try:
        parsed = json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _composer_list(payload: dict[str, Any]) -> list[dict[str, Any]] | None:
    comps = payload.get("allComposers")
    if isinstance(comps, list):
        return comps
    if isinstance(payload.get("composers"), list):
        return payload["composers"]
    return None


def load_composer_stores() -> list[ComposerStore]:
    stores: list[ComposerStore] = []
    seen: set[tuple[str, str]] = set()
    for db_path in [global_state_db(), *iter_workspace_state_dbs()]:
        if not db_path.is_file():
            continue
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            for key in COMPOSER_KEYS:
                payload = _read_json_value(conn, key)
                if not payload:
                    continue
                comps = _composer_list(payload)
                if comps is None:
                    continue
                sig = (str(db_path), key)
                if sig in seen:
                    continue
                seen.add(sig)
                stores.append(
                    ComposerStore(
                        db_path=db_path,
                        key=key,
                        payload=payload,
                        composers=comps,
                    )
                )
        finally:
            conn.close()
    return stores


def _activity_ms(composer: dict[str, Any]) -> int:
    values: list[int] = []
    for key in (
        "lastUpdatedAt",
        "conversationCheckpointLastUpdatedAt",
        "createdAt",
    ):
        raw = composer.get(key)
        if isinstance(raw, (int, float)) and raw > 0:
            values.append(int(raw))
    return max(values) if values else 0


def is_composer_pinned(composer: dict[str, Any]) -> bool:
    for key in ("isPinned", "pinned", "isFavorited", "isFavorite"):
        if composer.get(key) is True:
            return True
    return False


def is_subagent_composer(composer: dict[str, Any]) -> bool:
    info = composer.get("subagentInfo")
    return isinstance(info, dict) and bool(info.get("parentComposerId"))


def normalize_composer(composer: dict[str, Any]) -> ComposerEntry | None:
    composer_id = composer.get("composerId")
    if not isinstance(composer_id, str) or not composer_id:
        return None
    if composer_id in ("empty-state-draft",):
        return None
    return ComposerEntry(
        composer_id=composer_id,
        name=str(composer.get("name") or composer.get("subtitle") or composer_id),
        is_archived=bool(composer.get("isArchived")),
        is_pinned=is_composer_pinned(composer),
        is_draft=bool(composer.get("isDraft")),
        is_subagent=is_subagent_composer(composer),
        last_activity_ms=_activity_ms(composer),
        raw=composer,
    )


def merge_composer_entries(stores: list[ComposerStore]) -> dict[str, ComposerEntry]:
    merged: dict[str, ComposerEntry] = {}
    for store in stores:
        for composer in store.composers:
            entry = normalize_composer(composer)
            if not entry:
                continue
            prev = merged.get(entry.composer_id)
            if prev is None or entry.last_activity_ms >= prev.last_activity_ms:
                merged[entry.composer_id] = entry
    return merged


def is_protected(entry: ComposerEntry, *, current_composer_id: str | None) -> bool:
    if entry.is_pinned:
        return True
    if entry.is_draft:
        return True
    if entry.is_subagent:
        return True
    if current_composer_id and entry.composer_id == current_composer_id:
        return True
    return False


def select_archive_targets(
    composers: list[ComposerEntry],
    *,
    stale_days: int = DEFAULT_STALE_DAYS,
    max_active: int = DEFAULT_MAX_ACTIVE,
    now_ms: int | None = None,
    current_composer_id: str | None = None,
) -> list[ArchiveTarget]:
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    stale_cutoff = now - stale_days * MS_PER_DAY
    targets: dict[str, ArchiveTarget] = {}

    active = [c for c in composers if not c.is_archived]
    eligible = [c for c in active if not is_protected(c, current_composer_id=current_composer_id)]

    for entry in eligible:
        if entry.last_activity_ms and entry.last_activity_ms < stale_cutoff:
            targets[entry.composer_id] = ArchiveTarget(
                composer_id=entry.composer_id,
                name=entry.name,
                reason=f"stale>{stale_days}d",
            )

    overflow = max(0, len(eligible) - max_active)
    if overflow:
        sorted_eligible = sorted(
            eligible,
            key=lambda c: (c.last_activity_ms or 0, c.composer_id),
        )
        for entry in sorted_eligible[:overflow]:
            if entry.composer_id not in targets:
                targets[entry.composer_id] = ArchiveTarget(
                    composer_id=entry.composer_id,
                    name=entry.name,
                    reason=f"cap>{max_active}",
                )

    return list(targets.values())


def apply_archives(
    stores: list[ComposerStore],
    target_ids: set[str],
    *,
    dry_run: bool,
) -> tuple[dict[str, int], list[str]]:
    changed_by_db: dict[str, int] = {}
    reverted: list[str] = []
    if not target_ids:
        return changed_by_db, reverted

    for store in stores:
        touched = 0
        for composer in store.composers:
            cid = composer.get("composerId")
            if cid in target_ids and not composer.get("isArchived"):
                composer["isArchived"] = True
                touched += 1
        if not touched:
            continue
        changed_by_db[str(store.db_path)] = touched
        if dry_run:
            continue
        conn = sqlite3.connect(str(store.db_path))
        try:
            conn.execute(
                "UPDATE ItemTable SET value = ? WHERE key = ?",
                (json.dumps(store.payload), store.key),
            )
            conn.commit()
        finally:
            conn.close()

        verify_conn = sqlite3.connect(f"file:{store.db_path}?mode=ro", uri=True)
        try:
            row = verify_conn.execute(
                "SELECT value FROM ItemTable WHERE key = ?",
                (store.key,),
            ).fetchone()
            if row:
                payload = json.loads(row[0])
                comps = _composer_list(payload) or []
                still_active = [
                    c.get("composerId")
                    for c in comps
                    if c.get("composerId") in target_ids and not c.get("isArchived")
                ]
                if still_active:
                    reverted.append(str(store.db_path))
        finally:
            verify_conn.close()
    return changed_by_db, reverted


def load_state() -> dict[str, Any]:
    path = state_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def stop_followup_due(state: dict[str, Any], *, interval_days: int = LEARN_INTERVAL_DAYS) -> bool:
    last = float(state.get("last_stop_followup_epoch", state.get("last_learn_epoch", 0)) or 0)
    return time.time() - last >= interval_days * 86400


def workspace_root_for_messages() -> str:
    ws = infer_workspace_root() or runner_bootstrap_repo().resolve().parent
    return str(ws.resolve())


def build_stop_followup(
    *,
    learn_needed: bool,
    active_non_pinned: int,
    archive_targets: list[ArchiveTarget],
    max_active: int,
) -> str:
    workspace = workspace_root_for_messages()
    parts: list[str] = []
    if learn_needed:
        parts.append(
            "Run /workflow-from-chats for the last 7 days and merge durable prefs into "
            f"{workspace}/AGENTS.md Learned sections (and ~/.cursor/rules/novopay-orchestrator.mdc "
            "only if contradicted)."
        )
    if archive_targets:
        parts.append(
            f"Chat sidebar hygiene: {active_non_pinned} active non-pinned chats "
            f"(target {max_active - 2}-{max_active}). "
            f"Archive {len(archive_targets)} stale/overflow chat(s) with "
            "`bob chat-hygiene --auto` - archive only, never delete."
        )
    elif active_non_pinned > max_active:
        parts.append(
            f"Chat sidebar has {active_non_pinned} active non-pinned chats "
            f"(target {max_active - 2}-{max_active}). "
            "Run `bob chat-hygiene --auto` to archive overflow - archive only, never delete."
        )
    if not parts:
        parts.append(
            f"Routine Novopay hygiene: verify {workspace}/.cursor/skills/ has no duplicate "
            "copies in service repos. Reply briefly: hygiene done or nothing to change."
        )
    else:
        parts.append(
            f"Verify {workspace}/.cursor/skills/ has no duplicate copies in service repos."
        )
    return " ".join(parts)


def parse_hook_stop_json(raw: str) -> dict[str, Any] | None:
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if data.get("status") != "completed":
        return None
    try:
        loop = int(data.get("loop_count", 0))
    except (TypeError, ValueError):
        return None
    if loop != 0:
        return None
    return data


def _current_composer_from_hook(data: dict[str, Any] | None) -> str | None:
    if not data:
        return None
    for key in ("composer_id", "composerId", "conversation_id", "conversationId"):
        val = data.get(key)
        if isinstance(val, str) and val:
            return val
    return None


def run_hygiene(
    *,
    dry_run: bool,
    auto: bool,
    hook: str | None,
    max_active: int,
    stale_days: int,
    learn: bool,
    current_composer_id: str | None,
) -> int:
    stores = load_composer_stores()
    if not stores:
        print("No Cursor composer stores found.", file=sys.stderr)
        return 1

    merged = merge_composer_entries(stores)
    entries = list(merged.values())
    active_non_pinned = [
        e for e in entries if not e.is_archived and not e.is_pinned and not e.is_draft and not e.is_subagent
    ]
    targets = select_archive_targets(
        entries,
        stale_days=stale_days,
        max_active=max_active,
        current_composer_id=current_composer_id,
    )

    state = load_state()
    learn_needed = learn and stop_followup_due(state)

    if hook == "stop":
        if not stop_followup_due(state):
            print("{}")
            return 0
        msg = build_stop_followup(
            learn_needed=learn_needed,
            active_non_pinned=len(active_non_pinned),
            archive_targets=targets,
            max_active=max_active,
        )
        if not dry_run:
            now = time.time()
            state["last_stop_followup_epoch"] = now
            if learn_needed:
                state["last_learn_epoch"] = now
                state["last_learn_iso"] = datetime.now(timezone.utc).isoformat()
            save_state(state)
        print(json.dumps({"followup_message": msg}))
        return 0

    if targets:
        print(
            f"Archive candidates: {len(targets)} "
            f"(active non-pinned={len(active_non_pinned)}, max={max_active}, stale>{stale_days}d)"
        )
        for target in targets[:20]:
            print(f"  - {target.composer_id[:8]}… {target.name[:60]} ({target.reason})")
        if len(targets) > 20:
            print(f"  … and {len(targets) - 20} more")
    else:
        print(
            f"No archive targets (active non-pinned={len(active_non_pinned)}, max={max_active})."
        )

    if dry_run:
        print("(dry-run - no DB writes)")
        return 0

    if not auto and hook != "session":
        try:
            raw = input("Apply archives? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 1
        if raw not in ("y", "yes"):
            print("Cancelled.")
            return 1

    changed, reverted = apply_archives(stores, {t.composer_id for t in targets}, dry_run=False)
    archived_count = sum(changed.values())
    print(f"Archived {archived_count} composer row(s) across {len(changed)} DB file(s).")
    if reverted:
        print(
            "Warning: Cursor may have overwritten archive writes while the IDE is running.",
            file=sys.stderr,
        )
        print(
            "Re-run with Cursor fully quit, or rely on the sessionStart hook on next launch.",
            file=sys.stderr,
        )
        for path in reverted:
            print(f"  reverted: {path}", file=sys.stderr)

    state["last_session_archive_epoch"] = time.time()
    state["last_archive_count"] = archived_count
    state["last_run_iso"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    return 0


def run_chat_hygiene_cli(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archive stale/overflow Cursor chats (never delete).")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Preview only; no DB writes")
    parser.add_argument("--auto", action="store_true", help="Apply without confirmation")
    parser.add_argument("--hook", choices=("stop", "session"), help="Hook mode output/behavior")
    parser.add_argument("--max-active", type=int, default=DEFAULT_MAX_ACTIVE)
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS)
    parser.add_argument("--learn", action="store_true", help="Stop hook: include weekly learn follow-up")
    parser.add_argument("--current-composer-id", default="")
    ns = parser.parse_args(args)

    hook_json = None
    if ns.hook == "stop":
        hook_json = parse_hook_stop_json(os.environ.get("HOOK_STOP_JSON", ""))
        if hook_json is None:
            print("{}")
            return 0

    current_id = ns.current_composer_id.strip() or _current_composer_from_hook(hook_json)
    return run_hygiene(
        dry_run=ns.dry_run,
        auto=ns.auto or ns.hook == "session",
        hook=ns.hook,
        max_active=max(1, ns.max_active),
        stale_days=max(1, ns.stale_days),
        learn=ns.learn or ns.hook == "stop",
        current_composer_id=current_id,
    )
