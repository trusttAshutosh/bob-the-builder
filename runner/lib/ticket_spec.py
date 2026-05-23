from __future__ import annotations

from pathlib import Path
from typing import Any

from _yaml_util import load, repo_root, tdd_root


def ticket_dir(ticket_id: str) -> Path:
    return repo_root() / "docs/tdd-runs" / ticket_id


def spec_path(ticket_dir: Path) -> Path:
    ts = ticket_dir / "ticket-spec.yaml"
    if ts.exists():
        return ts
    raise FileNotFoundError(f"No ticket-spec.yaml in {ticket_dir} — run: bob init-ticket <id> \"<title>\"")


def load_spec(ticket_dir: Path) -> dict:
    data = load(spec_path(ticket_dir))
    data.setdefault("version", 2)
    env_profile = data.get("env_profile", "local-dsa")
    env_path = repo_root() / "deploy/tdd" / f"{env_profile}.yaml"
    if env_path.exists():
        data["_env"] = load(env_path)
    return data


def init_spec(ticket_id: str, title: str, description: str = "") -> Path:
    d = ticket_dir(ticket_id)
    d.mkdir(parents=True, exist_ok=True)
    for sub in ("evidence/api", "evidence/db", "evidence/logs", "evidence/unit", "stubs"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    schema = tdd_root() / "schemas/ticket-spec.schema.yaml"
    dest = d / "ticket-spec.yaml"
    if not dest.exists() and schema.exists():
        text = schema.read_text(encoding="utf-8")
        text = text.replace("TICKET-001", ticket_id).replace("Short title", title)
        dest.write_text(text, encoding="utf-8")
    ts = load(dest)
    ts["ticket"] = {"id": ticket_id, "title": title, "description": description or "", "acceptance_criteria": []}
    from _yaml_util import dump

    dump(dest, ts)
    (d / "TEST_PLAN.md").write_text(
        f"# {title}\n\n**Ticket:** {ticket_id}\n\n## Acceptance criteria\n\n- [ ] TBD\n",
        encoding="utf-8",
    )
    return dest


def wiremock_port(spec: dict) -> int:
    return int((spec.get("run") or {}).get("wiremock_port", 9090))


def masterdata_rows(spec: dict) -> list[dict]:
    return spec.get("masterdata") or []


def scenarios(spec: dict) -> list[dict]:
    return spec.get("scenarios") or []


def git_checkout_env(spec: dict) -> dict[str, str]:
    g = spec.get("git") or {}
    return {
        "branch_policy": str(g.get("branch_policy", "none")),
        "base_branch": str(g.get("base_branch", "ddp-prod")),
        "branch_prefix": str(g.get("branch_prefix", "ddp-fea-")),
    }


def impacted_keywords(spec: dict) -> str:
    t = spec.get("ticket") or {}
    imp = spec.get("impacted") or {}
    parts = [t.get("id", ""), t.get("title", ""), imp.get("feature", "")]
    parts.extend(imp.get("gateway_apis") or [])
    parts.extend(imp.get("bank_operations") or [])
    return " ".join(str(p) for p in parts if p)
