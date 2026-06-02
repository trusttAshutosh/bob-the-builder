"""Discover Kafka producers/consumers/topics from ticket-impacted code (any Novopay flow)."""
from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from host_repo import host_repo_root
from service_discovery import find_repo, list_workspace_repos

# Producer/consumer flow (not bootstrap-only properties).
_KAFKA_FLOW_HINT = re.compile(
    r"NovopayKafkaProducer|sendMessage\s*\(|pushDataToKafkaQueue\s*\(|"
    r"@KafkaListener|AbstractTypedRecordConsumer|"
    r"topicPrefix|MessageBroker\.xml|resolveKafkaTopic|BULK_UPLOAD_LEADS_TOPIC",
    re.I,
)

_KAFKA_FILE_HINT = _KAFKA_FLOW_HINT

_RE_TOPIC_PREFIX_CONST = re.compile(
    r'(?:private\s+static\s+final\s+String\s+)?(\w*TOPIC_PREFIX)\s*=\s*"([^"]+)"',
    re.M,
)
_RE_NOVOPAY_TOPIC_CONFIG = re.compile(
    r'@NovopayConfig\s*\(\s*key\s*=\s*"([^"]*topic[^"]*)"',
    re.I,
)
_RE_PUSH_KAFKA_LITERAL = re.compile(
    r'pushDataToKafkaQueue\s*\(\s*"([^"]+)"\s*\+',
    re.M,
)
_RE_PUSH_KAFKA_STATIC = re.compile(
    r'pushDataToKafkaQueue\s*\(\s*"([^"]+)"\s*,',
    re.M,
)
_RE_KAFKA_LISTENER = re.compile(
    r'@KafkaListener\s*\([^)]*topics\s*=\s*\{?\s*"([^"]+)"',
    re.M,
)
_RE_SEND_LITERAL = re.compile(
    r'\.sendMessage\s*\(\s*"([^"]+)"\s*,',
    re.M,
)
_RE_BOOTSTRAP_PROP = re.compile(
    r"^message\.broker\.bootstrap\.servers\s*=\s*(.+)\s*$",
    re.M,
)
_RE_SERVICE_ENV = re.compile(
    r"novopay\.service\.environment\s*=\s*(\S+)",
    re.M,
)


@dataclass
class KafkaBinding:
    """One produce or consume path discovered in source."""

    binding_id: str
    role: str  # producer | consumer | producer-helper
    repo: str
    source: str
    topic_template: str | None = None
    topic_literal: str | None = None
    config_override_key: str | None = None
    consumer_bean: str | None = None
    consumer_group_prefix: str | None = None
    payload_type: str | None = None
    detail: str = ""

    def resolved_topic(self, tenant: str, environment: str) -> str:
        if self.topic_literal:
            return self.topic_literal
        tpl = self.topic_template or ""
        return (
            tpl.replace("{tenant}", tenant)
            .replace("{environment}", environment.lower())
            .replace("{tenant_code}", tenant)
            .replace("{env}", environment.lower())
        )


@dataclass
class KafkaDiscoveryResult:
    mode_requested: str
    repos_scanned: list[str] = field(default_factory=list)
    seed_files: list[str] = field(default_factory=list)
    bindings: list[KafkaBinding] = field(default_factory=list)
    bootstrap_properties: list[dict[str, str]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    tenant: str = "dsa"
    environment: str = "dev"

    @property
    def has_kafka(self) -> bool:
        return bool(self.bindings)

    def resolved_topics(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for b in self.bindings:
            t = b.resolved_topic(self.tenant, self.environment)
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return out

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["bindings"] = [asdict(b) for b in self.bindings]
        d["resolved_topics"] = self.resolved_topics()
        d["has_kafka"] = self.has_kafka
        return d


def kafka_config(spec: dict | None) -> dict:
    if not spec:
        return {}
    k = (spec.get("run") or {}).get("kafka")
    return k if isinstance(k, dict) else {}


def kafka_mode(spec: dict | None) -> str:
    """off | on | auto — legacy run.kafka.enabled maps to on/off."""
    k = kafka_config(spec)
    mode = (k.get("mode") or "").strip().lower()
    if mode in ("off", "on", "auto"):
        return mode
    if "enabled" in k:
        return "on" if k.get("enabled") else "off"
    return "auto"


def should_run_kafka(spec: dict, discovery: KafkaDiscoveryResult | None) -> bool:
    mode = kafka_mode(spec)
    if mode == "off":
        return False
    if mode == "on":
        return True
    if (spec.get("kafka_scenarios") or []):
        return True
    return bool(discovery and discovery.has_kafka)


def tenant_and_environment(spec: dict, kcfg: dict | None = None) -> tuple[str, str]:
    k = kcfg or kafka_config(spec)
    tenant = (k.get("tenant_code") or "").strip()
    env = (k.get("environment") or "").strip()
    if not tenant:
        prof = (spec.get("env_profile") or "local-dsa").strip()
        tenant = prof.split("-", 1)[-1].strip() if "-" in prof else (prof or "dsa")
    if not env:
        env = "dev"
    return tenant, env.lower()


def _repos_for_ticket(spec: dict) -> list[Path]:
    imp = spec.get("impacted") or {}
    names = list(imp.get("repos") or [])
    repos: list[Path] = []
    seen: set[str] = set()

    def add(p: Path | None) -> None:
        if p and p.is_dir():
            key = str(p.resolve())
            if key not in seen:
                seen.add(key)
                repos.append(p.resolve())

    for name in names:
        add(find_repo(str(name)))
    host = host_repo_root()
    add(host)
    if not names:
        for p in list_workspace_repos():
            add(p)
    return repos


def _glob_java(repo: Path, pattern: str) -> list[Path]:
    root = repo / "src" / "main" / "java"
    if not root.is_dir():
        return []
    return sorted(root.rglob(pattern))


def _find_bean_files(repo: Path, bean: str) -> list[Path]:
    hits: list[Path] = []
    simple = bean[0].upper() + bean[1:] if bean else ""
    for p in _glob_java(repo, f"*{simple}*.java"):
        if p.stem.lower() == simple.lower() or bean.lower() in p.stem.lower():
            hits.append(p)
    return hits


def _find_api_related_java(repo: Path, api_id: str) -> list[Path]:
    if not api_id:
        return []
    stem = api_id.strip()
    patterns = [
        f"*{stem}*.java",
        f"*{stem[0].upper()}{stem[1:]}*.java",
    ]
    out: list[Path] = []
    for pat in patterns:
        out.extend(_glob_java(repo, pat))
    return out[:12]


def _git_changed_files(repo: Path, limit: int = 80) -> list[Path]:
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if r.returncode != 0 or not (r.stdout or "").strip():
            r = subprocess.run(
                ["git", "diff", "--name-only", "main...HEAD"],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=20,
            )
        paths: list[Path] = []
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if line.endswith((".java", ".xml", ".properties")):
                p = repo / line
                if p.is_file():
                    paths.append(p)
            if len(paths) >= limit:
                break
        return paths
    except (OSError, subprocess.TimeoutExpired):
        return []


def _collect_seed_files(spec: dict, repos: list[Path]) -> list[Path]:
    imp = spec.get("impacted") or {}
    seeds: list[Path] = []

    def add(p: Path | None) -> None:
        if p and p.is_file() and p not in seeds:
            seeds.append(p)

    for repo in repos:
        for bean in imp.get("processor_beans") or []:
            for p in _find_bean_files(repo, str(bean)):
                add(p)
        for api in imp.get("gateway_apis") or []:
            for p in _find_api_related_java(repo, str(api)):
                add(p)
        for rel in imp.get("paths") or imp.get("changed_paths") or []:
            add(repo / str(rel))
        for p in _git_changed_files(repo):
            add(p)

    if not seeds and repos:
        host = repos[0]
        for p in _git_changed_files(host):
            add(p)
    return seeds


def _read_text(path: Path, limit: int = 400_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _file_has_kafka_flow(path: Path) -> bool:
    if path.suffix == ".properties":
        return False
    return bool(_KAFKA_FLOW_HINT.search(_read_text(path)))


def _parse_message_broker_xml(path: Path, repo_name: str) -> list[KafkaBinding]:
    out: list[KafkaBinding] = []
    try:
        tree = ElementTree.parse(path)
        root = tree.getroot()
    except (ElementTree.ParseError, OSError):
        return out
    for consumer in root.findall(".//Consumer"):
        prefix_el = consumer.find("topicPrefix")
        bean_el = consumer.find("bean")
        group_el = consumer.find("consumersGroupIdPrefix")
        prefix = (prefix_el.text or "").strip() if prefix_el is not None else ""
        bean = (bean_el.text or "").strip() if bean_el is not None else ""
        group = (group_el.text or "").strip() if group_el is not None else ""
        if not prefix and not bean:
            continue
        tpl = f"{prefix}{{tenant}}_{{environment}}" if prefix else None
        bid = f"consumer:{bean or prefix}"
        out.append(
            KafkaBinding(
                binding_id=bid,
                role="consumer",
                repo=repo_name,
                source=f"{path.as_posix()}",
                topic_template=tpl,
                consumer_bean=bean or None,
                consumer_group_prefix=group or None,
                detail=f"MessageBroker consumer bean={bean} topicPrefix={prefix}",
            )
        )
    prod = root.find(".//Producer")
    if prod is not None and (prod.findtext("enabled") or "").strip().lower() == "true":
        pid = (prod.findtext("producerId") or "").strip()
        out.append(
            KafkaBinding(
                binding_id=f"producer:{pid or 'default'}",
                role="producer",
                repo=repo_name,
                source=f"{path.as_posix()}",
                detail=f"MessageBroker producer enabled id={pid}",
            )
        )
    return out


def _scan_java_file(path: Path, repo_name: str, text: str) -> list[KafkaBinding]:
    out: list[KafkaBinding] = []
    rel = path.as_posix()

    for m in _RE_TOPIC_PREFIX_CONST.finditer(text):
        const_name, prefix = m.group(1), m.group(2)
        tpl = f"{prefix}{{tenant}}_{{environment}}"
        if "resolveKafkaTopic" in text or "serviceEnvironment" in text:
            out.append(
                KafkaBinding(
                    binding_id=f"producer:{path.stem}:{const_name}",
                    role="producer",
                    repo=repo_name,
                    source=rel,
                    topic_template=tpl,
                    detail=f"constant {const_name} + tenant/environment",
                )
            )

    for m in _RE_NOVOPAY_TOPIC_CONFIG.finditer(text):
        key = m.group(1)
        prefix_m = _RE_TOPIC_PREFIX_CONST.search(text)
        tpl = None
        if prefix_m:
            tpl = f"{prefix_m.group(2)}{{tenant}}_{{environment}}"
        out.append(
            KafkaBinding(
                binding_id=f"config:{key}",
                role="producer",
                repo=repo_name,
                source=rel,
                topic_template=tpl,
                config_override_key=key,
                detail=f"@NovopayConfig override key={key}",
            )
        )

    for m in _RE_PUSH_KAFKA_LITERAL.finditer(text):
        base = m.group(1)
        tpl = f"{base}{{tenant}}_{{environment}}"
        out.append(
            KafkaBinding(
                binding_id=f"push:{path.stem}:{base}",
                role="producer-helper",
                repo=repo_name,
                source=rel,
                topic_template=tpl,
                detail="pushDataToKafkaQueue literal+tenant; env appended in producer wrapper",
            )
        )

    for m in _RE_PUSH_KAFKA_STATIC.finditer(text):
        lit = m.group(1)
        if "+" in lit:
            continue
        out.append(
            KafkaBinding(
                binding_id=f"push-static:{path.stem}:{lit}",
                role="producer-helper",
                repo=repo_name,
                source=rel,
                topic_literal=lit,
                detail="pushDataToKafkaQueue static topic base",
            )
        )

    for m in _RE_KAFKA_LISTENER.finditer(text):
        lit = m.group(1)
        out.append(
            KafkaBinding(
                binding_id=f"listener:{path.stem}:{lit}",
                role="consumer",
                repo=repo_name,
                source=rel,
                topic_literal=lit,
                detail="@KafkaListener",
            )
        )

    for m in _RE_SEND_LITERAL.finditer(text):
        lit = m.group(1)
        out.append(
            KafkaBinding(
                binding_id=f"send:{path.stem}:{lit}",
                role="producer",
                repo=repo_name,
                source=rel,
                topic_literal=lit,
                detail="sendMessage literal topic",
            )
        )

    if "AbstractTypedRecordConsumer" in text:
        gm = re.search(r"AbstractTypedRecordConsumer<(\w+)>", text)
        payload = gm.group(1) if gm else None
        out.append(
            KafkaBinding(
                binding_id=f"typed-consumer:{path.stem}",
                role="consumer",
                repo=repo_name,
                source=rel,
                payload_type=payload,
                detail="AbstractTypedRecordConsumer (topic from MessageBroker.xml)",
            )
        )

    return out


def _scan_properties(path: Path, repo_name: str) -> list[dict[str, str]]:
    text = _read_text(path)
    out: list[dict[str, str]] = []
    for m in _RE_BOOTSTRAP_PROP.finditer(text):
        out.append({"repo": repo_name, "file": path.as_posix(), "bootstrap": m.group(1).strip()})
    return out


def _dedupe_bindings(bindings: list[KafkaBinding]) -> list[KafkaBinding]:
    seen: set[str] = set()
    out: list[KafkaBinding] = []
    for b in bindings:
        key = f"{b.role}:{b.binding_id}:{b.topic_template}:{b.topic_literal}:{b.config_override_key}"
        if key in seen:
            continue
        seen.add(key)
        out.append(b)
    return out


def discover_kafka_for_ticket(spec: dict, ticket_dir: Path | None = None) -> KafkaDiscoveryResult:
    """Scan impacted repos/seeds for Kafka usage; resolve topics for local tenant/env."""
    kcfg = kafka_config(spec)
    tenant, env = tenant_and_environment(spec, kcfg)
    mode = kafka_mode(spec)
    repos = _repos_for_ticket(spec)
    repo_names = [p.name for p in repos]
    seeds = _collect_seed_files(spec, repos)

    issues: list[str] = []
    if not repos:
        issues.append("No repos to scan (set impacted.repos or BOB_HOST_REPO / BUILDER_WORKSPACE_ROOT)")

    kafka_seed_files = [p for p in seeds if _file_has_kafka_flow(p)]
    # Git-changed files with Kafka produce/consume usage count as in-flow.
    for repo in repos:
        for p in _git_changed_files(repo):
            if p not in seeds and _file_has_kafka_flow(p):
                seeds.append(p)
                kafka_seed_files.append(p)

    force_scan = bool(kcfg.get("scan_all_repos")) or mode == "on"
    all_bindings: list[KafkaBinding] = []
    bootstraps: list[dict[str, str]] = []

    for repo in repos:
        rname = repo.name
        repo_kafka_seeds = [p for p in kafka_seed_files if p.is_relative_to(repo)]

        prop_paths = list(repo.glob("src/main/resources/application.properties"))
        prop_paths += list(repo.glob("deploy/application/dist/application.properties"))
        for pp in prop_paths[:8]:
            bootstraps.extend(_scan_properties(pp, rname))

        if not repo_kafka_seeds and not force_scan:
            continue

        if repo_kafka_seeds or force_scan:
            mb_paths = list(repo.glob("deploy/**/messagebroker/MessageBroker.xml"))
            mb_paths += list(repo.glob("deploy/**/MessageBroker.xml"))
            for mb in mb_paths:
                all_bindings.extend(_parse_message_broker_xml(mb, rname))

        scan_java = list(repo_kafka_seeds)
        if force_scan:
            for jp in repo.glob("src/main/java/**/*.java"):
                if _file_has_kafka_flow(jp) and jp not in scan_java:
                    scan_java.append(jp)
        for jp in scan_java:
            text = _read_text(jp)
            if _KAFKA_FLOW_HINT.search(text):
                all_bindings.extend(_scan_java_file(jp, rname, text))

    if not all_bindings and repos and (kafka_seed_files or force_scan):
        issues.append(
            "Kafka hinted in seeds but no topic bindings parsed — check MessageBroker.xml or producer code."
        )
    elif not all_bindings and mode == "on":
        issues.append("run.kafka.mode=on but no bindings discovered; add impacted.paths or processor_beans.")

    explicit_topics = [str(t) for t in (kcfg.get("topics") or kcfg.get("capture_topics") or []) if t]
    for i, topic in enumerate(explicit_topics):
        all_bindings.append(
            KafkaBinding(
                binding_id=f"ticket-spec:topic:{i}",
                role="producer",
                repo="ticket-spec",
                source="run.kafka.topics",
                topic_literal=topic,
                detail="explicit topic from ticket-spec",
            )
        )

    bindings = _dedupe_bindings(all_bindings)
    return KafkaDiscoveryResult(
        mode_requested=mode,
        repos_scanned=repo_names,
        seed_files=[p.as_posix() for p in seeds[:50]],
        bindings=bindings,
        bootstrap_properties=bootstraps,
        issues=issues,
        tenant=tenant,
        environment=env,
    )


def resolve_topic_for_scenario(
    spec: dict,
    topic_raw: str,
    discovery: KafkaDiscoveryResult | None,
    *,
    binding_id: str | None = None,
) -> str:
    raw = (topic_raw or "").strip()
    k = kafka_config(spec)
    if raw and raw not in ("auto", "discover", "first"):
        return raw
    if binding_id and discovery:
        for b in discovery.bindings:
            if b.binding_id == binding_id:
                return b.resolved_topic(discovery.tenant, discovery.environment)
    if discovery and discovery.resolved_topics():
        return discovery.resolved_topics()[0]
    explicit = (k.get("topic") or "").strip()
    if explicit and explicit != "auto":
        return explicit
    tenant, env = tenant_and_environment(spec, k)
    return f"unknown-topic-{tenant}_{env}"


def write_discovery_artifact(ticket_dir: Path, discovery: KafkaDiscoveryResult) -> Path:
    ticket_dir.mkdir(parents=True, exist_ok=True)
    path = ticket_dir / "kafka-discovered.json"
    import json

    path.write_text(json.dumps(discovery.to_dict(), indent=2), encoding="utf-8")
    return path
