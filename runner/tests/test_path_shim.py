"""Tests for path_shim flat command shims."""
from __future__ import annotations

from pathlib import Path

from path_shim import _install_shims, flat_shim_commands


def test_flat_shim_commands_include_builder_intel() -> None:
    names = flat_shim_commands()
    assert "builder-intel" in names
    assert "ego-boost" in names
    assert "validate-ticket" in names
    assert "help" not in names
    assert "install" not in names


def test_install_shims_writes_builder_intel_cmd(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    installed = _install_shims(bin_dir)
    assert "builder-intel.cmd" in installed
    assert (bin_dir / "builder-intel.cmd").is_file()
    text = (bin_dir / "builder-intel.cmd").read_text(encoding="utf-8")
    assert "bob.py" in text
    assert "builder-intel" in text
