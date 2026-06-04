from __future__ import annotations

import json
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
    if prefix := db_expect.get("txn_result_description_prefix"):
        desc = row.get("txn_result_description", "")
        if not str(desc).startswith(str(prefix)):
            errors.append(f"txn_result_description prefix: want {prefix}* got {desc}")
    mnc = db_expect.get("must_not_contain") or {}
    for col, forbidden in mnc.items():
        val = row.get(col, "")
        for f in forbidden:
            if f in val:
                errors.append(f"{col} must not contain '{f}'")
    return len(errors) == 0, errors


def _unwrap_api_payload(response: dict, api_id: str) -> dict:
    if api_id in response and isinstance(response[api_id], dict):
        return response[api_id]
    return response


def _response_status(response: dict) -> dict:
    rs = response.get("response_status") or {}
    if isinstance(rs, dict) and isinstance(rs.get("response_status"), dict):
        return rs["response_status"]
    return rs if isinstance(rs, dict) else {}


def check_api_response(api_expect: dict, response: dict, api_id: str) -> tuple[bool, list[str]]:
    """Assert gateway JSON for the last API step (getLOCOffers, etc.)."""
    errors: list[str] = []
    if not api_expect:
        return True, errors
    body = _unwrap_api_payload(response, api_id)
    rs = _response_status(body if body is not response else response)
    code = str(rs.get("code", ""))
    status = str(rs.get("status", ""))

    want_code = api_expect.get("expect_response_code")
    if want_code is not None and code != str(want_code):
        errors.append(f"response_status.code: want={want_code} got={code or '(empty)'}")

    want_status = api_expect.get("expect_response_status")
    if want_status is not None and status != str(want_status):
        errors.append(f"response_status.status: want={want_status} got={status or '(empty)'}")

    for forbidden in api_expect.get("must_not_response_codes") or []:
        if code == str(forbidden):
            errors.append(f"response_status.code must not be {forbidden}")

    products = body.get("products") if isinstance(body, dict) else None
    if products is None and isinstance(response, dict):
        products = response.get("products")
    if not isinstance(products, list):
        products = []

    want_codes = api_expect.get("expect_product_codes")
    if want_codes is not None:
        actual = [
            str(p.get("product_code") or p.get("product_type") or "")
            for p in products
            if isinstance(p, dict)
        ]
        want = [str(c) for c in want_codes]
        if sorted(actual) != sorted(want):
            errors.append(f"products codes: want={want} got={actual}")

    want_count = api_expect.get("expect_product_count")
    if want_count is not None and len(products) != int(want_count):
        errors.append(f"products count: want={want_count} got={len(products)}")

    return len(errors) == 0, errors


def load_last_api_response(ticket_dir: Path, scenario_id: str, api_id: str) -> dict | None:
    for rel in (
        f"evidence/api/{scenario_id}-{api_id}-last.json",
        f"responses/{scenario_id}-{api_id}-last.json",
    ):
        path = ticket_dir / rel
        if not path.is_file():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None
