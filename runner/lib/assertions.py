from __future__ import annotations

from pathlib import Path
from typing import Any

from _yaml_util import load, tdd_root
from bob_home import assertion_catalog_dir


def load_feature_catalog(feature: str) -> dict:
    if not feature:
        return {}
    for base in (assertion_catalog_dir(), tdd_root() / "_seed/assertion-catalog"):
        path = base / f"{feature}.yaml"
        if path.exists():
            return load(path)
    return {}


def resolve_db_expect(scenario: dict, spec: dict) -> dict:
    """Merge scenario db, assertion_preset, and feature rules."""
    db = dict(scenario.get("db") or {})
    preset_name = db.pop("assertion_preset", None) or scenario.get("assertion_preset")
    feature = (spec.get("impacted") or {}).get("feature") or ""
    catalog = load_feature_catalog(feature)
    presets = catalog.get("presets") or {}
    rules = catalog.get("rules") or {}

    if preset_name and preset_name in presets:
        p = presets[preset_name]
        db.setdefault("expect", {})
        db["expect"] = {**p.get("expect", {}), **db.get("expect", {})}
        if "internal_txn_desc_prefix" in p:
            db["internal_txn_desc_prefix"] = p["internal_txn_desc_prefix"]
        if "internal_txn_desc" in p:
            db["internal_txn_desc"] = p["internal_txn_desc"]
        for rule_key in p.get("inherit_rules") or []:
            r = rules.get(rule_key) or {}
            mnc = r.get("must_not_contain") or {}
            db.setdefault("must_not_contain", {})
            for col, vals in mnc.items():
                db["must_not_contain"].setdefault(col, [])
                db["must_not_contain"][col] = list(set(db["must_not_contain"][col] + vals))

    return db


def _like_match(pattern: str, value: str) -> bool:
    """SQL-style % wildcard (single-line)."""
    import re

    if not pattern or "%" not in pattern:
        return value == pattern
    regex = "^" + re.escape(pattern).replace("%", ".*") + "$"
    return bool(re.match(regex, value or ""))


def check_db_row(db_expect: dict, row: dict[str, str]) -> tuple[bool, list[str]]:
    """row: txn_status, txn_result_code, txn_result_description, internal_txn_desc"""
    errors: list[str] = []
    if pattern := db_expect.get("expect_internal_txn_desc_pattern"):
        internal = row.get("internal_txn_desc", "")
        if not internal:
            errors.append("internal_txn_desc: empty row (no transaction_audit for CRN)")
        elif not _like_match(str(pattern), internal):
            errors.append(f"internal_txn_desc: want pattern {pattern!r} got {internal!r}")
    expect = db_expect.get("expect") or {}
    for k, v in expect.items():
        if str(row.get(k, "")) != str(v):
            errors.append(f"{k}: want={v} got={row.get(k)}")
    if prefix := db_expect.get("internal_txn_desc_prefix"):
        internal = row.get("internal_txn_desc", "")
        if not str(internal).startswith(str(prefix)):
            errors.append(f"internal_txn_desc prefix: want {prefix}* got {internal}")
    mnc = db_expect.get("must_not_contain") or {}
    for col, forbidden in mnc.items():
        val = row.get(col, "")
        for f in forbidden:
            if f in val:
                errors.append(f"{col} must not contain '{f}'")
    return len(errors) == 0, errors
