#!/usr/bin/env python3
"""Bob MCP stdio server — exposes tool-bridge handlers for agents / BOB_TOOL_BACKEND=mcp."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_LIB = _ROOT / "runner" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from tool_bridge.local_handlers import HANDLERS  # noqa: E402
from tool_bridge.registry import list_tool_specs  # noqa: E402


def _tool_list() -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for spec in list_tool_specs():
        if not spec.local_handler:
            continue
        props: dict[str, Any] = {}
        required: list[str] = []
        for name, meta in (spec.params or {}).items():
            if not isinstance(meta, dict):
                continue
            props[name] = {"type": meta.get("type", "string")}
            if meta.get("required"):
                required.append(name)
        tools.append(
            {
                "name": spec.mcp_tool or spec.local_handler,
                "description": spec.description or spec.tool_id,
                "inputSchema": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            }
        )
    return tools


def _handle_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    handler = HANDLERS.get(name)
    if handler is None:
        for spec in list_tool_specs():
            if spec.mcp_tool == name or spec.local_handler == name:
                handler = HANDLERS.get(spec.local_handler)
                break
    if handler is None:
        return {
            "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
            "isError": True,
        }
    result = handler(**arguments)
    text = result.text() if hasattr(result, "text") else str(result.data or "")
    if not result.ok:
        return {"content": [{"type": "text", "text": result.error or text}], "isError": True}
    return {"content": [{"type": "text", "text": text}]}


def _respond(req_id: int | None, result: dict[str, Any] | None = None, error: str | None = None) -> None:
    msg: dict[str, Any] = {"jsonrpc": "2.0"}
    if req_id is not None:
        msg["id"] = req_id
    if error:
        msg["error"] = {"code": -32603, "message": error}
    else:
        msg["result"] = result or {}
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        req_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params") or {}

        if method == "initialize":
            _respond(
                req_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "bob-tools", "version": "1.0"},
                },
            )
            continue

        if method == "notifications/initialized":
            continue

        if method == "tools/list":
            _respond(req_id, {"tools": _tool_list()})
            continue

        if method == "tools/call":
            name = str(params.get("name", ""))
            arguments = dict(params.get("arguments") or {})
            _respond(req_id, _handle_call(name, arguments))
            continue

        if req_id is not None:
            _respond(req_id, error=f"Method not found: {method}")


if __name__ == "__main__":
    main()
