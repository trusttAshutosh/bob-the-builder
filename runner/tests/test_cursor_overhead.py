"""Tests for Bob cursor MCP/plugin overhead policy."""
from __future__ import annotations

from cursor_overhead import (
    build_mcp_audit_suggestions,
    classify_mcp_server,
    recommended_tools_to_disable,
)


def test_classify_mcp_server_keep_app_control() -> None:
    verdict, _ = classify_mcp_server("cursor-app-control")
    assert verdict == "keep"


def test_classify_mcp_server_disable_browser() -> None:
    verdict, reason = classify_mcp_server("cursor-ide-browser")
    assert verdict == "disable"
    assert "backend" in reason.lower()


def test_classify_mcp_server_review_unknown() -> None:
    verdict, _ = classify_mcp_server("custom-team-mcp")
    assert verdict == "review"


def test_recommended_tools_to_disable_skips_keep_and_review() -> None:
    servers = {
        "cursor-app-control": ["move_agent_to_root"],
        "cursor-ide-browser": ["browser_click"],
        "custom-team-mcp": ["do_thing"],
    }
    disabled = recommended_tools_to_disable(servers)
    assert disabled == ["cursor-ide-browser|browser_click"]


def test_build_mcp_audit_suggestions_ok_when_clean() -> None:
    from cursor_overhead import McpAuditReport

    report = McpAuditReport(
        generated_at="2026-01-01T00:00:00+00:00",
        pending_disable_tools=[],
        user_mcp_json_servers=[],
        allowed_tools_in_state=[],
        plugins=[],
    )
    suggestions = build_mcp_audit_suggestions(report)
    assert suggestions[0].startswith("MCP/plugin overhead matches")
