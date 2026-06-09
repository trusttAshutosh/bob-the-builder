"""Detect repo changes that should force a Gradle bootRun restart (Java, unstaged only)."""
from __future__ import annotations

import subprocess
from pathlib import Path

JAVA_SUFFIX = ".java"


def _git_rel_paths(repo: Path, git_args: list[str]) -> list[str]:
    try:
        r = subprocess.run(
            ["git", *git_args],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if r.returncode != 0:
            return []
        return [line.strip() for line in (r.stdout or "").splitlines() if line.strip()]
    except (OSError, subprocess.TimeoutExpired):
        return []


def java_unstaged_boot_changes(repo: Path, limit: int = 80) -> list[Path]:
    """Return .java files with unstaged working-tree edits (Bob boot restart signal).

    Rules:
    - Java source files only (not .xml / .properties / docs).
    - Unstaged diff only (`git diff --name-only`); staged-only edits do not restart.
    - A file in both staged and unstaged lists counts (additional edits after staging).
    """
    unstaged = _git_rel_paths(repo, ["diff", "--name-only"])
    unstaged_java = {p for p in unstaged if p.endswith(JAVA_SUFFIX)}

    paths: list[Path] = []
    for rel in sorted(unstaged_java)[:limit]:
        candidate = repo / rel
        if candidate.is_file():
            paths.append(candidate)
    return paths


def repos_with_java_unstaged(repos: list[Path]) -> set[str]:
    return {repo.name for repo in repos if java_unstaged_boot_changes(repo)}


def host_restarts_for_dependency_change(host: Path | None, changed_repos: list[Path]) -> bool:
    """Restart host primary only when a composite Gradle dependency (e.g. platform-lib) changed."""
    if not host or not changed_repos:
        return False
    host_res = host.resolve()
    for repo in changed_repos:
        if repo.resolve() == host_res:
            continue
        if _is_composite_gradle_dependency(host, repo):
            return True
    return False


def _is_composite_gradle_dependency(host: Path, dep: Path) -> bool:
    if dep.name == "novopay-platform-lib":
        return True
    for gradle in (host / "settings.gradle", host / "settings.gradle.kts"):
        if not gradle.is_file():
            continue
        try:
            text = gradle.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if dep.name in text and "includeBuild" in text:
            return True
    return False
