"""Diagnose bootRun failures and build Spring override args (MySQL, dist props, Kafka, Redis)."""
from __future__ import annotations

import re
from pathlib import Path

from kafka_runtime import DEFAULT_BOOTSTRAP

# Ordered escalation: each tier adds overrides on top of the previous.
BOOT_PROFILE_STANDARD = "standard"
BOOT_PROFILE_EXTENDED = "extended"
BOOT_PROFILE_AGGRESSIVE = "aggressive"

_DIST_PROPS = Path("deploy/application/dist/application.properties")
_SRC_PROPS = Path("src/main/resources/application.properties")

_LOG_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "mysql",
        re.compile(
            r"Access denied for user|Communications link failure|"
            r"Could not connect to address|SQLException.*password",
            re.I,
        ),
        BOOT_PROFILE_EXTENDED,
    ),
    (
        "kafka",
        re.compile(
            r"kafka|Bootstrap broker|message\.broker|"
            r"Failed to construct kafka|TopicAuthorizationException",
            re.I,
        ),
        BOOT_PROFILE_EXTENDED,
    ),
    (
        "redis",
        re.compile(r"redis|RedisConnection|Unable to connect to Redis", re.I),
        BOOT_PROFILE_EXTENDED,
    ),
    (
        "elasticsearch",
        re.compile(r"Elasticsearch|RestHighLevelClient|9200", re.I),
        BOOT_PROFILE_AGGRESSIVE,
    ),
    (
        "service_name_placeholder",
        re.compile(
            r"Could not resolve placeholder.*novopay\.service\.name|"
            r"novopay\.service\.name.*must not be null",
            re.I,
        ),
        BOOT_PROFILE_STANDARD,
    ),
    (
        "port_bind",
        re.compile(r"Address already in use|BindException|Port.*already in use", re.I),
        BOOT_PROFILE_STANDARD,
    ),
]


def _props_text(repo: Path) -> str:
    chunks: list[str] = []
    for rel in (_SRC_PROPS, _DIST_PROPS):
        p = repo / rel
        if p.is_file():
            try:
                chunks.append(p.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
    return "\n".join(chunks)


def _props_has(text: str, needle: str) -> bool:
    return needle in text


def dist_properties_path(repo: Path) -> Path | None:
    p = repo / _DIST_PROPS
    return p if p.is_file() else None


def repo_has_copy_properties_task(repo: Path) -> bool:
    gradle = repo / "build.gradle"
    if not gradle.is_file():
        return False
    try:
        return "copyProperties" in gradle.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def diagnose_boot_log(log_text: str) -> list[str]:
    """Return ordered remediation profile ids suggested from boot.log tail."""
    if not log_text.strip():
        return [BOOT_PROFILE_EXTENDED]
    tail = log_text[-12000:]
    seen: list[str] = []
    for _name, pattern, profile in _LOG_PATTERNS:
        if pattern.search(tail) and profile not in seen:
            seen.append(profile)
    if not seen:
        seen.append(BOOT_PROFILE_EXTENDED)
    return seen


def escalation_chain(initial_profiles: list[str]) -> list[str]:
    """Merge diagnosis suggestions with a safe default retry ladder."""
    order = [BOOT_PROFILE_STANDARD, BOOT_PROFILE_EXTENDED, BOOT_PROFILE_AGGRESSIVE]
    out: list[str] = []
    for p in initial_profiles + order:
        if p not in out:
            out.append(p)
    return out


def build_spring_args(
    repo: Path,
    profile: str,
    *,
    mysql_user: str,
    mysql_pass: str,
    include_kafka: bool = False,
) -> str:
    """Space-separated Spring Boot CLI properties for Gradle --args=."""
    text = _props_text(repo)
    parts: list[str] = []

    if dist_properties_path(repo):
        parts.append(
            "--spring.config.additional-location="
            "file:./deploy/application/dist/application.properties"
        )

    if _props_has(text, "spring.datasource."):
        parts.append(f"--spring.datasource.username={mysql_user}")
        parts.append(f"--spring.datasource.password={mysql_pass}")

    if _props_has(text, "novopay.platform.master.datasource."):
        parts.append(f"--novopay.platform.master.datasource.username={mysql_user}")
        parts.append(f"--novopay.platform.master.datasource.password={mysql_pass}")

    parts.append("--management.health.elasticsearch.enabled=false")

    if profile in (BOOT_PROFILE_EXTENDED, BOOT_PROFILE_AGGRESSIVE) or include_kafka:
        kafka = _kafka_bootstrap()
        if _props_has(text, "message.broker.") or include_kafka:
            parts.append(f"--message.broker.bootstrap.servers={kafka}")

    if profile in (BOOT_PROFILE_EXTENDED, BOOT_PROFILE_AGGRESSIVE):
        redis_host = _redis_host()
        redis_port = _redis_port()
        if _props_has(text, "novopay.cache."):
            parts.append(f"--novopay.cache.host={redis_host}")
            parts.append(f"--novopay.cache.port={redis_port}")
        parts.append("--management.health.redis.enabled=false")
        parts.append("--management.health.kafka.enabled=false")

    if profile == BOOT_PROFILE_AGGRESSIVE:
        parts.append("--spring.jpa.hibernate.ddl-auto=none")

    return " ".join(parts)


def _kafka_bootstrap() -> str:
    import os

    return (os.environ.get("BOB_KAFKA_BOOTSTRAP") or DEFAULT_BOOTSTRAP).strip()


def _redis_host() -> str:
    import os

    return (os.environ.get("REDIS_HOST") or "127.0.0.1").strip()


def _redis_port() -> str:
    import os

    return (os.environ.get("REDIS_PORT") or "6379").strip()
