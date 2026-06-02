"""Load tool-bridge.yaml and mcp-servers.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from tool_bridge.types import ToolSpec

_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
_BRIDGE_PATH = _CONFIG_DIR / "tool-bridge.yaml"
_MCP_PATH = _CONFIG_DIR / "mcp-servers.yaml"

_bridge_cache: dict[str, Any] | None = None
_mcp_cache: dict[str, Any] | None = None


def _load_yaml(path: Path) -> dict[str, Any]:
    from _yaml_util import load

    if not path.is_file():
        return {}
    return load(path) or {}


def bridge_config() -> dict[str, Any]:
    global _bridge_cache
    if _bridge_cache is None:
        _bridge_cache = _load_yaml(_BRIDGE_PATH)
    return _bridge_cache


def mcp_servers_config() -> dict[str, Any]:
    global _mcp_cache
    if _mcp_cache is None:
        _mcp_cache = _load_yaml(_MCP_PATH)
    return _mcp_cache


def list_tool_specs() -> list[ToolSpec]:
    tools = bridge_config().get("tools") or {}
    out: list[ToolSpec] = []
    for tool_id, raw in tools.items():
        if not isinstance(raw, dict):
            continue
        mcp = raw.get("mcp") or {}
        out.append(
            ToolSpec(
                tool_id=tool_id,
                description=str(raw.get("description", "")),
                local_handler=str(raw.get("local_handler", "")),
                mcp_server=str(mcp.get("server", "")),
                mcp_tool=str(mcp.get("tool", "")),
                params=dict(raw.get("params") or {}),
            )
        )
    return sorted(out, key=lambda t: t.tool_id)


def get_tool_spec(tool_id: str) -> ToolSpec | None:
    raw = (bridge_config().get("tools") or {}).get(tool_id)
    if not isinstance(raw, dict):
        return None
    mcp = raw.get("mcp") or {}
    return ToolSpec(
        tool_id=tool_id,
        description=str(raw.get("description", "")),
        local_handler=str(raw.get("local_handler", "")),
        mcp_server=str(mcp.get("server", "")),
        mcp_tool=str(mcp.get("tool", "")),
        params=dict(raw.get("params") or {}),
    )


def get_mcp_server(name: str) -> dict[str, Any] | None:
    servers = mcp_servers_config().get("servers") or {}
    raw = servers.get(name)
    return raw if isinstance(raw, dict) else None
