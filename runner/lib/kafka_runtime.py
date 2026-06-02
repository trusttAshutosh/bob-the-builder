"""Local Kafka via Docker Compose: start/stop, produce/consume, ticket-spec scenarios."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bob_home import bob_assets_root, bob_product_root
from host_repo import host_repo_root
from kafka_discovery import (  # noqa: F401 re-export
    KafkaDiscoveryResult,
    discover_kafka_for_ticket,
    kafka_config,
    kafka_mode,
    resolve_topic_for_scenario,
    should_run_kafka,
    tenant_and_environment,
)

DEFAULT_BOOTSTRAP = "localhost:9092"
KAFKA_UI_DEFAULT = "http://localhost:8090"
CONTAINER_NAME = "bob-kafka"
KAFKA_TOPICS_SH = "/opt/kafka/bin/kafka-topics.sh"
KAFKA_CONSUMER_SH = "/opt/kafka/bin/kafka-console-consumer.sh"
KAFKA_PRODUCER_SH = "/opt/kafka/bin/kafka-console-producer.sh"


def compose_file() -> Path:
    return bob_product_root() / "local" / "kafka" / "docker-compose.yml"


def kafka_enabled(spec: dict | None, discovery: KafkaDiscoveryResult | None = None) -> bool:
    """True when this ticket run should start/use Kafka (mode on, scenarios, or auto+discovery)."""
    if spec and (spec.get("kafka_scenarios") or []):
        return True
    if kafka_mode(spec) == "on":
        return True
    if kafka_mode(spec) == "off":
        return False
    return bool(discovery and discovery.has_kafka)


def bootstrap_servers(spec: dict | None = None) -> str:
    k = kafka_config(spec) if spec else {}
    return (
        (k.get("bootstrap") or os.environ.get("BOB_KAFKA_BOOTSTRAP") or DEFAULT_BOOTSTRAP)
        .strip()
        or DEFAULT_BOOTSTRAP
    )


def _docker_available() -> bool:
    try:
        r = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return r.returncode == 0
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False


def _compose(*args: str, timeout: float = 180) -> subprocess.CompletedProcess[str]:
    cmd = ["docker", "compose", "-f", str(compose_file()), *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _port_open(host: str, port: int, timeout: float = 2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _docker_exec(*args: str, timeout: float = 120) -> subprocess.CompletedProcess[str]:
    cmd = ["docker", "exec", CONTAINER_NAME, *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def resolve_bulk_upload_topic(spec: dict, kcfg: dict | None = None) -> str:
    """Backward-compatible alias; prefer discovery.resolve_topic_for_scenario."""
    k = kcfg or kafka_config(spec)
    explicit = (k.get("topic") or k.get("bulk_upload_topic") or "").strip()
    if explicit and explicit not in ("auto", "discover"):
        return explicit
    disc = discover_kafka_for_ticket(spec)
    if disc.resolved_topics():
        return disc.resolved_topics()[0]
    tenant, env = tenant_and_environment(spec, k)
    return f"unknown-topic-{tenant}_{env}"


def apply_kafka_boot_env(spec: dict | None) -> str:
    """Set BOB_KAFKA_BOOTSTRAP for CC bootRun when Kafka is enabled."""
    bs = bootstrap_servers(spec)
    os.environ["BOB_KAFKA_BOOTSTRAP"] = bs
    return bs


def clear_kafka_boot_env() -> None:
    os.environ.pop("BOB_KAFKA_BOOTSTRAP", None)


def kafka_up(*, wait_seconds: float = 90) -> tuple[bool, str]:
    if not compose_file().is_file():
        return False, f"Missing compose file: {compose_file()}"
    if not _docker_available():
        return False, "Docker not available (install Docker Desktop and ensure daemon is running)"
    r = _compose("up", "-d")
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()[:400]
        return False, f"docker compose up failed: {err}"
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if _port_open("127.0.0.1", 9092):
            hr = _docker_exec(
                KAFKA_TOPICS_SH,
                "--bootstrap-server",
                "localhost:9092",
                "--list",
                timeout=15,
            )
            if hr.returncode == 0:
                ui = kafka_ui_url()
                return True, f"Kafka UP at {DEFAULT_BOOTSTRAP} (UI: {ui})"
        time.sleep(2)
    return False, f"Kafka did not become ready on :9092 within {int(wait_seconds)}s"


def kafka_down() -> tuple[bool, str]:
    if not compose_file().is_file():
        return False, f"Missing compose file: {compose_file()}"
    if not _docker_available():
        return False, "Docker not available"
    r = _compose("down", "--remove-orphans")
    if r.returncode != 0:
        return False, (r.stderr or r.stdout or "compose down failed")[:300]
    clear_kafka_boot_env()
    return True, "Kafka stack stopped"


def kafka_health() -> tuple[bool, str]:
    if not _port_open("127.0.0.1", 9092):
        return False, "port 9092 not listening"
    r = _docker_exec(
        KAFKA_TOPICS_SH,
        "--bootstrap-server",
        "localhost:9092",
        "--list",
        timeout=20,
    )
    if r.returncode != 0:
        return False, (r.stderr or r.stdout or "broker not responding")[:200]
    topics = [t.strip() for t in (r.stdout or "").splitlines() if t.strip()]
    return True, f"UP — {len(topics)} topic(s); UI {kafka_ui_url()}"


def kafka_ui_url(spec: dict | None = None) -> str:
    k = kafka_config(spec) if spec else {}
    return (k.get("ui_url") or os.environ.get("BOB_KAFKA_UI_URL") or KAFKA_UI_DEFAULT).strip()


def list_topics() -> tuple[bool, list[str], str]:
    ok, msg = kafka_health()
    if not ok:
        return False, [], msg
    r = _docker_exec(
        KAFKA_TOPICS_SH,
        "--bootstrap-server",
        "localhost:9092",
        "--list",
        timeout=30,
    )
    if r.returncode != 0:
        return False, [], (r.stderr or r.stdout or "list failed")[:200]
    topics = sorted(t.strip() for t in (r.stdout or "").splitlines() if t.strip())
    return True, topics, msg


def ensure_topic(topic: str) -> tuple[bool, str]:
    r = _docker_exec(
        KAFKA_TOPICS_SH,
        "--bootstrap-server",
        "localhost:9092",
        "--create",
        "--if-not-exists",
        "--topic",
        topic,
        "--partitions",
        "1",
        "--replication-factor",
        "1",
        timeout=30,
    )
    if r.returncode != 0 and "already exists" not in (r.stderr or "").lower():
        return False, (r.stderr or r.stdout or "create topic failed")[:200]
    return True, f"topic {topic} ready"


def consume_topic(
    topic: str,
    *,
    max_messages: int = 50,
    timeout_sec: float = 15,
    from_beginning: bool = True,
) -> tuple[bool, list[dict[str, Any]], str]:
    ok, _ = kafka_health()
    if not ok:
        return False, [], "Kafka not healthy"
    args = [
        KAFKA_CONSUMER_SH,
        "--bootstrap-server",
        "localhost:9092",
        "--topic",
        topic,
        "--max-messages",
        str(max(1, max_messages)),
        "--timeout-ms",
        str(int(max(1000, timeout_sec * 1000))),
    ]
    if from_beginning:
        args.append("--from-beginning")
    r = _docker_exec(*args, timeout=timeout_sec + 30)
    raw_lines = [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]
    messages: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    for i, ln in enumerate(raw_lines, 1):
        try:
            messages.append(json.loads(ln))
        except json.JSONDecodeError:
            messages.append({"_raw": ln})
            parse_errors.append(f"line {i} not JSON")
    detail = f"read {len(messages)} message(s) from {topic}"
    if parse_errors:
        detail += f" ({len(parse_errors)} non-JSON)"
    if r.returncode not in (0, 1) and not messages:
        return False, [], (r.stderr or r.stdout or "consume failed")[:300]
    return True, messages, detail


def produce_json(
    topic: str,
    payload: dict[str, Any] | str,
    *,
    partition_key: str | None = None,
) -> tuple[bool, str]:
    ok, _ = kafka_health()
    if not ok:
        return False, "Kafka not healthy"
    ensure_topic(topic)
    if isinstance(payload, dict):
        body = json.dumps(payload, separators=(",", ":"))
    else:
        body = payload.strip()
    cmd = [
        "docker",
        "exec",
        "-i",
        CONTAINER_NAME,
        KAFKA_PRODUCER_SH,
        "--bootstrap-server",
        "localhost:9092",
        "--topic",
        topic,
    ]
    if partition_key:
        cmd.extend(["--property", "parse.key=true", "--property", "key.separator=:"])
        stdin = f"{partition_key}:{body}"
    else:
        stdin = body
    r = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return False, (r.stderr or r.stdout or "produce failed")[:300]
    return True, f"produced 1 record to {topic}" + (f" key={partition_key}" if partition_key else "")


def _resolve_fixture_path(raw: str, ticket_dir: Path | None) -> Path:
    p = Path(raw)
    if p.is_file():
        return p
    if ticket_dir:
        cand = ticket_dir / raw
        if cand.is_file():
            return cand
    assets = bob_assets_root() / "kafka-fixtures" / Path(raw).name
    if assets.is_file():
        return assets
    host = host_repo_root()
    if host:
        for base in (host / "docs" / "tdd-runs", ticket_dir or Path(".")):
            if base and base.is_dir():
                cand = base / raw
                if cand.is_file():
                    return cand
    raise FileNotFoundError(f"Kafka fixture not found: {raw}")


def _json_path_get(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, list):
            if not part.isdigit():
                return None
            idx = int(part)
            if idx < 0 or idx >= len(cur):
                return None
            cur = cur[idx]
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _assert_json_message(msg: dict[str, Any], rules: list[dict[str, Any]]) -> list[str]:
    errs: list[str] = []
    for rule in rules:
        path = str(rule.get("path", "")).strip()
        if not path:
            continue
        val = _json_path_get(msg, path)
        if rule.get("must_exist") and val is None:
            errs.append(f"{path}: missing")
            continue
        if "equals" in rule and val != rule["equals"]:
            errs.append(f"{path}: expected {rule['equals']!r}, got {val!r}")
        if "contains" in rule and (val is None or str(rule["contains"]) not in str(val)):
            errs.append(f"{path}: does not contain {rule['contains']!r}")
        if "min_length" in rule:
            try:
                n = len(val)  # type: ignore[arg-type]
            except TypeError:
                n = 0
            if n < int(rule["min_length"]):
                errs.append(f"{path}: length {n} < {rule['min_length']}")
    return errs


def save_kafka_evidence(
    ticket_dir: Path,
    topic: str,
    messages: list[dict[str, Any]],
    *,
    label: str = "capture",
) -> Path:
    out_dir = ticket_dir / "evidence" / "kafka"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_topic = topic.replace("/", "_")
    path = out_dir / f"{label}-{safe_topic}-{ts}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for m in messages:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    return path


def capture_configured_topics(
    spec: dict,
    ticket_dir: Path,
    discovery: KafkaDiscoveryResult | None = None,
) -> list[dict[str, Any]]:
    k = kafka_config(spec)
    topics = [str(t) for t in (k.get("capture_topics") or k.get("topics") or []) if t]
    disc = discovery or discover_kafka_for_ticket(spec, ticket_dir)
    if not topics:
        topics = disc.resolved_topics()
    results: list[dict[str, Any]] = []
    consume_cfg = k.get("consume") if isinstance(k.get("consume"), dict) else {}
    max_m = int(consume_cfg.get("max_messages", k.get("capture_max_messages", 20)))
    timeout = float(consume_cfg.get("timeout_sec", k.get("capture_timeout_sec", 10)))
    for topic in topics:
        ok, msgs, detail = consume_topic(
            topic, max_messages=max_m, timeout_sec=timeout, from_beginning=True
        )
        ev_path = save_kafka_evidence(ticket_dir, topic, msgs, label="capture") if msgs else None
        results.append(
            {
                "topic": topic,
                "ok": ok,
                "detail": detail,
                "count": len(msgs),
                "evidence": str(ev_path) if ev_path else None,
            }
        )
    return results


def run_kafka_scenario(
    sc: dict,
    spec: dict,
    ticket_dir: Path,
    discovery: KafkaDiscoveryResult | None = None,
) -> dict[str, Any]:
    sid = sc.get("id", "?")
    topic_raw = (sc.get("topic") or "auto").strip()
    disc = discovery or discover_kafka_for_ticket(spec, ticket_dir)
    topic = resolve_topic_for_scenario(
        spec,
        topic_raw,
        disc,
        binding_id=sc.get("binding_id") or sc.get("binding"),
    )
    result: dict[str, Any] = {"id": sid, "name": sc.get("name", ""), "topic": topic, "pass": True, "detail": []}

    fixture = sc.get("produce_fixture") or sc.get("fixture")
    if fixture:
        try:
            path = _resolve_fixture_path(str(fixture), ticket_dir)
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, FileNotFoundError) as e:
            result["pass"] = False
            result["detail"].append(f"fixture: {e}")
            return result
        key = sc.get("partition_key") or sc.get("key")
        ok, msg = produce_json(topic, payload, partition_key=str(key) if key else None)
        result["detail"].append(msg)
        if not ok:
            result["pass"] = False

    consume_block = sc.get("consume") or {}
    if consume_block or sc.get("assert_json"):
        max_m = int(consume_block.get("max_messages", 5))
        timeout = float(consume_block.get("timeout_sec", 10))
        from_beginning = bool(consume_block.get("from_beginning", True))
        min_messages = int(consume_block.get("min_messages", sc.get("min_messages", 0)))
        ok, msgs, detail = consume_topic(
            topic,
            max_messages=max_m,
            timeout_sec=timeout,
            from_beginning=from_beginning,
        )
        result["detail"].append(detail)
        ev = save_kafka_evidence(ticket_dir, topic, msgs, label=f"scenario-{sid}")
        result["evidence"] = str(ev)
        if min_messages and len(msgs) < min_messages:
            result["pass"] = False
            result["detail"].append(f"expected >= {min_messages} messages, got {len(msgs)}")
        rules = sc.get("assert_json") or []
        if rules and msgs:
            target = msgs[-1]
            errs = _assert_json_message(target, rules)
            if errs:
                result["pass"] = False
                result["detail"].extend(errs)
        elif rules and not msgs:
            result["pass"] = False
            result["detail"].append("assert_json: no messages to check")

    expect_fail = sc.get("expect_consume_failure") or sc.get("expect_failure")
    if expect_fail and result["pass"]:
        result["pass"] = False
        result["detail"].append("expected failure but scenario passed")

    return result


def run_kafka_scenarios(
    spec: dict,
    ticket_dir: Path,
    discovery: KafkaDiscoveryResult | None = None,
) -> list[dict[str, Any]]:
    scenarios = spec.get("kafka_scenarios") or []
    if not scenarios:
        return []
    if not kafka_health()[0]:
        up, msg = kafka_up()
        if not up:
            return [{"id": "?", "pass": False, "detail": [msg], "name": "kafka bootstrap"}]
    apply_kafka_boot_env(spec)
    disc = discovery or discover_kafka_for_ticket(spec, ticket_dir)
    out: list[dict[str, Any]] = []
    for sc in scenarios:
        out.append(run_kafka_scenario(sc, spec, ticket_dir, disc))
    return out


def format_kafka_scenario_summary(results: list[dict[str, Any]]) -> str:
    if not results:
        return "no kafka_scenarios"
    parts = []
    for r in results:
        st = "PASS" if r.get("pass") else "FAIL"
        parts.append(f"{r.get('id', '?')}:{st}")
    return "; ".join(parts)
