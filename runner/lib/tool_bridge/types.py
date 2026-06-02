"""Types for Bob tool bridge (local + optional MCP)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolBackend(str, Enum):
    LOCAL = "local"
    MCP = "mcp"
    AUTO = "auto"


@dataclass
class ToolResult:
    ok: bool
    data: Any = None
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    backend: str = "local"
    tool_id: str = ""
    error: str = ""

    def text(self) -> str:
        if isinstance(self.data, str):
            return self.data
        if self.stdout:
            return self.stdout
        return ""


@dataclass
class ToolSpec:
    tool_id: str
    description: str
    local_handler: str
    mcp_server: str = ""
    mcp_tool: str = ""
    params: dict[str, Any] = field(default_factory=dict)
