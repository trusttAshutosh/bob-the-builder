"""Route tool calls to local or MCP backend."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from tool_bridge.local_handlers import run_local_handler
from tool_bridge.mcp_client import mcp_call_tool
from tool_bridge.registry import get_tool_spec
from tool_bridge.types import ToolBackend, ToolResult


def resolve_backend() -> ToolBackend:
    raw = (os.environ.get("BOB_TOOL_BACKEND") or "local").strip().lower()
    try:
        return ToolBackend(raw)
    except ValueError:
        return ToolBackend.LOCAL


def backend_label() -> str:
    return resolve_backend().value


def run_tool(
    tool_id: str,
    /,
    *,
    product_root: Path | None = None,
    **arguments: Any,
) -> ToolResult:
    """
    Execute a registered tool. Default: local Python handlers (no MCP required).

    BOB_TOOL_BACKEND=local  — always local (default)
    BOB_TOOL_BACKEND=mcp    — MCP only; fails if server unavailable
    BOB_TOOL_BACKEND=auto   — try MCP when tool has mcp mapping, else local
    """
    spec = get_tool_spec(tool_id)
    if spec is None:
        return ToolResult(ok=False, error=f"Unknown tool: {tool_id}", tool_id=tool_id)

    backend = resolve_backend()
    if backend == ToolBackend.MCP:
        return _run_mcp(spec, arguments, product_root=product_root)
    if backend == ToolBackend.AUTO:
        if spec.mcp_server and spec.mcp_tool:
            mcp_result = _run_mcp(spec, arguments, product_root=product_root)
            if mcp_result.ok:
                return mcp_result
        return _run_local(spec, arguments)

    return _run_local(spec, arguments)


def _run_local(spec: Any, arguments: dict[str, Any]) -> ToolResult:
    if not spec.local_handler:
        return ToolResult(ok=False, error="No local_handler configured", tool_id=spec.tool_id)
    result = run_local_handler(spec.local_handler, arguments)
    result.tool_id = spec.tool_id
    return result


def _run_mcp(spec: Any, arguments: dict[str, Any], *, product_root: Path | None) -> ToolResult:
    if not spec.mcp_server or not spec.mcp_tool:
        return ToolResult(
            ok=False,
            error=f"Tool {spec.tool_id} has no MCP mapping",
            tool_id=spec.tool_id,
            backend="mcp",
        )
    result = mcp_call_tool(
        spec.mcp_server,
        spec.mcp_tool,
        arguments,
        product_root=product_root,
    )
    result.tool_id = spec.tool_id
    return result
