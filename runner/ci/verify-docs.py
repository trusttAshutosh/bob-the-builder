#!/usr/bin/env python3
"""Verify Bob product docs match doc-invariants.yaml and CLI reality."""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_RUNNER_LIB = ROOT / "runner" / "lib"
if str(_RUNNER_LIB) not in sys.path:
    sys.path.insert(0, str(_RUNNER_LIB))

INVARIANTS_YAML = ROOT / "docs" / "doc-invariants.yaml"
FEATURES_YAML = ROOT / "docs" / "product-features.yaml"
BUILDER_CLI = ROOT / "runner" / "lib" / "builder_cli.py"
HELP_FN = "_print_help"


@dataclass
class Finding:
    rule_id: str
    detail: str


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit("PyYAML required: pip install pyyaml") from exc
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _cli_commands() -> set[str]:
    text = BUILDER_CLI.read_text(encoding="utf-8")
    cmds: set[str] = set()
    block = re.search(r"handlers\s*=\s*\{", text)
    if block:
        rest = text[block.start() :]
        end = rest.find("\n    }")
        chunk = rest[: end if end > 0 else 4000]
        cmds |= set(re.findall(r'"([a-z-]+)":\s*cmd_', chunk))
        cmds |= set(re.findall(r'"([a-z-]+)":\s*lambda', chunk))
    if "CMD_ALIASES" in text:
        alias_block = text.split("CMD_ALIASES", 1)[1].split("\n}", 1)[0]
        cmds |= set(re.findall(r':\s*"([a-z-]+)"', alias_block))
    return cmds


def _expand_files(patterns: list[str]) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for pat in patterns:
        pat = pat.replace("\\", "/")
        if "**" in pat:
            matches = ROOT.glob(pat)
        else:
            p = ROOT / pat
            matches = [p] if p.is_file() else []
        for path in matches:
            rp = path.resolve()
            if rp.is_file() and rp not in seen:
                seen.add(rp)
                out.append(path)
    return sorted(out, key=lambda p: str(p).replace("\\", "/"))


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def check_required_files(data: dict) -> list[Finding]:
    findings: list[Finding] = []
    for rel in data.get("required_files") or []:
        path = ROOT / rel.replace("/", "\\") if "\\" in str(ROOT) else ROOT / rel
        if not path.is_file():
            findings.append(Finding("required_files", f"missing file: {rel}"))
    return findings


def check_content_rules(data: dict) -> list[Finding]:
    findings: list[Finding] = []
    for rule in data.get("content_rules") or []:
        rid = rule.get("id", "content")
        for rel in rule.get("files") or []:
            path = ROOT / rel
            if not path.is_file():
                findings.append(Finding(rid, f"missing file: {rel}"))
                continue
            text = _read(path)
            for needle in rule.get("must_contain") or []:
                if needle not in text:
                    findings.append(Finding(rid, f"{rel}: missing {needle!r}"))
            for needle in rule.get("must_not_contain") or []:
                if needle in text:
                    findings.append(Finding(rid, f"{rel}: forbidden {needle!r}"))
    return findings


def check_conditional_rules(data: dict) -> list[Finding]:
    findings: list[Finding] = []
    for rule in data.get("conditional_rules") or []:
        rid = rule.get("id", "conditional")
        trigger = rule.get("when_contains", "")
        required = rule.get("must_also_contain") or []
        if not trigger:
            continue
        for path in _expand_files(rule.get("files") or []):
            text = _read(path)
            if trigger not in text:
                continue
            rel = _rel(path)
            for needle in required:
                if needle not in text:
                    findings.append(Finding(rid, f"{rel}: mentions {trigger!r} but missing {needle!r}"))
    return findings


def check_forbidden_in_docs(data: dict) -> list[Finding]:
    findings: list[Finding] = []
    block = data.get("forbidden_in_docs") or {}
    exclude = {x.replace("\\", "/") for x in (block.get("exclude_files") or [])}
    patterns = block.get("patterns") or []
    for path in _expand_files(block.get("scan_globs") or []):
        rel = _rel(path)
        if rel in exclude:
            continue
        text = _read(path)
        for item in patterns:
            pid = item.get("id", "forbidden")
            needle = item.get("needle", "")
            if needle and needle in text:
                findings.append(Finding(pid, f"{rel}: forbidden text {needle!r}"))
    return findings


def _cheatsheet_commands(cheatsheet_text: str, skip_rows: list[str]) -> set[str]:
    cmds: set[str] = set()
    for line in cheatsheet_text.splitlines():
        if not line.strip().startswith("| `bob "):
            continue
        if any(skip in line for skip in skip_rows):
            continue
        match = re.match(r"\|\s*`bob ([a-z][a-z0-9-]*)", line.strip())
        if match:
            cmds.add(match.group(1))
    return cmds


def check_cheatsheet_commands(data: dict, cli: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    block = data.get("cheatsheet") or {}
    rel = block.get("file", "docs/BOB_CHEATSHEET.md")
    path = ROOT / rel
    if not path.is_file():
        return [Finding("cheatsheet", f"missing {rel}")]
    text = _read(path)
    skip = block.get("skip_rows_containing") or []
    found = _cheatsheet_commands(text, skip)
    for extra in block.get("extra_commands") or []:
        found.add(extra)
    for cmd in sorted(found):
        if cmd not in cli:
            findings.append(Finding("cheatsheet", f"`bob {cmd}` in {rel} but not in CLI handlers"))
    return findings


def check_feature_commands_in_cheatsheet(data: dict) -> list[Finding]:
    findings: list[Finding] = []
    block = data.get("feature_commands_in_cheatsheet") or {}
    cheat_rel = block.get("file", "docs/BOB_CHEATSHEET.md")
    cheat_path = ROOT / cheat_rel
    if not cheat_path.is_file():
        return [Finding("feature_commands_in_cheatsheet", f"missing {cheat_rel}")]
    cheat_text = _read(cheat_path)
    skip = set(block.get("skip_commands") or [])
    features = _load_yaml(FEATURES_YAML).get("features") or []
    for feat in features:
        for cmd in feat.get("commands") or []:
            if cmd in skip:
                continue
            token = f"bob {cmd}"
            if token not in cheat_text and f"`bob {cmd}" not in cheat_text:
                findings.append(
                    Finding(
                        "feature_commands_in_cheatsheet",
                        f"registered command `{cmd}` ({feat.get('id')}) not documented in {cheat_rel}",
                    )
                )
    return findings


def check_cli_help_contract(data: dict) -> list[Finding]:
    findings: list[Finding] = []
    import io
    from contextlib import redirect_stdout

    import builder_cli

    buf = io.StringIO()
    with redirect_stdout(buf):
        builder_cli._print_help()
    help_text = buf.getvalue()
    for rule in data.get("cli_help_contract") or []:
        cmd = rule.get("command", "")
        needle = rule.get("must_contain", "")
        if needle and needle not in help_text:
            findings.append(Finding("cli_help_contract", f"help missing {needle!r} (command {cmd})"))
    return findings


def _is_external_link(target: str) -> bool:
    t = target.strip()
    return t.startswith("http://") or t.startswith("https://") or t.startswith("mailto:")


def check_markdown_links(data: dict) -> list[Finding]:
    findings: list[Finding] = []
    block = data.get("markdown_links") or {}
    exclude = {x.replace("\\", "/") for x in (block.get("exclude_files") or [])}
    link_re = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for path in _expand_files(block.get("scan_globs") or []):
        rel = _rel(path)
        if rel in exclude:
            continue
        text = _read(path)
        for match in link_re.finditer(text):
            target = match.group(1).strip()
            if not target or target.startswith("#") or _is_external_link(target):
                continue
            target = target.split("#", 1)[0].strip()
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                findings.append(Finding("markdown_links", f"{rel}: link target outside repo: {target!r}"))
                continue
            if not resolved.exists():
                findings.append(Finding("markdown_links", f"{rel}: broken link {target!r}"))
    return findings


def verify_all(data: dict | None = None) -> tuple[list[Finding], dict[str, int]]:
    data = data or _load_yaml(INVARIANTS_YAML)
    cli = _cli_commands()
    groups: list[tuple[str, list[Finding]]] = [
        ("required_files", check_required_files(data)),
        ("content_rules", check_content_rules(data)),
        ("conditional_rules", check_conditional_rules(data)),
        ("forbidden_in_docs", check_forbidden_in_docs(data)),
        ("cheatsheet", check_cheatsheet_commands(data, cli)),
        ("feature_commands_in_cheatsheet", check_feature_commands_in_cheatsheet(data)),
        ("cli_help_contract", check_cli_help_contract(data)),
        ("markdown_links", check_markdown_links(data)),
    ]
    findings: list[Finding] = []
    counts: dict[str, int] = {}
    for name, items in groups:
        counts[name] = len(items)
        findings.extend(items)
    return findings, counts


def main() -> int:
    p = argparse.ArgumentParser(description="Verify Bob doc invariants against product reality")
    p.add_argument("--check", action="store_true", help="Run checks (default)")
    p.add_argument("--list-rules", action="store_true", help="Print rule ids from doc-invariants.yaml")
    args = p.parse_args()

    if not INVARIANTS_YAML.is_file():
        print(f"Missing {INVARIANTS_YAML}", file=sys.stderr)
        return 1

    data = _load_yaml(INVARIANTS_YAML)

    if args.list_rules:
        for rule in data.get("content_rules") or []:
            print(rule.get("id", "?"))
        for rule in data.get("conditional_rules") or []:
            print(rule.get("id", "?"))
        return 0

    findings, counts = verify_all(data)
    if findings:
        print("Doc invariant check FAILED:", file=sys.stderr)
        by_rule: dict[str, list[str]] = {}
        for f in findings:
            by_rule.setdefault(f.rule_id, []).append(f.detail)
        for rid, details in sorted(by_rule.items()):
            print(f"  [{rid}]", file=sys.stderr)
            for detail in details:
                print(f"    - {detail}", file=sys.stderr)
        print(
            f"Summary: {len(findings)} failure(s) across "
            + ", ".join(f"{k}={v}" for k, v in counts.items() if v),
            file=sys.stderr,
        )
        return 1

    print("Doc invariants OK.")
    print(f"  Rules checked: {len(data.get('content_rules') or [])} content, "
          f"{len(data.get('conditional_rules') or [])} conditional, "
          f"{len((data.get('forbidden_in_docs') or {}).get('patterns') or [])} forbidden patterns")
    print(f"  CLI commands registered: {len(_cli_commands())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
