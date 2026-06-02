"""Bob tool bridge — local-first CLI tools with optional MCP backend."""
from tool_bridge.registry import get_tool_spec, list_tool_specs, mcp_servers_config
from tool_bridge.router import backend_label, resolve_backend, run_tool
from tool_bridge.types import ToolBackend, ToolResult

__all__ = [
    "ToolBackend",
    "ToolResult",
    "backend_label",
    "get_tool_spec",
    "list_tool_specs",
    "mcp_servers_config",
    "resolve_backend",
    "run_tool",
]
