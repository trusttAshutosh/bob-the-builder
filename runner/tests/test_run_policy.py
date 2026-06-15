"""Validate-ticket run policy defaults (E2E-first, unit tests opt-in)."""
from __future__ import annotations

import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from ticket_spec import unit_tests_enabled  # noqa: E402


def test_unit_tests_disabled_by_default() -> None:
    assert unit_tests_enabled({}) is False
    assert unit_tests_enabled({"run": {}}) is False
    assert unit_tests_enabled({"run": {"unit_tests": False}}) is False


def test_unit_tests_opt_in_only() -> None:
    assert unit_tests_enabled({"run": {"unit_tests": True}}) is True
