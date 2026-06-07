"""Tests for contract governance (weakening detection + approval)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from contract_governance import (  # noqa: E402
    Weakening,
    approval_covers,
    diff_contract_text,
    write_approval,
)


def test_detect_removed_must_contain() -> None:
    old = """
content_rules:
  - id: rule-a
    files: [README.md]
    must_contain: [alpha, beta]
"""
    new = """
content_rules:
  - id: rule-a
    files: [README.md]
    must_contain: [alpha]
"""
    hits = diff_contract_text("docs/doc-invariants.yaml", old, new)
    assert any(h.kind == "removed_must_contain" and "beta" in h.detail for h in hits)


def test_strengthening_not_weakening() -> None:
    old = """
content_rules:
  - id: rule-a
    files: [README.md]
    must_contain: [alpha]
"""
    new = """
content_rules:
  - id: rule-a
    files: [README.md]
    must_contain: [alpha, beta]
"""
    hits = diff_contract_text("docs/doc-invariants.yaml", old, new)
    assert hits == []


def test_approval_covers_weakening(tmp_path: Path) -> None:
    rel = "docs/doc-invariants.yaml"
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text("content_rules: []\n", encoding="utf-8")
    diff_weakening = [
        Weakening(rel, "removed_content_rule", "rule-a"),
    ]
    from contract_governance import ContractDiff

    diff = ContractDiff(base_ref="HEAD", head_ref="HEAD", changed_files=[rel], weakenings=diff_weakening)
    assert not approval_covers(tmp_path, diff)[0]

    write_approval(
        tmp_path,
        reason="Test approval for removed rule",
        approver="test.user",
        diff=diff,
    )
    assert approval_covers(tmp_path, diff)[0]


def test_verify_governance_on_repo() -> None:
    root = Path(__file__).resolve().parents[2]
    r = subprocess.run(
        [sys.executable, str(root / "runner" / "ci" / "verify-contract-governance.py"), "--check"],
        cwd=root,
        check=False,
    )
    assert r.returncode == 0
