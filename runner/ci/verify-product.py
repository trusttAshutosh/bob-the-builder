#!/usr/bin/env python3
"""Verify Bob product features; update or check docs/NEXT.md scorecard sections."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_RUNNER_LIB = ROOT / "runner" / "lib"
if str(_RUNNER_LIB) not in sys.path:
    sys.path.insert(0, str(_RUNNER_LIB))

FEATURES_YAML = ROOT / "docs" / "product-features.yaml"
NEXT_MD = ROOT / "docs" / "NEXT.md"
BUILDER_CLI = ROOT / "runner" / "lib" / "builder_cli.py"

MARKER_COMMIT = "<!-- PRODUCT-VERIFY:COMMIT="
MARKER_CHECKED = "<!-- PRODUCT-VERIFY:CHECKED="
SCORECARD_START = "<!-- SCORECARD:START -->"
SCORECARD_END = "<!-- SCORECARD:END -->"
LAST_START = "<!-- LAST_COMMIT:START -->"
LAST_END = "<!-- LAST_COMMIT:END -->"
INTACT_START = "<!-- FEATURES_INTACT:START -->"
INTACT_END = "<!-- FEATURES_INTACT:END -->"


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit("PyYAML required: pip install pyyaml") from exc
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _git(*args: str) -> str:
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if r.returncode != 0:
            return ""
        return (r.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def head_commit() -> str:
    return _git("rev-parse", "HEAD") or "none"


def has_commits() -> bool:
    return bool(_git("rev-parse", "HEAD"))


def last_commit_info() -> dict:
    if not has_commits():
        return {
            "hash": "none",
            "hash_short": "none",
            "subject": "(no commits yet)",
            "date": date.today().isoformat(),
            "files": [],
        }
    h = _git("rev-parse", "HEAD")
    subject = _git("log", "-1", "--format=%s")
    when = _git("log", "-1", "--format=%ci")
    files = [ln for ln in _git("show", "--name-only", "--format=", "HEAD").splitlines() if ln.strip()]
    return {
        "hash": h,
        "hash_short": h[:7] if h else "none",
        "subject": subject or "(empty)",
        "date": (when.split()[0] if when else date.today().isoformat()),
        "files": files,
    }


def _cli_commands() -> set[str]:
    text = BUILDER_CLI.read_text(encoding="utf-8")
    cmds: set[str] = set()
    # Canonical handler keys
    block = re.search(r"handlers\s*=\s*\{", text)
    if block:
        rest = text[block.start() :]
        end = rest.find("\n    }")
        chunk = rest[: end if end > 0 else 2000]
        cmds |= set(re.findall(r'"([a-z-]+)":\s*cmd_', chunk))
        cmds |= set(re.findall(r'"([a-z-]+)":\s*lambda', chunk))
    # CMD_ALIASES resolved targets
    if "CMD_ALIASES" in text:
        alias_block = text.split("CMD_ALIASES", 1)[1].split("\n}", 1)[0]
        cmds |= set(re.findall(r':\s*"([a-z-]+)"', alias_block))
    return cmds


def _feature_paths(feature: dict) -> list[Path]:
    out: list[Path] = []
    for rel in feature.get("paths") or []:
        out.append(ROOT / rel.replace("/", "\\") if "\\" in str(ROOT) else ROOT / rel)
    return out


def check_feature(feature: dict, commands: set[str]) -> tuple[bool, str]:
    fid = feature.get("id", "?")
    missing: list[str] = []
    for cmd in feature.get("commands") or []:
        if cmd not in commands and cmd not in {"help", "version"}:
            missing.append(f"command:{cmd}")
    for path in _feature_paths(feature):
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)).replace("\\", "/"))
    for rule in feature.get("file_contains") or []:
        rel = rule["file"]
        needle = rule["needle"]
        p = ROOT / rel
        if not p.is_file():
            missing.append(rel)
        elif needle not in p.read_text(encoding="utf-8"):
            missing.append(f"{rel} (missing text: {needle!r})")
    if missing:
        return False, "; ".join(missing)
    return True, "ok"


def verify_all() -> tuple[list[dict], list[dict]]:
    data = _load_yaml(FEATURES_YAML)
    commands = _cli_commands()
    ok_list: list[dict] = []
    fail_list: list[dict] = []
    for feat in data.get("features") or []:
        passed, detail = check_feature(feat, commands)
        row = {
            "id": feat.get("id"),
            "name": feat.get("name"),
            "detail": detail,
        }
        if passed:
            ok_list.append(row)
        else:
            fail_list.append(row)
    return ok_list, fail_list


def _features_touched(files: list[str], features: list[dict]) -> tuple[list[str], list[str]]:
    if not files:
        return [], []
    added_labels: list[str] = []
    removed_guess: list[str] = []
    for feat in features:
        fid = feat.get("id", "")
        name = feat.get("name", fid)
        rel_paths = [p.replace("\\", "/") for p in (feat.get("paths") or [])]
        rel_cmds = feat.get("commands") or []
        hit = any(
            any(f == rp or f.startswith(rp.rstrip("/") + "/") for rp in rel_paths)
            for f in files
        )
        if hit:
            added_labels.append(f"{name} (`{fid}`) — files touched")
    return added_labels, removed_guess


def _replace_block(text: str, start: str, end: str, body: str) -> str:
    pattern = re.escape(start) + r".*?" + re.escape(end)
    block = f"{start}\n{body.rstrip()}\n{end}"
    if start in text and end in text:
        return re.sub(pattern, block, text, count=1, flags=re.DOTALL)
    return text + "\n\n" + block + "\n"


def _update_meta_lines(text: str, commit: str, checked: str) -> str:
    text = re.sub(r"<!-- PRODUCT-VERIFY:COMMIT=[^>]+-->", f"{MARKER_COMMIT}{commit} -->", text)
    text = re.sub(
        r"<!-- PRODUCT-VERIFY:CHECKED=[^>]+-->",
        f"{MARKER_CHECKED}{checked} -->",
        text,
    )
    if MARKER_COMMIT not in text:
        text = text.replace(
            "**Living backlog.**",
            f"**Living backlog.**\n\n{MARKER_COMMIT}{commit} -->\n{MARKER_CHECKED}{checked} -->",
            1,
        )
    return text


def render_scorecard_footer(ok: int, total: int, info: dict) -> str:
    return (
        f"*Last feature check: {info['date']} · commit `{info['hash_short']}` · "
        f"{ok}/{total} features intact · auto-refreshed after commit via post-commit hook*"
    )


def render_last_commit(info: dict, touched: list[str], ok: int, total: int) -> str:
    lines = [
        f"**Commit:** `{info['hash_short']}` — {info['subject']}",
        f"**Date:** {info['date']}",
        "",
        "### Files changed",
    ]
    if info["files"]:
        lines.extend(f"- `{f}`" for f in info["files"][:40])
        if len(info["files"]) > 40:
            lines.append(f"- … and {len(info['files']) - 40} more")
    else:
        lines.append("- (none — no commits yet)")
    lines.extend(["", "### Features touched in this commit"])
    if touched:
        lines.extend(f"- {t}" for t in touched)
    else:
        lines.append("- (none mapped — docs-only or infra)")
    lines.extend(
        [
            "",
            "### Regression check",
            f"- **{ok}/{total} registered features still intact** after this commit (see below).",
            "- Removing a feature requires updating `docs/product-features.yaml` and scorecard notes.",
        ]
    )
    return "\n".join(lines)


def render_intact(ok_list: list[dict], fail_list: list[dict]) -> str:
    lines = [
        "| Feature | ID | Status |",
        "|---------|-----|--------|",
    ]
    for row in ok_list:
        lines.append(f"| {row['name']} | `{row['id']}` | intact |")
    for row in fail_list:
        lines.append(f"| {row['name']} | `{row['id']}` | **MISSING** — {row['detail']} |")
    lines.extend(
        [
            "",
            f"**Total:** {len(ok_list)} intact, {len(fail_list)} missing.",
            "",
            "Source: [`docs/product-features.yaml`](product-features.yaml) · "
            "Verifier: `runner/ci/verify-product.py`",
        ]
    )
    return "\n".join(lines)


def read_stored_commit(text: str) -> str:
    m = re.search(r"<!-- PRODUCT-VERIFY:COMMIT=([^>]+) -->", text)
    return (m.group(1).strip() if m else "") or "none"


def build_scorecard_block(ok: int, total: int, info: dict, existing: str) -> str:
    """Preserve manual grade table inside scorecard; refresh footer only."""
    if SCORECARD_START in existing and SCORECARD_END in existing:
        inner = existing.split(SCORECARD_START, 1)[1].split(SCORECARD_END, 1)[0]
        # Replace old footer line if present
        inner = re.sub(
            r"\*Last feature check:.*?\*",
            render_scorecard_footer(ok, total, info),
            inner,
            flags=re.DOTALL,
        )
        if "*Last feature check:" not in inner:
            inner = inner.rstrip() + "\n\n" + render_scorecard_footer(ok, total, info) + "\n"
        return inner.strip()

    return (
        "## Current scorecard\n\n"
        "(Run --update after adding SCORECARD markers.)\n\n"
        + render_scorecard_footer(ok, total, info)
    )


def update_next_md(ok_list: list[dict], fail_list: list[dict], info: dict, features: list[dict]) -> None:
    text = NEXT_MD.read_text(encoding="utf-8")
    ok, total = len(ok_list), len(ok_list) + len(fail_list)
    touched, _ = _features_touched(info["files"], features)
    commit = info["hash_short"]

    scorecard_body = build_scorecard_block(ok, total, info, text)
    text = _replace_block(text, SCORECARD_START, SCORECARD_END, scorecard_body)
    text = _replace_block(
        text,
        LAST_START,
        LAST_END,
        render_last_commit(info, touched, ok, total),
    )
    text = _replace_block(text, INTACT_START, INTACT_END, render_intact(ok_list, fail_list))
    text = _update_meta_lines(text, commit, date.today().isoformat())
    NEXT_MD.write_text(text, encoding="utf-8")


def cmd_check(args: argparse.Namespace) -> int:
    ok_list, fail_list = verify_all()
    if fail_list:
        print("Product feature check FAILED:", file=sys.stderr)
        for row in fail_list:
            print(f"  - {row['id']}: {row['detail']}", file=sys.stderr)
        return 1

    if not NEXT_MD.is_file():
        print("Missing docs/NEXT.md", file=sys.stderr)
        return 1

    text = NEXT_MD.read_text(encoding="utf-8")
    for marker in (SCORECARD_START, LAST_START, INTACT_START):
        if marker not in text:
            print(f"Missing section marker in NEXT.md: {marker}", file=sys.stderr)
            print("Run: python runner/ci/verify-product.py --update", file=sys.stderr)
            return 1

    stored = read_stored_commit(text)
    head = head_commit()
    head_short = head[:7] if head != "none" else "none"

    if has_commits() and stored not in {head, head_short, "none"}:
        print(
            f"NOTE: NEXT.md verify stamp is `{stored}`; HEAD is `{head_short}` "
            "(normal after a new commit — run --update when convenient).",
            file=sys.stderr,
        )
        if args.strict:
            print("Strict mode: run bob verify-product --update and commit docs/NEXT.md.", file=sys.stderr)
            return 1

    from builder_intel_sync import verify_builder_intel_sync

    intel_ok, intel_msg = verify_builder_intel_sync(ROOT)
    if not intel_ok:
        print(intel_msg, file=sys.stderr)
        if args.strict:
            return 1

    print(f"Product features OK ({len(ok_list)}/{len(ok_list)} intact).")
    print(f"NEXT.md verify stamp: {stored} (HEAD: {head_short})")
    if intel_ok:
        print(intel_msg)
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    ok_list, fail_list = verify_all()
    if fail_list and not args.allow_missing:
        print("Cannot update NEXT.md — features missing:", file=sys.stderr)
        for row in fail_list:
            print(f"  - {row['id']}: {row['detail']}", file=sys.stderr)
        return 1

    data = _load_yaml(FEATURES_YAML)
    info = last_commit_info()
    update_next_md(ok_list, fail_list, info, data.get("features") or [])
    print(f"Updated {NEXT_MD}")
    print(f"  Features: {len(ok_list)} intact, {len(fail_list)} missing")
    print(f"  Commit stamp: {info['hash_short']}")

    from builder_intel_sync import sync_builder_intel

    changed, msg = sync_builder_intel(ROOT, write=True)
    print(msg)

    from sample_outputs import refresh_sample_outputs, should_refresh_samples

    if should_refresh_samples(info.get("files")):
        refresh_sample_outputs(product_root=ROOT, quiet=False)
        print(f"Refreshed {ROOT / 'assets/examples/sample-validate-output'}")
    return 0 if not fail_list else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Verify Bob product features and NEXT.md sections")
    p.add_argument("--check", action="store_true", help="CI mode: fail if features or NEXT stamp stale")
    p.add_argument("--update", action="store_true", help="Refresh NEXT.md auto sections")
    p.add_argument("--strict", action="store_true", help="Fail if NEXT.md verify stamp != HEAD")
    p.add_argument("--allow-missing", action="store_true", help="Update NEXT.md even if checks fail")
    args = p.parse_args()
    if args.check:
        return cmd_check(args)
    if args.update:
        return cmd_update(args)
    # default: check only
    args.check = True
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
