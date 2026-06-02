# MCP-ready tool bridge

Bob can run **side-effect tools** (git, MySQL, subprocess) through a single registry. **Local execution is the default** — nothing changes until you opt in to MCP.

## Backends

| `BOB_TOOL_BACKEND` | Behavior |
|--------------------|----------|
| `local` (default) | Python handlers in `runner/lib/tool_bridge/local_handlers.py` |
| `mcp` | Call tools on the MCP server in `runner/config/mcp-servers.yaml` |
| `auto` | Try MCP when the tool has an MCP mapping; fall back to local on failure |

Set in `user.env` or the shell:

```bash
export BOB_TOOL_BACKEND=local   # default — no MCP required
export BOB_TOOL_BACKEND=auto    # gradual migration
export BOB_TOOL_BACKEND=mcp     # agents / remote only
```

## Registry

| File | Purpose |
|------|---------|
| `runner/config/tool-bridge.yaml` | Tool IDs, local handler names, MCP server/tool names |
| `runner/config/mcp-servers.yaml` | How to spawn MCP servers (stdio) |
| `runner/mcp/bob_tools_server.py` | Built-in MCP server exposing the same handlers as local |

## CLI

```bash
bob tools list
bob tools backend
bob tools run git.branch --cwd .
bob tools run mysql.query --sql "SELECT 1"
```

## Wiring in code

Prefer the bridge for new external I/O:

```python
from tool_bridge import run_tool

result = run_tool("git.branch", cwd=str(repo_path))
branch = str(result.data) if result.ok else "unknown"
```

Already routed: `git.branch` (context + run summary), `mysql.query` (`mysql_runner`).

## Moving a tool to MCP

1. Add or confirm `local_handler` and `mcp` block in `tool-bridge.yaml`.
2. Implement the handler in `local_handlers.py` (local path).
3. Ensure `bob_tools_server.py` exposes the same name (uses the same handlers).
4. Test local: `bob tools run <tool-id>`.
5. Test MCP: `BOB_TOOL_BACKEND=mcp bob tools run <tool-id>`.
6. Switch agents/Cursor MCP config to call the server when ready.

No change to `bob validate-ticket` or other commands until you replace direct `subprocess` calls with `run_tool`.

## Cursor / IDE MCP

Example `.cursor/mcp.json` (optional — for IDE agents, not required for Bob CLI):

```json
{
  "mcpServers": {
    "bob-tools": {
      "command": "python",
      "args": ["runner/mcp/bob_tools_server.py"],
      "cwd": "/path/to/bob-the-builder"
    }
  }
}
```

Bob CLI with `BOB_TOOL_BACKEND=mcp` spawns the same server from `mcp-servers.yaml`.

## Design rules

- **Local must always work** — CI and developers without MCP use `local`.
- **One tool ID** — same name in YAML, Python, and MCP `tools/call`.
- **Migrate incrementally** — wrap one tool at a time; use `auto` during transition.

## See also

- [EVIDENCE_AND_VERIFY.md](EVIDENCE_AND_VERIFY.md) — validate-ticket proof (DB, logs, Kafka, Redis)
- [README.md](README.md) — documentation index
