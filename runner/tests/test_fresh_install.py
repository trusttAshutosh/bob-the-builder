"""Tests for fresh install + non-CC discover-apis verification."""
from __future__ import annotations

from pathlib import Path

import pytest

from fresh_install_verify import (
    FIXTURE_HOST,
    assert_discovered_catalog,
    assert_empty_api_catalog,
    run_fresh_install_verify,
)


def test_fixture_host_has_orchestration_and_payments_profile() -> None:
    orch = FIXTURE_HOST / "deploy/application/orchestration/smoke-flow.xml"
    prof = FIXTURE_HOST / "deploy/tdd/env-local-dsa.yaml"
    assert orch.is_file()
    text = prof.read_text(encoding="utf-8")
    assert "payments_management" in text
    assert "PAYMENTS_BASE" in text
    assert "credit_card_management" not in text


def test_assert_empty_api_catalog_rejects_populated(tmp_path: Path) -> None:
    apis = tmp_path / "api-catalog" / "apis"
    apis.mkdir(parents=True)
    (apis / "getFoo.yaml").write_text("api_id: getFoo\n", encoding="utf-8")
    (tmp_path / "api-catalog" / "index.yaml").write_text("apis: {}\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="empty"):
        assert_empty_api_catalog(tmp_path)


def test_assert_discovered_catalog_checks_non_cc_fields(tmp_path: Path) -> None:
    apis = tmp_path / "api-catalog" / "apis"
    apis.mkdir(parents=True)
    skeleton = """\
api_id: smokeGetHealth
service: payments-fixture
http:
  base_env: PAYMENTS_BASE
"""
    (apis / "smokeGetHealth.yaml").write_text(skeleton, encoding="utf-8")
    (apis / "smokeSubmitOrder.yaml").write_text(
        skeleton.replace("smokeGetHealth", "smokeSubmitOrder"),
        encoding="utf-8",
    )
    (tmp_path / "api-catalog" / "index.yaml").write_text(
        "apis:\n  smokeGetHealth: apis/smokeGetHealth.yaml\n  smokeSubmitOrder: apis/smokeSubmitOrder.yaml\n",
        encoding="utf-8",
    )
    count = assert_discovered_catalog(tmp_path, host_name="novopay-platform-payments-fixture")
    assert count == 2


def test_run_fresh_install_verify_end_to_end() -> None:
    result = run_fresh_install_verify(verbose=False)
    assert result.ok, result.message
    assert result.apis_created == 2
