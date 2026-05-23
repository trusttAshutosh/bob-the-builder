# Platform knowledge graph

Stable map of gateway APIs, processors, features, and stub registry entries.

**Regenerate after orchestration or major processor changes:**

```bash
bob sync-graph
```

Session-specific data (branch, ticket, run results) lives in **`{BOB_LOCAL}/agent/session-graph.yaml`** (gitignored).

Agents: **`bob query-graph <keywords>`** writes context to `{BOB_LOCAL}/agent/kg-context-last.md`.
