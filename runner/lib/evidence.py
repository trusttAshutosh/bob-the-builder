from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from _yaml_util import dump, load, repo_root

BOB_NAME = "Bob the Builder"


def evidence_root(ticket_dir: Path) -> Path:
    p = ticket_dir / "evidence"
    p.mkdir(parents=True, exist_ok=True)
    for sub in ("api", "db", "logs", "unit", "kafka", "redis"):
        (p / sub).mkdir(exist_ok=True)
    return p


def copy_api_responses(ticket_dir: Path) -> None:
    ev = evidence_root(ticket_dir)
    src = ticket_dir / "responses"
    if src.exists():
        for f in src.glob("*.json"):
            shutil.copy2(f, ev / "api" / f.name)


def save_db_evidence(ticket_dir: Path, scenario_id: str, text: str) -> None:
    ev = evidence_root(ticket_dir)
    (ev / "db" / f"{scenario_id}.txt").write_text(text, encoding="utf-8")


def save_log_evidence(ticket_dir: Path, text: str) -> None:
    ev = evidence_root(ticket_dir)
    src = ticket_dir / "log-search.txt"
    if src.exists():
        shutil.copy2(src, ev / "logs" / "log-search.txt")
    else:
        (ev / "logs" / "log-search.txt").write_text(text, encoding="utf-8")


def save_unit_evidence(ticket_dir: Path, summary: str) -> None:
    (evidence_root(ticket_dir) / "unit" / "gradle-test-summary.txt").write_text(summary, encoding="utf-8")


def save_kafka_evidence_index(ticket_dir: Path, paths: list[str]) -> None:
    """Write index of kafka evidence files (complements kafka_runtime.save_kafka_evidence)."""
    ev = evidence_root(ticket_dir) / "kafka"
    ev.mkdir(parents=True, exist_ok=True)
    lines = [p for p in paths if p]
    (ev / "INDEX.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_redis_evidence_note(ticket_dir: Path, text: str) -> None:
    ev = evidence_root(ticket_dir) / "redis"
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "README.txt").write_text(text.strip() + "\n", encoding="utf-8")


def publish_report(ticket_dir: Path, spec: dict, summary_lines: list[str]) -> Path:
    """Persist raw execution log; full report is written at end of validate-ticket."""
    path = ticket_dir / "execution-summary.txt"
    path.write_text("\n".join(summary_lines), encoding="utf-8")
    return path


def write_run_manifest(ticket_dir: Path, spec: dict, results: dict) -> None:
    manifest = {
        "ticket_id": (spec.get("ticket") or {}).get("id"),
        "at": datetime.now().isoformat(timespec="seconds"),
        "scenarios": results,
    }
    dump(ticket_dir / "evidence" / "run-manifest.yaml", manifest)
