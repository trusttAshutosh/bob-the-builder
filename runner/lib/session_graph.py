from __future__ import annotations

import subprocess
import time
from pathlib import Path

from _yaml_util import dump, load, repo_root
from bob_home import agent_dir, ensure_bob_home


def session_path() -> Path:
    ensure_bob_home(quiet=True)
    p = agent_dir() / "session-graph.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=repo_root(), capture_output=True, text=True, timeout=30)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def update(
    ticket_id: str,
    title: str = "",
    run_results: dict | None = None,
    run_data: dict | None = None,
) -> Path:
    data = load(session_path()) if session_path().exists() else {"tasks": [], "branches": {}, "runs": []}
    br = _git("rev-parse", "--abbrev-ref", "HEAD")
    changed = sorted(
        set(
            _git("diff", "--name-only", "HEAD").splitlines()
            + _git("diff", "--cached", "--name-only").splitlines()
        )
    )
    data["branches"][br] = {
        "ticket_id": ticket_id,
        "title": title,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "files_changed": changed[:100],
    }
    task_entry: dict = {
        "ticket_id": ticket_id,
        "title": title,
        "branch": br,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "results": run_results or {},
    }
    if run_data:
        task_entry["overall"] = run_data.get("overall")
        task_entry["duration_seconds"] = run_data.get("duration_seconds")
        task_entry["decisions"] = {
            k: run_data.get("decisions", {}).get(k)
            for k in (
                "env_profile",
                "header_profile",
                "stub_refs",
                "apis_from_catalog",
                "cc_health",
                "crn",
            )
            if run_data.get("decisions", {}).get(k) is not None
        }
    tasks = [t for t in data.get("tasks", []) if t.get("ticket_id") != ticket_id]
    tasks.insert(0, task_entry)
    data["tasks"] = tasks[:30]

    if run_data:
        runs = [r for r in data.get("runs", []) if r.get("ticket_id") != ticket_id]
        runs.insert(
            0,
            {
                "ticket_id": ticket_id,
                "at": run_data.get("finished_at", task_entry["at"]),
                "overall": run_data.get("overall"),
                "duration_seconds": run_data.get("duration_seconds"),
                "branch": run_data.get("branch", br),
                "decisions": task_entry.get("decisions", {}),
                "scenario_count": len(run_data.get("scenarios") or []),
            },
        )
        data["runs"] = runs[:50]

    data["meta"] = {"updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    dump(session_path(), data)
    return session_path()


def query_slice(keywords: str, max_lines: int = 100) -> str:
    from platform_graph import platform_path

    pp = platform_path()
    plat = load(pp) if pp.exists() else {}
    sess = load(session_path()) if session_path().exists() else {}
    terms = [t.lower() for t in keywords.split() if t.strip()]

    def match(s: str) -> bool:
        s = s.lower()
        return any(t in s for t in terms) if terms else True

    lines = ["# Context slice (platform + session)", ""]
    lines.append("## Platform features")
    for feat, info in (plat.get("features") or {}).items():
        if match(feat) or match(str(info)):
            lines.append(f"- **{feat}**: {info}")

    lines.append("\n## Gateway APIs")
    for api, info in sorted((plat.get("gateway_apis") or {}).items()):
        if match(api):
            lines.append(f"- `{api}` beans={info.get('processor_beans', [])}")

    lines.append("\n## Processors")
    for bean, info in sorted((plat.get("processors") or {}).items()):
        if match(bean) or match(info.get("class", "")):
            lines.append(f"- `{bean}` → {info.get('class')} ({info.get('extends')})")

    lines.append("\n## Bank stub registry")
    for op, fixtures in sorted((plat.get("bank_operation_stubs") or {}).items()):
        if match(op):
            lines.append(f"- `{op}`: {fixtures}")

    lines.append("\n## Session")
    for br, info in list((sess.get("branches") or {}).items())[-5:]:
        if match(br) or match(str(info)):
            lines.append(f"- branch `{br}` → ticket {info.get('ticket_id')}")

    out = "\n".join(lines[:max_lines])
    ctx = agent_dir() / "kg-context-last.md"
    ctx.parent.mkdir(parents=True, exist_ok=True)
    ctx.write_text(out, encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "update":
        update(sys.argv[2] if len(sys.argv) > 2 else "unknown", sys.argv[3] if len(sys.argv) > 3 else "")
    else:
        print(query_slice(" ".join(sys.argv[1:]) if len(sys.argv) > 1 else "loan"))


def load_platform() -> dict:
    from platform_graph import platform_path

    p = platform_path()
    return load(p) if p.exists() else {}
