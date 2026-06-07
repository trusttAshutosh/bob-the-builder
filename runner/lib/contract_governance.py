"""Detect contract weakening and require recorded human approval."""
from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONTRACT_FILES = (
    "docs/doc-invariants.yaml",
    "docs/product-features.yaml",
)
GOVERNANCE_REL = "docs/contract-governance.yaml"
APPROVALS_DIR_REL = "docs/contract-approvals"
INDEX_REL = f"{APPROVALS_DIR_REL}/index.yaml"


@dataclass
class Weakening:
    file: str
    kind: str
    detail: str

    def key(self) -> tuple[str, str, str]:
        return (self.file, self.kind, self.detail)


@dataclass
class ContractDiff:
    base_ref: str
    head_ref: str
    changed_files: list[str] = field(default_factory=list)
    weakenings: list[Weakening] = field(default_factory=list)

    @property
    def weakened(self) -> bool:
        return bool(self.weakenings)


def product_root(root: Path | None = None) -> Path:
    if root is not None:
        return root.resolve()
    from bob_home import bob_product_root

    return bob_product_root().resolve()


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit("PyYAML required: pip install pyyaml") from exc
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def file_sha256(root: Path, rel: str) -> str:
    path = root / rel
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(root: Path, *args: str) -> str:
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if r.returncode != 0:
            return ""
        return (r.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def git_show(root: Path, ref: str, rel: str) -> str | None:
    out = _git(root, "show", f"{ref}:{rel}")
    return out if out else None


def resolve_base_ref(root: Path, vs: str | None) -> str:
    if vs:
        return vs
    for candidate in ("origin/main", "origin/master", "main", "master", "HEAD~1"):
        if candidate.startswith("HEAD"):
            return candidate
        if _git(root, "rev-parse", "--verify", candidate):
            return candidate
    return "HEAD~1"


def _summarize_invariants(data: dict[str, Any]) -> dict[str, Any]:
    content: dict[str, set[str]] = {}
    for rule in data.get("content_rules") or []:
        rid = str(rule.get("id", ""))
        content[rid] = {str(x) for x in (rule.get("must_contain") or [])}
    conditional = {str(r.get("id", "")) for r in (data.get("conditional_rules") or []) if r.get("id")}
    forbidden = {
        str(p.get("id", ""))
        for p in ((data.get("forbidden_in_docs") or {}).get("patterns") or [])
        if p.get("id")
    }
    required = {str(x) for x in (data.get("required_files") or [])}
    skip_commands = {
        str(x) for x in ((data.get("feature_commands_in_cheatsheet") or {}).get("skip_commands") or [])
    }
    skip_rows = {str(x) for x in ((data.get("cheatsheet") or {}).get("skip_rows_containing") or [])}
    return {
        "content": content,
        "conditional": conditional,
        "forbidden": forbidden,
        "required": required,
        "skip_commands": skip_commands,
        "skip_rows": skip_rows,
    }


def _summarize_features(data: dict[str, Any]) -> dict[str, Any]:
    features: dict[str, dict[str, Any]] = {}
    for feat in data.get("features") or []:
        fid = str(feat.get("id", ""))
        features[fid] = {
            "commands": {str(x) for x in (feat.get("commands") or [])},
            "paths": {str(x) for x in (feat.get("paths") or [])},
            "file_contains": {
                (str(r.get("file", "")), str(r.get("needle", "")))
                for r in (feat.get("file_contains") or [])
                if r.get("file") and r.get("needle")
            },
        }
    return {"features": features}


def _diff_invariants(old: dict[str, Any], new: dict[str, Any], rel: str) -> list[Weakening]:
    o = _summarize_invariants(old)
    n = _summarize_invariants(new)
    out: list[Weakening] = []

    for path in sorted(o["required"] - n["required"]):
        out.append(Weakening(rel, "removed_required_file", path))

    for rid in sorted(set(o["content"]) - set(n["content"])):
        out.append(Weakening(rel, "removed_content_rule", rid))

    for rid in sorted(set(o["content"]) & set(n["content"])):
        for needle in sorted(o["content"][rid] - n["content"][rid]):
            out.append(Weakening(rel, "removed_must_contain", f"{rid}: {needle!r}"))

    for rid in sorted(o["conditional"] - n["conditional"]):
        out.append(Weakening(rel, "removed_conditional_rule", rid))

    for pid in sorted(o["forbidden"] - n["forbidden"]):
        out.append(Weakening(rel, "removed_forbidden_pattern", pid))

    for cmd in sorted(n["skip_commands"] - o["skip_commands"]):
        out.append(Weakening(rel, "expanded_skip_commands", cmd))

    for row in sorted(n["skip_rows"] - o["skip_rows"]):
        out.append(Weakening(rel, "expanded_skip_rows", row))

    return out


def _diff_features(old: dict[str, Any], new: dict[str, Any], rel: str) -> list[Weakening]:
    o = _summarize_features(old)
    n = _summarize_features(new)
    out: list[Weakening] = []
    old_feats = o["features"]
    new_feats = n["features"]

    for fid in sorted(set(old_feats) - set(new_feats)):
        out.append(Weakening(rel, "removed_feature", fid))

    for fid in sorted(set(old_feats) & set(new_feats)):
        oc, nc = old_feats[fid]["commands"], new_feats[fid]["commands"]
        op, np = old_feats[fid]["paths"], new_feats[fid]["paths"]
        ofc, nfc = old_feats[fid]["file_contains"], new_feats[fid]["file_contains"]
        for cmd in sorted(oc - nc):
            out.append(Weakening(rel, "removed_feature_command", f"{fid}:{cmd}"))
        for path in sorted(op - np):
            out.append(Weakening(rel, "removed_feature_path", f"{fid}:{path}"))
        for item in sorted(ofc - nfc):
            out.append(Weakening(rel, "removed_file_contains", f"{fid}:{item[0]}:{item[1]!r}"))

    return out


def diff_contract_text(rel: str, old_text: str | None, new_text: str | None) -> list[Weakening]:
    if old_text is None or new_text is None or old_text == new_text:
        return []
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit("PyYAML required: pip install pyyaml") from exc
    old = yaml.safe_load(old_text) or {}
    new = yaml.safe_load(new_text) or {}
    if rel.endswith("doc-invariants.yaml"):
        return _diff_invariants(old, new, rel)
    if rel.endswith("product-features.yaml"):
        return _diff_features(old, new, rel)
    return []


def diff_contracts(root: Path, base_ref: str, head_ref: str = "HEAD") -> ContractDiff:
    root = product_root(root)
    diff = ContractDiff(base_ref=base_ref, head_ref=head_ref)
    for rel in CONTRACT_FILES:
        old_text = git_show(root, base_ref, rel) if base_ref != "EMPTY" else None
        if head_ref == "STAGED":
            new_text = _git(root, "show", f":{rel}") or None
        elif head_ref == "WORKTREE":
            path = root / rel
            new_text = path.read_text(encoding="utf-8") if path.is_file() else None
        else:
            new_text = git_show(root, head_ref, rel) if head_ref != "EMPTY" else None
        if old_text == new_text:
            continue
        if old_text is None and new_text is None:
            continue
        diff.changed_files.append(rel)
        diff.weakenings.extend(diff_contract_text(rel, old_text, new_text))
    return diff


def load_all_approvals(root: Path) -> list[dict[str, Any]]:
    root = product_root(root)
    entries: list[dict[str, Any]] = []
    index = _load_yaml(root / INDEX_REL)
    entries.extend(index.get("approvals") or [])
    approvals_dir = root / APPROVALS_DIR_REL
    if approvals_dir.is_dir():
        for path in sorted(approvals_dir.glob("*.yaml")):
            if path.name == "index.yaml":
                continue
            data = _load_yaml(path)
            if data.get("id"):
                entries.append(data)
    return entries


def _weakening_keys(items: list[Weakening | dict[str, Any]]) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for item in items:
        if isinstance(item, Weakening):
            keys.add(item.key())
        else:
            keys.add((str(item.get("file", "")), str(item.get("kind", "")), str(item.get("detail", ""))))
    return keys


def approval_covers(root: Path, diff: ContractDiff) -> tuple[bool, str]:
    if not diff.weakened:
        return True, "No contract weakening detected."

    current_hashes = {rel: file_sha256(root, rel) for rel in diff.changed_files}
    required = _weakening_keys(diff.weakenings)

    for entry in load_all_approvals(root):
        hashes = entry.get("file_hashes") or {}
        if not all(current_hashes.get(rel) == hashes.get(rel) for rel in diff.changed_files):
            continue
        approved = _weakening_keys(entry.get("weakenings") or [])
        if not required.issubset(approved):
            continue
        return True, f"Approved by {entry.get('approver', '?')} — {entry.get('reason', '')}"

    return False, (
        "Contract weakened without matching human approval. "
        'Run: bob contract-diff && bob approve-contract-change --reason "..."'
    )


def verify_governance(root: Path | None = None, *, base_ref: str | None = None) -> tuple[int, str]:
    root = product_root(root)
    base = resolve_base_ref(root, base_ref)
    diff = diff_contracts(root, base_ref=base, head_ref="HEAD")
    if not diff.changed_files:
        return 0, f"Contract unchanged vs {base}."
    if not diff.weakened:
        return 0, f"Contract changed vs {base} (strengthening/neutral only)."
    ok, msg = approval_covers(root, diff)
    if ok:
        return 0, msg
    lines = [msg, "", "Weakenings:"]
    for w in diff.weakenings:
        lines.append(f"  - [{w.file}] {w.kind}: {w.detail}")
    return 1, "\n".join(lines)


def format_contract_diff_report(diff: ContractDiff) -> str:
    lines = [
        f"Contract diff: {diff.base_ref} -> {diff.head_ref}",
        f"Changed files: {', '.join(diff.changed_files) or '(none)'}",
        "",
    ]
    if not diff.weakened:
        lines.append("Weakenings: none (strengthening or neutral edits only).")
        return "\n".join(lines)
    lines.append("Weakenings (require human approval before merge/commit):")
    for w in diff.weakenings:
        lines.append(f"  - [{w.file}] {w.kind}: {w.detail}")
    lines.extend(
        [
            "",
            "Impact: CI/doc checks may pass with fewer guards — wrong or incomplete docs can return.",
            'Next: bob approve-contract-change --reason "..."  (you must type APPROVE)',
        ]
    )
    return "\n".join(lines)


def _slug(text: str, limit: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:limit] or "change").strip("-")


def write_approval(
    root: Path,
    *,
    reason: str,
    approver: str,
    diff: ContractDiff,
) -> Path:
    root = product_root(root)
    if not diff.weakened:
        raise ValueError("No contract weakening to approve.")

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    approval_id = f"{ts}-{_slug(reason)}"
    file_hashes = {rel: file_sha256(root, rel) for rel in diff.changed_files}
    record = {
        "id": approval_id,
        "approved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "approver": approver,
        "reason": reason.strip(),
        "file_hashes": file_hashes,
        "weakenings": [{"file": w.file, "kind": w.kind, "detail": w.detail} for w in diff.weakenings],
    }

    out_dir = root / APPROVALS_DIR_REL
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{approval_id}.yaml"
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit("PyYAML required: pip install pyyaml") from exc
    out_path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True), encoding="utf-8")

    index_path = root / INDEX_REL
    index = _load_yaml(index_path)
    index.setdefault("version", 1)
    index.setdefault("approvals", [])
    index["approvals"] = [e for e in index["approvals"] if e.get("id") != approval_id]
    index["approvals"].append(
        {
            "id": approval_id,
            "approved_at": record["approved_at"],
            "approver": approver,
            "reason": reason.strip(),
            "file": str(out_path.relative_to(root)).replace("\\", "/"),
        }
    )
    index_path.write_text(yaml.safe_dump(index, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return out_path


def verify_staged_commit(root: Path | None = None) -> tuple[int, str]:
    root = product_root(root)
    diff = diff_contracts(root, base_ref="HEAD", head_ref="STAGED")
    if not diff.weakened:
        return 0, "Staged contract changes OK."
    ok, msg = approval_covers(root, diff)
    if ok:
        return 0, msg
    staged_approvals = _git(root, "diff", "--cached", "--name-only", "--", APPROVALS_DIR_REL)
    if staged_approvals.strip():
        return (
            1,
            "Contract weakened and approval file is staged, but hashes/weakenings do not match. "
            "Run bob approve-contract-change after final contract edits.",
        )
    return (
        1,
        msg + "\n\nStaged commit blocked. Run bob approve-contract-change and stage the approval YAML.",
    )
