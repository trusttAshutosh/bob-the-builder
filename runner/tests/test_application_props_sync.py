"""Unit tests for application_props_sync."""
from pathlib import Path

from application_props_sync import _patch_properties_file


def test_patch_properties_rewrites_mysql_keys(tmp_path: Path) -> None:
    props = tmp_path / "application.properties"
    props.write_text(
        "spring.datasource.url=jdbc:mysql://localhost:3306/platform_master\n"
        "spring.datasource.username=root\n"
        "spring.datasource.password=root\n",
        encoding="utf-8",
    )
    creds = {"host": "10.0.0.5", "port": "3307", "user": "bob_user", "pass": "secret", "platform_schema": "platform_master"}
    assert _patch_properties_file(props, creds) is True
    text = props.read_text(encoding="utf-8")
    assert "jdbc:mysql://10.0.0.5:3307/platform_master" in text
    assert "spring.datasource.username=bob_user" in text
    assert "spring.datasource.password=secret" in text
