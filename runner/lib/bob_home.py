"""Bob the Builder — one workspace folder: bob-the-builder/{assets,local,runner}."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from _yaml_util import tdd_root
from host_repo import runner_bootstrap_repo, workspace_root
from workspace_env import WORKSPACE_ENV

PRODUCT_DIR = "bob-the-builder"
ASSETS_SUB = "assets"
LOCAL_SUB = "local"

# Old workspace folders from earlier naming (safe to remove after cleanup-workspace)
STALE_WORKSPACE_DIRS = (
    ".bob-the-builder",
    "bob-the-builder-local",
    "novopay-bob",
    "novopay-bob-local",
)


def bob_product_root() -> Path:
    """Single product directory under the workspace (or host .local before setup)."""
    override = os.environ.get("BOB_PRODUCT_ROOT", "").strip()
    if override:
        p = Path(override).expanduser()
    elif workspace_root():
        p = workspace_root() / PRODUCT_DIR
    else:
        import sys

        p = runner_bootstrap_repo() / ".local" / PRODUCT_DIR
        if not getattr(bob_product_root, "_warned_fallback", False):
            bob_product_root._warned_fallback = True  # type: ignore[attr-defined]
            print(
                f"WARN: {WORKSPACE_ENV} not set — using {p}. Run: bob setup",
                file=sys.stderr,
            )
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def bob_local_root() -> Path:
    override = os.environ.get("BOB_LOCAL", "").strip()
    if override:
        p = Path(override).expanduser()
    else:
        p = bob_product_root() / LOCAL_SUB
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def bob_assets_root() -> Path:
    override = os.environ.get("BOB_HOME", "").strip()
    if override:
        p = Path(override).expanduser()
    else:
        p = bob_product_root() / ASSETS_SUB
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def bob_home() -> Path:
    return bob_assets_root()


def seed_root() -> Path:
    return tdd_root() / "_seed"


def _copy_tree(src: Path, dest: Path) -> None:
    if not src.exists():
        return
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dest / item.name
        if item.is_dir():
            if target.exists():
                _copy_tree(item, target)
            else:
                shutil.copytree(item, target)
        elif not target.exists():
            shutil.copy2(item, target)


def ensure_bob_home(*, quiet: bool = False) -> Path:
    assets = bob_assets_root()
    local = bob_local_root()
    marker = assets / ".bob-initialized"
    seed = seed_root()

    for sub in (
        "api-catalog/apis",
        "stub-registry/bank-operations",
        "assertion-catalog/examples",
        "platform-graph",
    ):
        (assets / sub).mkdir(parents=True, exist_ok=True)
    for sub in ("agent", ".runtime-wiremock"):
        (local / sub).mkdir(parents=True, exist_ok=True)

    if not marker.exists() and seed.exists():
        for name in ("api-catalog", "stub-registry", "assertion-catalog", "platform-graph"):
            src = seed / name
            if src.exists():
                _copy_tree(src, assets / name)
        readme = assets / "README.md"
        if not readme.exists():
            readme.write_text(
                "# Bob the Builder — shared assets (BOB_HOME)\n\n"
                "Populated by `bob discover-apis` and `bob sync-graph` from your host repo.\n\n"
                "Reference CC catalogs: `examples/novopay-cc/` (optional copy).\n",
                encoding="utf-8",
            )
        marker.write_text("seeded\n", encoding="utf-8")
        if not quiet:
            print(f"Product folder: {bob_product_root()}")
            print(f"  assets -> {assets}")
            print(f"  local  -> {local}")

    return assets


def api_catalog_dir() -> Path:
    return ensure_bob_home(quiet=True) / "api-catalog"


def stub_registry_dir() -> Path:
    return ensure_bob_home(quiet=True) / "stub-registry"


def assertion_catalog_dir() -> Path:
    return ensure_bob_home(quiet=True) / "assertion-catalog"


def platform_graph_path() -> Path:
    return ensure_bob_home(quiet=True) / "platform-graph" / "platform-graph.yaml"


def agent_dir() -> Path:
    return bob_local_root() / "agent"


def wiremock_runtime_dir() -> Path:
    return bob_local_root() / ".runtime-wiremock"


def prefs_path() -> Path:
    from host_repo import runner_bootstrap_repo

    return runner_bootstrap_repo() / LOCAL_SUB / "user.env"


def bob_home_hint() -> str:
    return str(bob_assets_root())


def bob_local_hint() -> str:
    return str(bob_local_root())


def stale_workspace_dirs(ws: Path) -> list[Path]:
    out: list[Path] = []
    for name in STALE_WORKSPACE_DIRS:
        p = ws / name
        if p.is_dir() and p.resolve() != bob_product_root().resolve():
            out.append(p)
    return out
