"""Tests for DB verify SQL generation."""
from __future__ import annotations

import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from audit_config import (  # noqa: E402
    audit_time_column,
    build_scenario_audit_select,
    db_verify_sql_header,
)


def _minimal_spec() -> dict:
    return {
        "_env": {
            "audit": {
                "schema": "dsa_credit_card_mgmt",
                "table": "transaction_audit",
                "crn_column": "client_reference_code",
                "order_by": "updated_on DESC",
                "columns": [
                    "txn_status",
                    "txn_result_code",
                    "txn_result_description",
                    "internal_txn_desc",
                ],
            }
        }
    }


def test_audit_time_column_from_order_by() -> None:
    assert audit_time_column({"order_by": "updated_on DESC"}) == "updated_on"
    assert audit_time_column({"order_by": "created_on ASC"}) == "created_on"
    assert audit_time_column({}) == "updated_on"


def test_db_verify_header_lists_test_run_time() -> None:
    header = "\n".join(db_verify_sql_header("CRN1", "dsa_credit_card_mgmt"))
    assert "test_run_time" in header


def test_scenario_select_includes_test_run_time() -> None:
    sql = build_scenario_audit_select(
        "S1",
        "Happy path",
        "CRN1-S1",
        _minimal_spec(),
        {"expect": {"txn_status": "SUCCESS"}},
    )
    assert "updated_on AS test_run_time" in sql
    assert "client_reference_code, updated_on AS test_run_time, txn_status" in sql
