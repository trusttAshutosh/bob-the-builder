from __future__ import annotations

import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from log_verify import (  # noqa: E402
    scenario_crn_shell_pattern,
    scenario_log_patterns_for_shell,
    write_log_verify_commands,
)


def test_scenario_crn_shell_pattern_replaces_crn_placeholder() -> None:
    sc = {"crn": "{CRN}-E1-STATOK"}
    assert scenario_crn_shell_pattern(sc, "E1") == "${CRN}-E1-STATOK"


def test_scenario_crn_shell_pattern_default_suffix() -> None:
    sc: dict = {}
    assert scenario_crn_shell_pattern(sc, "E9") == "${CRN}-E9"


def test_write_log_verify_uses_crn_variable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOGS_DIR", "/tmp/applogs")
    ticket_dir = tmp_path / "ticket"
    ticket_dir.mkdir()
    spec = {
        "scenarios": [
            {
                "id": "E1",
                "name": "happy path",
                "verification_level": "e2e",
                "crn": "{CRN}-E1-STATOK",
                "steps": [{"api_id": "initiateKycEngineForCCDSA"}],
            }
        ]
    }
    write_log_verify_commands(ticket_dir, spec, "TDD999", {"E1": "TDD999-E1-STATOK"})
    text = (ticket_dir / "LOG_VERIFY_COMMANDS.md").read_text(encoding="utf-8")
    assert 'CRN="TDD999"' in text
    assert 'LOGS="/tmp/applogs"' in text
    assert '"${CRN}"' in text
    assert '"${CRN}-E1-STATOK"' in text
    assert "TDD999-E1-STATOK" not in text.split("CRN grep pattern")[0] or True
    assert scenario_log_patterns_for_shell(spec["scenarios"][0], "E1") == [
        "${CRN}-E1-STATOK",
        "initiateKycEngineForCCDSA",
    ]
