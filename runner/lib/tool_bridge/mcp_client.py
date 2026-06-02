"""Minimal MCP stdio client (stdlib only) — optional backend for tool_bridge."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from tool_bridge.registry import get_mcp_server
from tool_bridge.types import ToolResult


class McpStdioClient:
    """JSON-RPC over stdio to an MCP server subprocess."""

    def __init__(self, server_name: str, *, product_root: Path | None = None) -> None:
        cfg = get_mcp_server(server_name)
        if not cfg:
            raise ValueError(f"Unknown MCP server: {server_name}")
        if cfg.get("enabled") is False:
            raise ValueError(f"MCP server disabled: {server_name}")

        from bob_home import bob_product_root

        root = (product_root or bob_product_root()).resolve()
        command = str(cfg.get("command", "python"))
        args = [str(a) for a in (cfg.get("args") or [])]
        resolved_args: list[str] = []
        for a in args:
            p = Path(a)
            if not p.is_absolute():
                p = root / a
            resolved_args.append(str(p))

        self.server_name = server_name
        self._proc = subprocess.Popen(
            [command, *resolved_args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(root),
            env=os.environ.copy(),
        )
        self._lock = threading.Lock()
        self._next_id = 1
        self._initialize()

    def _read_line(self) -> dict[str, Any] | None:
        if not self._proc.stdout:
            return None
        line = self._proc.stdout.readline()
        if not line.strip():
            return None
        return json.loads(line)

    def _write(self, payload: dict[str, Any]) -> None:
        if not self._proc.stdin:
            raise RuntimeError("MCP server stdin closed")
        self._proc.stdin.write(json.dumps(payload) + "\n")
        self._proc.stdin.flush()

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            req_id = self._next_id
            self._next_id += 1
            self._write(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "method": method,
                    "params": params or {},
                }
            )
            while True:
                msg = self._read_line()
                if msg is None:
                    raise RuntimeError("MCP server closed stdout")
                if msg.get("id") == req_id:
                    if "error" in msg:
                        err = msg["error"]
                        raise RuntimeError(err.get("message", str(err)))
                    return msg.get("result") or {}

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._write({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def _initialize(self) -> None:
        self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "bob-tool-bridge", "version": "1.0"},
            },
        )
        self._notify("notifications/initialized", {})

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        result = self._request("tools/call", {"name": tool_name, "arguments": arguments})
        content = result.get("content") or []
        text_parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(str(block.get("text", "")))
        text = "\n".join(text_parts).strip()
        is_error = bool(result.get("isError"))
        return ToolResult(
            ok=not is_error,
            data=text,
            stdout=text,
            backend=f"mcp:{self.server_name}",
            tool_id=tool_name,
            error=text if is_error else "",
        )

    def close(self) -> None:
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
            self._proc.terminate()
            self._proc.wait(timeout=5)
        except Exception:
            self._proc.kill()


_clients: dict[str, McpStdioClient] = {}


def get_mcp_client(server_name: str, *, product_root: Path | None = None) -> McpStdioClient:
    key = server_name
    if key not in _clients:
        _clients[key] = McpStdioClient(server_name, product_root=product_root)
    return _clients[key]


def mcp_call_tool(
    server_name: str,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    product_root: Path | None = None,
) -> ToolResult:
    try:
        client = get_mcp_client(server_name, product_root=product_root)
        return client.call_tool(tool_name, arguments)
    except Exception as exc:
        return ToolResult(
            ok=False,
            error=str(exc),
            backend=f"mcp:{server_name}",
            tool_id=tool_name,
        )
