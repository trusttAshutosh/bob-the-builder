#!/usr/bin/env python3
"""Cumulative transcript metrics across all chats (active + archived + ghost)."""
from __future__ import annotations

import json
import statistics
import sqlite3
import sys
from pathlib import Path

CONTEXT_LIMIT = 200_000
CHARS_PER_TOKEN = 4

_LIB = Path(__file__).resolve().parents[1] / "runner" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from chat_hygiene import global_state_db  # noqa: E402

OUT_JSON = Path(__file__).resolve().parents[1] / "docs" / "CONTEXT_ALL_CHATS_CUMULATIVE.json"
OUT_MD = Path(__file__).resolve().parents[1] / "docs" / "CONTEXT_ALL_CHATS_CUMULATIVE.md"


def extract_user_query(text: str) -> str:
    if "<user_query>" in text:
        start = text.find("<user_query>") + len("<user_query>")
        end = text.find("</user_query>")
        return text[start:end] if end > start else text
    return text


def analyze_transcript(path: Path) -> dict:
    user_q_chars = 0
    injected_chars = 0
    assistant_chars = 0
    tool_uses = 0
    user_turns = 0
    assistant_turns = 0
    max_user_q = 0
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        role = event.get("role")
        content = event.get("message", {}).get("content", [])
        if role == "user":
            user_turns += 1
            texts: list[str] = []
            if isinstance(content, str):
                texts = [content]
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        texts.append(part.get("text", ""))
            blob = "\n".join(texts)
            uq = extract_user_query(blob)
            user_q_chars += len(uq)
            injected_chars += max(0, len(blob) - len(uq))
            max_user_q = max(max_user_q, len(uq))
        elif role == "assistant" and isinstance(content, list):
            assistant_turns += 1
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text":
                    assistant_chars += len(part.get("text", ""))
                elif part.get("type") == "tool_use":
                    tool_uses += 1
    return {
        "user_turns": user_turns,
        "assistant_turns": assistant_turns,
        "user_query_chars": user_q_chars,
        "injected_chars": injected_chars,
        "assistant_chars": assistant_chars,
        "tool_uses": tool_uses,
        "max_user_query_chars": max_user_q,
        "user_query_tokens": user_q_chars // CHARS_PER_TOKEN,
        "injected_tokens": injected_chars // CHARS_PER_TOKEN,
        "assistant_tokens": assistant_chars // CHARS_PER_TOKEN,
        "transcript_visible_tokens": (user_q_chars + injected_chars + assistant_chars) // CHARS_PER_TOKEN,
    }


def discover_transcripts() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in Path.home().glob(".cursor/projects/*/agent-transcripts/*/*.jsonl"):
        if "subagents" in path.parts:
            continue
        chat_id = path.stem
        if chat_id not in found:
            found[chat_id] = path
    return found


def fleet_stats(rows: list[dict], label: str) -> dict:
    with_tx = [r for r in rows if r.get("has_transcript")]
    with_pct = [r for r in rows if r.get("est_window_tokens") is not None]
    stats: dict = {"label": label, "chats": len(rows), "with_transcript": len(with_tx), "with_context_pct": len(with_pct)}
    if with_tx:
        uq = [r["user_query_tokens"] for r in with_tx]
        stats.update(
            {
                "user_query_tokens_total": sum(uq),
                "user_query_tokens_avg_per_chat": int(sum(uq) / len(uq)),
                "user_query_tokens_median_per_chat": int(statistics.median(uq)),
                "injected_tokens_total": sum(r["injected_tokens"] for r in with_tx),
                "assistant_tokens_total": sum(r["assistant_tokens"] for r in with_tx),
                "transcript_visible_tokens_total": sum(r["transcript_visible_tokens"] for r in with_tx),
                "tool_uses_total": sum(r["tool_uses"] for r in with_tx),
                "user_turns_total": sum(r["user_turns"] for r in with_tx),
                "assistant_turns_total": sum(r["assistant_turns"] for r in with_tx),
            }
        )
        vis = stats["transcript_visible_tokens_total"]
        if vis:
            stats["user_query_pct_of_visible"] = round(stats["user_query_tokens_total"] / vis * 100, 2)
            stats["assistant_pct_of_visible"] = round(stats["assistant_tokens_total"] / vis * 100, 2)
            stats["injected_pct_of_visible"] = round(stats["injected_tokens_total"] / vis * 100, 2)
    if with_pct:
        windows = [r["est_window_tokens"] for r in with_pct]
        stats["est_window_tokens_sum"] = sum(windows)
        stats["est_window_tokens_avg"] = int(sum(windows) / len(windows))
    return stats


def main() -> int:
    db = global_state_db()
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT value FROM ItemTable WHERE key='composer.composerHeaders'"
        ).fetchone()
    headers = json.loads(row[0]).get("allComposers", []) if row else []
    header_by_id = {h.get("composerId"): h for h in headers if not h.get("isDraft")}
    transcripts = discover_transcripts()

    rows: list[dict] = []
    for chat_id, header in header_by_id.items():
        pct = header.get("contextUsagePercent")
        tp = transcripts.get(chat_id)
        rec = {
            "id": chat_id,
            "name": header.get("name") or header.get("subtitle") or "(untitled)",
            "archived": bool(header.get("isArchived")),
            "pct": pct,
            "est_window_tokens": int(CONTEXT_LIMIT * pct / 100) if pct is not None else None,
            "has_transcript": tp is not None,
        }
        if tp:
            rec.update(analyze_transcript(tp))
        rows.append(rec)

    ghost_rows: list[dict] = []
    for chat_id, tp in transcripts.items():
        if chat_id in header_by_id:
            continue
        ghost_rows.append(
            {
                "id": chat_id,
                "name": "(ghost - header missing)",
                "archived": None,
                **analyze_transcript(tp),
                "has_transcript": True,
            }
        )

    active = [r for r in rows if not r["archived"]]
    archived = [r for r in rows if r["archived"]]
    summaries = [
        fleet_stats(rows, "all_composers"),
        fleet_stats(active, "active"),
        fleet_stats(archived, "archived"),
    ]

    matched_tx = [r for r in rows if r.get("has_transcript")]
    corpus_uq = sum(r["user_query_tokens"] for r in matched_tx) + sum(g["user_query_tokens"] for g in ghost_rows)
    corpus_inj = sum(r["injected_tokens"] for r in matched_tx) + sum(g["injected_tokens"] for g in ghost_rows)
    corpus_ast = sum(r["assistant_tokens"] for r in matched_tx) + sum(g["assistant_tokens"] for g in ghost_rows)
    corpus_vis = sum(r["transcript_visible_tokens"] for r in matched_tx) + sum(
        g["transcript_visible_tokens"] for g in ghost_rows
    )
    corpus_tools = sum(r["tool_uses"] for r in matched_tx) + sum(g["tool_uses"] for g in ghost_rows)

    corpus = {
        "transcript_files": len(matched_tx) + len(ghost_rows),
        "header_matched_transcripts": len(matched_tx),
        "ghost_transcripts": len(ghost_rows),
        "user_query_tokens": corpus_uq,
        "injected_tokens": corpus_inj,
        "assistant_tokens": corpus_ast,
        "transcript_visible_tokens": corpus_vis,
        "tool_uses": corpus_tools,
        "user_query_pct_of_visible": round(corpus_uq / corpus_vis * 100, 2) if corpus_vis else 0,
        "assistant_pct_of_visible": round(corpus_ast / corpus_vis * 100, 2) if corpus_vis else 0,
        "injected_pct_of_visible": round(corpus_inj / corpus_vis * 100, 2) if corpus_vis else 0,
    }

    top_user = sorted(matched_tx, key=lambda r: -r.get("user_query_tokens", 0))[:25]
    huge_paste = [r for r in matched_tx if r.get("max_user_query_chars", 0) > 50_000]
    user_dominant = [
        r
        for r in matched_tx
        if r.get("transcript_visible_tokens", 0) > 0
        and r["user_query_tokens"] / r["transcript_visible_tokens"] > 0.5
    ]

    payload = {
        "summaries": summaries,
        "corpus": corpus,
        "top25_user_query_chats": top_user,
        "huge_paste_chat_count": len(huge_paste),
        "user_dominant_visible_count": len(user_dominant),
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Cumulative context across all chats (active + archived)",
        "",
        "Transcript jsonl files are **cumulative history** (all turns ever written to disk).",
        "This is different from `contextUsagePercent`, which is only the **last snapshot** of the live window per chat.",
        "",
        "## Full corpus (all transcript files on disk)",
        "",
        f"| Metric | Tokens |",
        f"|--------|-------:|",
        f"| Transcript files | {corpus['transcript_files']} ({corpus['header_matched_transcripts']} matched headers + {corpus['ghost_transcripts']} ghost) |",
        f"| Your `<user_query>` words (all turns, all chats) | **{corpus_uq:,}** |",
        f"| Injected user envelope (images/metadata) | {corpus_inj:,} |",
        f"| Assistant visible text | {corpus_ast:,} |",
        f"| Visible transcript total | {corpus_vis:,} |",
        f"| Tool calls | {corpus_tools:,} |",
        "",
        f"- Your words: **{corpus['user_query_pct_of_visible']}%** of visible transcript text",
        f"- Assistant visible text: **{corpus['assistant_pct_of_visible']}%**",
        f"- Injected metadata: **{corpus['injected_pct_of_visible']}%**",
        "",
        "## By composer header status",
        "",
        "| Group | Chats | With transcript | Your words total | Avg your words/chat | Median your words/chat | Assistant total | Tool calls | Your % of visible |",
        "|-------|------:|------------------:|-----------------:|--------------------:|-----------------------:|----------------:|-----------:|------------------:|",
    ]
    for s in summaries:
        lines.append(
            f"| {s['label']} | {s['chats']} | {s.get('with_transcript', 0)} | "
            f"{s.get('user_query_tokens_total', 'n/a'):,} | {s.get('user_query_tokens_avg_per_chat', 'n/a'):,} | "
            f"{s.get('user_query_tokens_median_per_chat', 'n/a'):,} | "
            f"{s.get('assistant_tokens_total', 'n/a'):,} | {s.get('tool_uses_total', 'n/a'):,} | "
            f"{s.get('user_query_pct_of_visible', 'n/a')} |"
        )

    with_pct = [r for r in rows if r.get("est_window_tokens") is not None]
    window_sum = sum(r["est_window_tokens"] for r in with_pct)
    lines.extend(
        [
            "",
            "## Stored window snapshots (not cumulative history)",
            "",
            f"- Chats with last-known context %: **{len(with_pct)}**",
            f"- Sum of last window sizes: **{window_sum:,}** tokens (adding these is not meaningful - each is a separate chat snapshot)",
            f"- Avg last window: **{window_sum // len(with_pct):,}** tokens",
            "",
            "## Hygiene signals (cumulative transcript)",
            "",
            f"- Chats with any single paste **>50K chars** in one `user_query`: **{len(huge_paste)}**",
            f"- Chats where your words are **>50%** of visible transcript: **{len(user_dominant)}**",
            "",
            "## Top 25 chats by cumulative your-words",
            "",
            "| Status | Your words | Assistant | Tools | Visible total | Name |",
            "|--------|----------:|----------:|------:|--------------:|------|",
        ]
    )
    for r in top_user:
        status = "archived" if r["archived"] else "active"
        lines.append(
            f"| {status} | {r['user_query_tokens']:,} | {r['assistant_tokens']:,} | {r['tool_uses']:,} | "
            f"{r['transcript_visible_tokens']:,} | {r['name'][:55]} |"
        )

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT_MD.read_text(encoding="utf-8"))
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
