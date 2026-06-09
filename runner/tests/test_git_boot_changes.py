"""Tests for git_boot_changes (Java unstaged boot restart detection)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from git_boot_changes import (
    host_restarts_for_dependency_change,
    java_unstaged_boot_changes,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "bob@test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Bob"], cwd=repo, check=True, capture_output=True)


def test_java_unstaged_only_not_staged_only(tmp_path: Path) -> None:
    repo = tmp_path / "svc"
    repo.mkdir()
    java = repo / "src" / "main" / "java" / "Foo.java"
    java.parent.mkdir(parents=True)
    java.write_text("class Foo {}\n", encoding="utf-8")
    _git(repo)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    assert java_unstaged_boot_changes(repo) == []

    java.write_text("class Foo { void m() {} }\n", encoding="utf-8")
    assert len(java_unstaged_boot_changes(repo)) == 1

    subprocess.run(["git", "add", "src/main/java/Foo.java"], cwd=repo, check=True, capture_output=True)
    assert java_unstaged_boot_changes(repo) == []

    java.write_text("class Foo { void m() {} void n() {} }\n", encoding="utf-8")
    paths = java_unstaged_boot_changes(repo)
    assert len(paths) == 1


def test_ignores_properties_and_xml(tmp_path: Path) -> None:
    repo = tmp_path / "svc"
    repo.mkdir()
    props = repo / "application.properties"
    props.write_text("x=1\n", encoding="utf-8")
    _git(repo)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    props.write_text("x=2\n", encoding="utf-8")

    assert java_unstaged_boot_changes(repo) == []


def test_host_restarts_only_for_composite_lib(tmp_path: Path) -> None:
    host = tmp_path / "novopay-platform-creditcard-management"
    notif = tmp_path / "novopay-platform-notifications"
    lib = tmp_path / "novopay-platform-lib"
    host.mkdir()
    notif.mkdir()
    lib.mkdir()
    (host / "settings.gradle").write_text(
        "includeBuild('../novopay-platform-lib')\n", encoding="utf-8"
    )

    assert host_restarts_for_dependency_change(host, [notif.resolve()]) is False
    assert host_restarts_for_dependency_change(host, [lib.resolve()]) is True
