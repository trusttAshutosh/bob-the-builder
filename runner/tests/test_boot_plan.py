"""Tests for boot_plan (changed-only service boot)."""
from __future__ import annotations

from boot_plan import (
    BOOT_POLICY_ALL,
    BOOT_POLICY_CHANGED_ONLY,
    BootPlan,
    ServiceBootEntry,
    _classify_entry,
    boot_policy,
    build_boot_plan,
    repos_requiring_fresh_boot,
)


def test_boot_policy_defaults_changed_only() -> None:
    assert boot_policy({}) == BOOT_POLICY_CHANGED_ONLY
    assert boot_policy({"run": {"boot_policy": "all"}}) == BOOT_POLICY_ALL


def test_classify_changed_repo_boots() -> None:
    cfg = {
        "service_key": "credit_card_management",
        "repo_dir": "novopay-platform-creditcard-management",
        "reason": "host repo",
        "default_base": "http://localhost:8016/cc-mgmt",
    }
    spec = {"_env": {"services": {}}, "stubs": [{"ref": "bank-operations/getCardSummary/success-200"}]}
    entry = _classify_entry(
        cfg,
        policy=BOOT_POLICY_CHANGED_ONLY,
        changed_repos={"novopay-platform-creditcard-management"},
        spec=spec,
    )
    assert entry.action == "boot"


def test_classify_unchanged_masterdata_mocks_when_stubs() -> None:
    cfg = {
        "service_key": "masterdata_management",
        "repo_dir": "novopay-platform-masterdata-management",
        "reason": "Java import",
        "default_base": "http://localhost:8015/masterdata",
    }
    spec = {
        "_env": {"services": {}},
        "stubs": [{"ref": "bank-operations/getCardSummary/success-200"}],
        "run": {"apply_masterdata": True},
    }
    entry = _classify_entry(
        cfg,
        policy=BOOT_POLICY_CHANGED_ONLY,
        changed_repos={"novopay-platform-creditcard-management"},
        spec=spec,
    )
    assert entry.action == "mock"
    assert "WireMock" in entry.mock_via


def test_classify_unchanged_peer_mocks() -> None:
    cfg = {
        "service_key": "notifications",
        "repo_dir": "novopay-platform-notifications",
        "reason": "config peer",
    }
    spec = {"_env": {"services": {}}, "stubs": []}
    entry = _classify_entry(
        cfg,
        policy=BOOT_POLICY_CHANGED_ONLY,
        changed_repos={"novopay-platform-creditcard-management"},
        spec=spec,
    )
    assert entry.action == "mock"


def test_build_boot_plan_all_policy_boots_everything(monkeypatch) -> None:
    monkeypatch.setattr(
        "service_boot._discover_all_boot_configs",
        lambda _spec: [
            {"service_key": "credit_card_management", "repo_dir": "novopay-platform-creditcard-management"},
            {"service_key": "masterdata_management", "repo_dir": "novopay-platform-masterdata-management"},
        ],
    )
    spec = {"run": {"boot_policy": "all"}, "_env": {"services": {}}, "impacted": {"repos": []}}
    plan = build_boot_plan(spec)
    assert len(plan.boot) == 2
    assert plan.mock == []


def test_boot_plan_boot_configs() -> None:
    plan = BootPlan(
        policy=BOOT_POLICY_CHANGED_ONLY,
        changed_repos={"novopay-platform-creditcard-management"},
        boot=[
            ServiceBootEntry(
                service_key="credit_card_management",
                repo_dir="novopay-platform-creditcard-management",
                reason="host",
                action="boot",
                cfg={"service_key": "credit_card_management", "repo_dir": "novopay-platform-creditcard-management"},
            )
        ],
    )
    assert len(plan.boot_configs) == 1
    assert plan.boot_configs[0]["repo_dir"] == "novopay-platform-creditcard-management"


def test_repos_requiring_fresh_boot_empty_when_clean(monkeypatch) -> None:
    monkeypatch.setattr("kafka_discovery._git_changed_files", lambda _repo: [])
    monkeypatch.setattr("kafka_discovery._repos_for_ticket", lambda _spec: [])
    assert repos_requiring_fresh_boot({}) == set()


def test_repos_requiring_fresh_boot_includes_host_when_lib_dirty(monkeypatch, tmp_path) -> None:
    host = tmp_path / "novopay-platform-creditcard-management"
    lib = tmp_path / "novopay-platform-lib"
    host.mkdir()
    lib.mkdir()

    def fake_repos(_spec: dict) -> list:
        return [host, lib]

    def fake_diff(repo) -> list:
        return [repo / "src/main/java/Foo.java"] if repo == lib else []

    monkeypatch.setattr("kafka_discovery._repos_for_ticket", fake_repos)
    monkeypatch.setattr("kafka_discovery._git_changed_files", fake_diff)
    monkeypatch.setattr("boot_plan.host_repo_root", lambda: host)

    fresh = repos_requiring_fresh_boot({"impacted": {}})
    assert lib.name in fresh
    assert host.name in fresh


def test_repos_requiring_fresh_boot_host_only_when_host_dirty(monkeypatch, tmp_path) -> None:
    host = tmp_path / "novopay-platform-creditcard-management"
    host.mkdir()

    monkeypatch.setattr("kafka_discovery._repos_for_ticket", lambda _spec: [host])
    monkeypatch.setattr(
        "kafka_discovery._git_changed_files",
        lambda repo: [repo / "src/main/java/Bar.java"],
    )
    monkeypatch.setattr("boot_plan.host_repo_root", lambda: host)

    fresh = repos_requiring_fresh_boot({})
    assert fresh == {host.name}
