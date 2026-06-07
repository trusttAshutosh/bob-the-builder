"""Verify clean install + discover-apis from a non-CC fixture host."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

from _yaml_util import load, runner_root

FIXTURE_HOST = runner_root() / "tests" / "fixtures" / "ci-host"
HOST_DIR_NAME = "novopay-platform-payments-fixture"
EXPECTED_APIS = ("smokeGetHealth", "smokeSubmitOrder")
CC_SERVICE_SLUG = "credit_card_management"


@dataclass
class FreshInstallResult:
    ok: bool
    message: str
    apis_created: int = 0


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_bob(command: str, *, repo: Path, cwd: Path, env: dict[str, str]) -> int:
    proc = subprocess.run(
        [sys.executable, str(repo / "bob.py"), command],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"bob {command} exited {proc.returncode}: {detail}")
    return proc.returncode


def assert_empty_api_catalog(bob_home: Path) -> None:
    apis_dir = bob_home / "api-catalog" / "apis"
    yaml_files = sorted(apis_dir.glob("*.yaml"))
    if yaml_files:
        names = ", ".join(p.name for p in yaml_files[:5])
        raise AssertionError(f"expected empty assets/api-catalog/apis after install, found: {names}")

    index_path = bob_home / "api-catalog" / "index.yaml"
    if not index_path.is_file():
        raise AssertionError("missing api-catalog/index.yaml after install")

    index = load(index_path)
    apis = index.get("apis") or {}
    if apis:
        raise AssertionError(f"expected empty index apis map after install, found {len(apis)} entries")


def assert_discovered_catalog(bob_home: Path, *, host_name: str) -> int:
    apis_dir = bob_home / "api-catalog" / "apis"
    missing = [name for name in EXPECTED_APIS if not (apis_dir / f"{name}.yaml").is_file()]
    if missing:
        raise AssertionError(f"missing discovered API skeletons: {', '.join(missing)}")

    index_path = bob_home / "api-catalog" / "index.yaml"
    index = load(index_path)
    if len(index.get("apis") or {}) != len(EXPECTED_APIS):
        raise AssertionError("index.yaml api count does not match discovered skeletons")

    expected_service = host_name
    if host_name.startswith("novopay-platform-"):
        expected_service = host_name[len("novopay-platform-") :]

    for api_id in EXPECTED_APIS:
        data = load(apis_dir / f"{api_id}.yaml")
        service = str(data.get("service") or "")
        base_env = str((data.get("http") or {}).get("base_env") or "")
        if service != expected_service:
            raise AssertionError(
                f"{api_id}.yaml service={service!r} expected non-CC slug {expected_service!r}"
            )
        if service == CC_SERVICE_SLUG:
            raise AssertionError(f"{api_id}.yaml still uses CC service slug {CC_SERVICE_SLUG!r}")
        if base_env != "PAYMENTS_BASE":
            raise AssertionError(f"{api_id}.yaml base_env={base_env!r} expected PAYMENTS_BASE")

    return len(EXPECTED_APIS)


def run_fresh_install_verify(*, repo: Path | None = None, verbose: bool = True) -> FreshInstallResult:
    if not yaml:
        return FreshInstallResult(False, "PyYAML required")

    repo = (repo or _repo_root()).resolve()
    fixture = FIXTURE_HOST
    runner = repo / "runner"
    if not fixture.is_dir():
        return FreshInstallResult(False, f"missing fixture host: {fixture}")

    with tempfile.TemporaryDirectory(prefix="bob-fresh-install-") as td:
        ws = Path(td) / "workspace"
        ws.mkdir()
        host = ws / HOST_DIR_NAME
        shutil.copytree(fixture, host)

        bob_home = Path(td) / "bob-home"
        bob_local = Path(td) / "bob-local"
        env = os.environ.copy()
        env["BUILDER_WORKSPACE_ROOT"] = str(ws)
        env["BOB_PRODUCT_ROOT"] = str(repo)
        env["BOB_HOST_REPO"] = str(host)
        env["BOB_HOME"] = str(bob_home)
        env["BOB_LOCAL"] = str(bob_local)
        env["BOB_IGNORE_PREFS"] = "1"
        env["PYTHONPATH"] = str(runner / "lib")

        try:
            _run_bob("install", repo=repo, cwd=repo, env=env)
            if not (bob_home / ".bob-initialized").is_file():
                return FreshInstallResult(False, "bob install did not seed BOB_HOME")

            assert_empty_api_catalog(bob_home)
            if verbose:
                print("OK: empty api-catalog after bob install")

            _run_bob("discover-apis", repo=repo, cwd=host, env=env)
            count = assert_discovered_catalog(bob_home, host_name=HOST_DIR_NAME)
            if verbose:
                print(f"OK: discover-apis from non-CC host ({HOST_DIR_NAME}) -> {count} skeletons")
                print(f"OK: service slug payments-fixture, base_env PAYMENTS_BASE")

            return FreshInstallResult(
                True,
                f"fresh install verify OK ({count} APIs from {HOST_DIR_NAME})",
                apis_created=count,
            )
        except (AssertionError, RuntimeError) as exc:
            return FreshInstallResult(False, str(exc))


def main(argv: list[str] | None = None) -> int:
    verbose = "--quiet" not in (argv or sys.argv[1:])
    result = run_fresh_install_verify(verbose=verbose)
    if result.ok:
        print(result.message)
        return 0
    print(f"FAIL: {result.message}", file=sys.stderr)
    return 1
