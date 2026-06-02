# Bob knowledge graph - visual view (Obsidian)

Bob builds a **structured graph** in YAML (`platform-graph.yaml`, `session-graph.yaml`). This guide shows how to see it **live** like Obsidian's graph view (not static flowcharts only).

## Quick start (recommended)

```bash
bob sync-graph              # scan host repo + export Obsidian vault
# or
bob graph sync-obsidian
bob graph open              # print vault path + instructions
```

1. Install [Obsidian](https://obsidian.md) (free for personal use).
2. **Open folder as vault** → choose the path printed by `bob graph open`.
   - Default: `bob-the-builder/local/obsidian-vault/`
   - Override: set `BOB_OBSIDIAN_VAULT=C:\path\to\vault` in `local/user.env`
3. Open note **Bob Home**.
4. Click **Graph** in the left ribbon (global graph) or **Local graph** while viewing a note.

Re-run `bob graph sync-obsidian` after `sync-graph` or `validate-ticket` (validate exports tickets by default).

## What is in the vault

| Folder / file | Content |
|---------------|---------|
| `Bob Home.md` | Index + counts |
| `api/*.md` | Gateway API → wikilinks to processors |
| `processor/*.md` | Processor bean → Java class, pattern |
| `stub/*.md` | Bank WireMock operations |
| `ticket/*.md` | Your session tickets, scenarios, linked APIs |
| `graph-overview.mmd` | Mermaid subset (first ~40 APIs) |
| `bob-export-manifest.json` | Last export metadata |

Edges in Obsidian = `[[wikilinks]]` between notes (API → processor → ticket).

## Without Obsidian (upload / paste options)

You can visualize **today's** graph without waiting for export:

| Tool | What to use | How |
|------|-------------|-----|
| **Obsidian** | Exported vault | `bob graph sync-obsidian` then open vault folder |
| **Mermaid Live** | `graph-overview.mmd` in vault | Copy file → https://mermaid.live |
| **GitHub / Cursor** | Same `.mmd` | Markdown preview with mermaid |
| **Gephi** | CSV (manual) | Not auto-exported yet; use Obsidian or request `bob graph export-csv` |
| **Neo4j Bloom / Aura** | CSV import | Same as above |
| **yEd** | Manual | Import if you build edge list from YAML |

Raw YAML is **not** directly uploadable to most graph UIs. Run **`bob graph sync-obsidian`** first to get linked notes Obsidian understands.

### Raw files (human-readable, not graphical)

| File | Path |
|------|------|
| Platform graph | `bob-the-builder/assets/platform-graph/platform-graph.yaml` |
| Session graph | `bob-the-builder/local/agent/session-graph.yaml` |
| Agent slice | `bob-the-builder/local/agent/kg-context-last.md` |

## validate-ticket

Each run refreshes the Obsidian vault (session tickets + platform) unless disabled:

```yaml
run:
  graph:
    sync_obsidian: false
```

## Not the same as MiroFish

[MiroFish](https://github.com/666ghj/MiroFish) builds LLM-extracted graphs from documents and runs agent **simulations**. Bob exports **code-derived** API/processor topology for **backend TDD**. Use Obsidian on Bob's vault, not MiroFish, for this workflow.

See [README.md](README.md) (doc index) · [BOB_CONTEXT_AND_EVAL.md](BOB_CONTEXT_AND_EVAL.md).
