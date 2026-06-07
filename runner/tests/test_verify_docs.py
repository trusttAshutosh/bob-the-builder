"""Tests for doc invariants verifier."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

_spec = importlib.util.spec_from_file_location(
    "verify_docs",
    Path(__file__).resolve().parents[1] / "ci" / "verify-docs.py",
)
verify_docs = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["verify_docs"] = verify_docs
_spec.loader.exec_module(verify_docs)


def test_verify_all_passes_on_product_tree() -> None:
    findings, _ = verify_docs.verify_all()
    assert findings == [], [f"{f.rule_id}: {f.detail}" for f in findings]


def test_content_rule_failure(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    readme = root / "README.md"
    readme.write_text("# Bob\n", encoding="utf-8")
    inv = {
        "content_rules": [
            {
                "id": "need-clone",
                "files": ["README.md"],
                "must_contain": ["git clone https://github.com/"],
            }
        ]
    }
    monkeypatch.setattr(verify_docs, "ROOT", root)
    monkeypatch.setattr(verify_docs, "INVARIANTS_YAML", root / "docs" / "doc-invariants.yaml")
    findings, _ = verify_docs.verify_all(inv)
    assert any(f.rule_id == "need-clone" for f in findings)


def test_conditional_rule_failure(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "repo"
    docs = root / "docs"
    docs.mkdir(parents=True)
    doc = docs / "sample.md"
    doc.write_text("Use bob next for tickets\n", encoding="utf-8")
    inv = {
        "conditional_rules": [
            {
                "id": "bob-next-product",
                "files": ["docs/sample.md"],
                "when_contains": "bob next",
                "must_also_contain": ["Bob product"],
            }
        ]
    }
    monkeypatch.setattr(verify_docs, "ROOT", root)
    findings, _ = verify_docs.verify_all(inv)
    assert any(f.rule_id == "bob-next-product" for f in findings)
