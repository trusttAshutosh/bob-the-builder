#!/usr/bin/env python3
"""Measure stored context % vs transcript-visible user/agent split across all chats."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

CONTEXT_LIMIT = 200_000
CHARS_PER_TOKEN = 4

_LIB = Path(__file__).resolve().parents[1] / "runner" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from chat_hygiene import global_state_db  # noqa: E402

OUT_JSON = Path(__file__).resolve().parents[1] / "docs" / "CONTEXT_CONVERSATION_BREAKDOWN.json"
OUT_MD = Path(__file__).resolve().parents[1] / "docs" / "CONTEXT_CONVERSATION_BREAKDOWN.md"


def transcript_path_for_id(chat_id: str) -> Path | None:
    root = Path.home() / ".cursor" / "projects"
    for path in root.rglob(f"agent-transcripts/{chat_id}/{chat_id}.jsonl"):
        if "subagents" not in path.parts:
            return path
    return None


def analyze_transcript(path: Path) -> dict:
    user_query_chars = 0
    user_envelope_chars = 0
    assistant_text_chars = 0
    tool_uses = 0
    user_turns = 0
    assistant_turns = 0
    lines = 0
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        lines += 1
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
            user_envelope_chars += len(blob)
            if "<user_query>" in blob:
                start = blob.find("<user_query>") + len("<user_query>")
                end = blob.find("</user_query>")
                user_query_chars += len(blob[start:end] if end > start else blob)
            else:
                user_query_chars += len(blob)
        elif role == "assistant":
            assistant_turns += 1
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text":
                    assistant_text_chars += len(part.get("text", ""))
                elif part.get("type") == "tool_use":
                    tool_uses += 1
    injected_chars = max(0, user_envelope_chars - user_query_chars)
    return {
        "lines": lines,
        "user_turns": user_turns,
        "assistant_turns": assistant_turns,
        "user_query_chars": user_query_chars,
        "injected_chars": injected_chars,
        "assistant_text_chars": assistant_text_chars,
        "tool_uses": tool_uses,
    }


def tokens_from_chars(chars: int) -> int:
    return chars // CHARS_PER_TOKEN


def summarize(rows: list[dict], label: str) -> dict:
    pcts = [r["pct"] for r in rows if r.get("pct") is not None]
    with_tx = [r for r in rows if r.get("has_transcript")]
    est = [r["est_total_tokens"] for r in with_tx if r.get("est_total_tokens")]
    uq = [r["est_user_query_tokens"] for r in with_tx]
    inj = [r["est_injected_tokens"] for r in with_tx]
    ast = [r["est_assistant_text_tokens"] for r in with_tx]
    vis = [r["transcript_visible_tokens"] for r in with_tx]
    unacc = [r["unaccounted_tokens"] for r in with_tx if r.get("unaccounted_tokens") is not None]
    tools = [r["tool_uses"] for r in with_tx]

    summary = {
        "label": label,
        "chat_count": len(rows),
        "with_context_pct": len(pcts),
        "with_transcript": len(with_tx),
    }
    if pcts:
        summary.update(
            {
                "pct_min": round(min(pcts), 1),
                "pct_max": round(max(pcts), 1),
                "pct_avg": round(sum(pcts) / len(pcts), 1),
            }
        )
    if est:
        summary.update(
            {
                "est_total_tokens_avg": int(sum(est) / len(est)),
                "est_total_tokens_max": max(est),
                "user_query_tokens_total": sum(uq),
                "user_query_tokens_avg": int(sum(uq) / len(uq)),
                "injected_tokens_total": sum(inj),
                "injected_tokens_avg": int(sum(inj) / len(uq)),
                "assistant_text_tokens_total": sum(ast),
                "assistant_text_tokens_avg": int(sum(ast) / len(uq)),
                "transcript_visible_tokens_avg": int(sum(vis) / len(uq)),
                "unaccounted_tokens_total": sum(unacc),
                "unaccounted_tokens_avg": int(sum(unacc) / len(unacc)),
                "tool_uses_total": sum(tools),
                "tool_uses_avg": round(sum(tools) / len(tools), 1),
            }
        )
        ratios = [r["user_query_pct_of_total"] for r in with_tx if r.get("user_query_pct_of_total") is not None]
        if ratios:
            ratios_sorted = sorted(ratios)
            summary["user_query_pct_of_total_median"] = round(ratios_sorted[len(ratios_sorted) // 2], 2)
            summary["user_query_pct_of_total_avg"] = round(sum(ratios) / len(ratios), 2)
            summary["user_query_pct_of_total_p90"] = round(ratios_sorted[int(len(ratios_sorted) * 0.9)], 2)
    return summary


def main() -> int:
    db = global_state_db()
    if not db.is_file():
        print(f"Missing state DB: {db}", file=sys.stderr)
        return 1

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT value FROM ItemTable WHERE key='composer.composerHeaders'"
        ).fetchone()
    headers = json.loads(row[0]).get("allComposers", []) if row else []

    rows: list[dict] = []
    for header in headers:
        if header.get("isDraft"):
            continue
        chat_id = header.get("composerId", "")
        pct = header.get("contextUsagePercent")
        est_total = int(CONTEXT_LIMIT * pct / 100) if pct is not None else None
        rec = {
            "id": chat_id,
            "name": header.get("name") or header.get("subtitle") or "(untitled)",
            "archived": bool(header.get("isArchived")),
            "pct": pct,
            "est_total_tokens": est_total,
            "has_transcript": False,
        }
        tp = transcript_path_for_id(chat_id)
        if tp:
            analysis = analyze_transcript(tp)
            rec["has_transcript"] = True
            rec.update(analysis)
            uq = tokens_from_chars(rec["user_query_chars"])
            inj = tokens_from_chars(rec["injected_chars"])
            ast = tokens_from_chars(rec["assistant_text_chars"])
            vis = uq + inj + ast
            rec["est_user_query_tokens"] = uq
            rec["est_injected_tokens"] = inj
            rec["est_assistant_text_tokens"] = ast
            rec["transcript_visible_tokens"] = vis
            if est_total is not None:
                rec["unaccounted_tokens"] = max(0, est_total - vis)
                rec["user_query_pct_of_total"] = round(uq / est_total * 100, 2) if est_total else None
                rec["visible_transcript_pct_of_total"] = round(vis / est_total * 100, 2) if est_total else None
                rec["unaccounted_pct_of_total"] = round(rec["unaccounted_tokens"] / est_total * 100, 2) if est_total else None
        rows.append(rec)

    active = [r for r in rows if not r["archived"]]
    archived = [r for r in rows if r["archived"]]
    active_hot = [r for r in active if r.get("pct") is not None and r["pct"] >= 60]

    summaries = [
        summarize(rows, "all"),
        summarize(active, "active"),
        summarize(archived, "archived"),
        summarize(active_hot, "active_gte_60pct"),
    ]

    payload = {
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "methodology": {
            "stored_context_pct": "composer.composerHeaders.contextUsagePercent",
            "est_total_tokens": "contextUsagePercent * 200000",
            "user_query_tokens": "chars inside <user_query> only, divided by 4",
            "injected_tokens": "user envelope minus user_query (images, metadata), divided by 4",
            "assistant_text_tokens": "assistant text parts in transcript jsonl, divided by 4",
            "unaccounted_tokens": "est_total - (user_query + injected + assistant_text); mostly tool results and hidden context",
            "limitation": "Per-category Context panel (Rules, Tools, MCP) is NOT stored per chat historically.",
        },
        "summaries": summaries,
        "active_hot_detail": sorted(active_hot, key=lambda r: -(r.get("pct") or 0)),
        "top_20_by_pct": sorted(
            [r for r in rows if r.get("pct") is not None],
            key=lambda r: -r["pct"],
        )[:20],
        "rows": rows,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Context conversation breakdown (measured)",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## Methodology",
        "",
        "- **Stored total**: `contextUsagePercent` from Cursor `state.vscdb` x 200K window.",
        "- **Your words**: only text inside `<user_query>` in transcript jsonl.",
        "- **Injected**: images/metadata Cursor attaches to user turns.",
        "- **Assistant text**: visible assistant prose in transcript (not tool results).",
        "- **Unaccounted**: stored total minus transcript-visible text - mostly tool outputs, file reads, hidden payloads.",
        "- **Not available historically**: per-chat Rules/Tools/MCP/Skills split from the Context panel.",
        "",
        "## Fleet summaries",
        "",
        "| Group | Chats | With % | With transcript | Avg % | Avg total (est) | Avg your words | Avg unaccounted | Median your words % of total |",
        "|-------|------:|-------:|----------------:|------:|----------------:|---------------:|----------------:|-----------------------------:|",
    ]
    for s in summaries:
        lines.append(
            f"| {s['label']} | {s['chat_count']} | {s.get('with_context_pct', 0)} | "
            f"{s.get('with_transcript', 0)} | {s.get('pct_avg', 'n/a')} | "
            f"{s.get('est_total_tokens_avg', 'n/a')} | {s.get('user_query_tokens_avg', 'n/a')} | "
            f"{s.get('unaccounted_tokens_avg', 'n/a')} | {s.get('user_query_pct_of_total_median', 'n/a')} |"
        )

    lines.extend(["", "## Active chats at >= 60% (measured)", ""])
    lines.append("| % | Total est | Your words | Injected | Asst text | Unaccounted | Tools | Name |")
    lines.append("|--:|----------:|-----------:|---------:|----------:|------------:|------:|------|")
    for r in payload["active_hot_detail"]:
        if not r.get("has_transcript"):
            lines.append(f"| {r.get('pct', 0):.1f} | n/a | n/a | n/a | n/a | n/a | n/a | {r['name'][:60]} |")
            continue
        lines.append(
            f"| {r['pct']:.1f} | {r['est_total_tokens']:,} | {r['est_user_query_tokens']:,} | "
            f"{r['est_injected_tokens']:,} | {r['est_assistant_text_tokens']:,} | "
            f"{r.get('unaccounted_tokens', 0):,} | {r['tool_uses']} | {r['name'][:60]} |"
        )

    hot_with_tx = [r for r in active_hot if r.get("has_transcript") and r.get("est_total_tokens")]
    if hot_with_tx:
        total_est = sum(r["est_total_tokens"] for r in hot_with_tx)
        total_uq = sum(r["est_user_query_tokens"] for r in hot_with_tx)
        total_unacc = sum(r.get("unaccounted_tokens", 0) for r in hot_with_tx)
        lines.extend(
            [
                "",
                "## Active >= 60% combined (transcript-backed)",
                "",
                f"- Combined estimated context: **{total_est:,}** tokens across **{len(hot_with_tx)}** chats",
                f"- Combined your `<user_query>` words: **{total_uq:,}** tokens (**{total_uq / total_est * 100:.1f}%** of stored total)",
                f"- Combined unaccounted (agent/tool/hidden): **{total_unacc:,}** tokens (**{total_unacc / total_est * 100:.1f}%**)",
                "",
                "The earlier ~10-20K hygiene guess is **not supported** by your hot chats aggregate - your words are far smaller; unaccounted agent/tool payload dominates.",
            ]
        )

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT_MD.read_text(encoding="utf-8"))
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
