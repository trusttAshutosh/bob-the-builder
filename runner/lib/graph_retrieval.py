"""Hybrid retrieval over Bob platform graph, API catalog, and session (lexical + graph expand)."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _yaml_util import load
from bob_home import agent_dir, api_catalog_dir, platform_graph_path
from session_graph import session_path

_TOKEN = re.compile(r"[a-z0-9]+", re.I)
_SKIP_BEANS = frozenset(
    {
        "mandatoryfieldvalidator",
        "patternfieldvalidator",
        "numbervalidator",
        "masterdatanegativecheckvalidator",
        "dummyprocessor",
    }
)


@dataclass
class RetrievalHit:
    doc_id: str
    kind: str
    score: float
    title: str
    snippet: str
    expand_from: str | None = None


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text) if len(t) > 1]


def _lexical_score(query_terms: list[str], corpus: str) -> float:
    if not query_terms:
        return 0.0
    text = corpus.lower()
    hits = sum(1 for t in query_terms if t in text)
    if hits == 0:
        return 0.0
    # Length-normalized overlap (BM25-lite without corpus IDF)
    return hits / math.sqrt(max(len(_tokenize(corpus)), 1))


def _load_platform() -> dict:
    p = platform_graph_path()
    return load(p) if p.is_file() else {}


def _load_session() -> dict:
    sp = session_path()
    return load(sp) if sp.is_file() else {}


def _query_terms(keywords: str, spec: dict | None) -> list[str]:
    terms = _tokenize(keywords)
    if spec:
        imp = spec.get("impacted") or {}
        for api in imp.get("gateway_apis") or []:
            terms.extend(_tokenize(str(api)))
        for bean in imp.get("processor_beans") or []:
            terms.extend(_tokenize(str(bean)))
        feat = imp.get("feature") or ""
        terms.extend(_tokenize(str(feat)))
        ticket = (spec.get("ticket") or {}).get("id") or ""
        terms.extend(_tokenize(str(ticket)))
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _collect_hits(
    plat: dict,
    sess: dict,
    spec: dict | None,
    terms: list[str],
    *,
    top_k: int = 25,
) -> list[RetrievalHit]:
    hits: list[RetrievalHit] = []
    processors = plat.get("processors") or {}

    for api_id, info in (plat.get("gateway_apis") or {}).items():
        beans = info.get("processor_beans") or []
        text = f"{api_id} {info.get('path', '')} {' '.join(beans)} {info.get('catalog', '')}"
        sc = _lexical_score(terms, text)
        if sc > 0:
            hits.append(
                RetrievalHit(
                    doc_id=f"api:{api_id}",
                    kind="api",
                    score=sc * 2.0,
                    title=api_id,
                    snippet=f"path={info.get('path', '')} beans={len(beans)}",
                )
            )

    for bean, info in (plat.get("processors") or {}).items():
        if not bean.endswith("Processor"):
            continue
        text = f"{bean} {info.get('class', '')} {info.get('extends', '')} {info.get('file', '')}"
        sc = _lexical_score(terms, text)
        if sc > 0:
            hits.append(
                RetrievalHit(
                    doc_id=f"processor:{bean}",
                    kind="processor",
                    score=sc * 1.5,
                    title=bean,
                    snippet=str(info.get("class", "")),
                )
            )

    for op, fixtures in (plat.get("bank_operation_stubs") or {}).items():
        text = f"{op} {' '.join(fixtures or [])}"
        sc = _lexical_score(terms, text)
        if sc > 0:
            hits.append(
                RetrievalHit(
                    doc_id=f"stub:{op}",
                    kind="stub",
                    score=sc,
                    title=op,
                    snippet=f"{len(fixtures or [])} fixture(s)",
                )
            )

    cat_dir = api_catalog_dir() / "apis"
    if cat_dir.is_dir():
        for yf in cat_dir.glob("*.yaml"):
            try:
                data = load(yf)
            except Exception:
                continue
            api_id = str(data.get("api_id", yf.stem))
            text = f"{api_id} {data.get('path', '')} {data.get('description', '')} {data.get('bank_calls', '')}"
            sc = _lexical_score(terms, text)
            if sc > 0:
                hits.append(
                    RetrievalHit(
                        doc_id=f"catalog:{api_id}",
                        kind="catalog",
                        score=sc * 1.2,
                        title=api_id,
                        snippet=str(yf.name),
                    )
                )

    for task in (sess.get("tasks") or [])[:15]:
        tid = task.get("ticket_id", "")
        text = f"{tid} {task.get('title', '')} {task.get('branch', '')} {task.get('overall', '')}"
        sc = _lexical_score(terms, text)
        if sc > 0:
            hits.append(
                RetrievalHit(
                    doc_id=f"ticket:{tid}",
                    kind="ticket",
                    score=sc * 1.3,
                    title=tid or "?",
                    snippet=f"branch={task.get('branch', '')} overall={task.get('overall', '')}",
                )
            )

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top_k]


def _graph_expand(plat: dict, hits: list[RetrievalHit], terms: list[str]) -> list[RetrievalHit]:
    """Add processors linked to top API hits (hybrid graph hop)."""
    seen = {h.doc_id for h in hits}
    processors = plat.get("processors") or {}
    expanded: list[RetrievalHit] = list(hits)
    for h in hits:
        if h.kind != "api":
            continue
        api_id = h.title
        info = (plat.get("gateway_apis") or {}).get(api_id) or {}
        for bean in info.get("processor_beans") or []:
            if bean.lower() in _SKIP_BEANS or bean not in processors:
                continue
            did = f"processor:{bean}"
            if did in seen:
                continue
            seen.add(did)
            pinfo = processors[bean]
            expanded.append(
                RetrievalHit(
                    doc_id=did,
                    kind="processor",
                    score=h.score * 0.85,
                    title=bean,
                    snippet=str(pinfo.get("class", "")),
                    expand_from=api_id,
                )
            )
    expanded.sort(key=lambda x: x.score, reverse=True)
    return expanded


def hybrid_query(
    keywords: str,
    spec: dict | None = None,
    *,
    max_lines: int = 120,
    top_k: int = 20,
) -> str:
    """Rank platform + catalog + session; expand API→processor edges."""
    plat = _load_platform()
    sess = _load_session()
    terms = _query_terms(keywords, spec)
    hits = _collect_hits(plat, sess, spec, terms, top_k=top_k)
    hits = _graph_expand(plat, hits, terms)

    meta = plat.get("meta") or {}
    lines = [
        "# Context slice (hybrid retrieval)",
        "",
        f"**Query terms:** {', '.join(terms[:20]) or '(none)'}",
        f"**Platform graph:** {meta.get('repo', '—')} updated {meta.get('updated_at', '—')}",
        f"**Hits:** {len(hits)} (lexical rank + API→processor expansion)",
        "",
    ]

    by_kind: dict[str, list[RetrievalHit]] = {}
    for h in hits:
        by_kind.setdefault(h.kind, []).append(h)

    for kind in ("api", "processor", "stub", "catalog", "ticket"):
        group = by_kind.get(kind) or []
        if not group:
            continue
        lines.append(f"## {kind.title()} ({len(group)})")
        lines.append("")
        for h in group[:12]:
            exp = f" <- {h.expand_from}" if h.expand_from else ""
            lines.append(f"- **{h.title}** (score {h.score:.2f}){exp} — {h.snippet}")
        lines.append("")

    if not hits and terms:
        lines.append("_No ranked hits — run `bob sync-graph` and `bob discover-apis`, or broaden keywords._")
        lines.append("")

    out = "\n".join(lines[:max_lines])
    return out


def write_context_slice(
    keywords: str,
    spec: dict | None = None,
    *,
    max_lines: int = 120,
    top_k: int = 20,
) -> Path:
    text = hybrid_query(keywords, spec, max_lines=max_lines, top_k=top_k)
    ctx = agent_dir() / "kg-context-last.md"
    ctx.parent.mkdir(parents=True, exist_ok=True)
    ctx.write_text(text, encoding="utf-8")
    return ctx
