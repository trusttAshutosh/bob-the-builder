#!/usr/bin/env python3
"""Committed platform graph — run: python3 platform_graph.py"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from _yaml_util import dump, host_repo_root, load, tdd_root
from host_repo import host_repo_name
from bob_home import api_catalog_dir, platform_graph_path, stub_registry_dir


def platform_path() -> Path:
    return platform_graph_path()


def scan() -> dict:
    repo = host_repo_root()
    name = host_repo_name()
    g = {
        "meta": {
            "version": 1,
            "repo": name,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
        "repos": {
            name: {"role": "host-service", "base_branch": "ddp-prod"},
        },
        "patterns": {
            "simple_processor": "AbstractProcessor",
            "transaction_processor": "AbstractCreditCardManager",
            "audit_table": "transaction_audit",
        },
        "gateway_apis": {},
        "orchestration": {},
        "processors": {},
        "features": {},
        "bank_operation_stubs": {},
    }

    for xml in (repo / "deploy/application/orchestration").rglob("*.xml"):
        text = xml.read_text(encoding="utf-8", errors="ignore")
        rel = str(xml.relative_to(repo)).replace("\\", "/")
        for m in re.finditer(r'<Request\s+name="([^"]+)"[^>]*>(.*?)</Request>', text, re.DOTALL):
            req, body = m.group(1), m.group(2)
            beans = list(dict.fromkeys(re.findall(r'bean="([^"]+)"', body)))
            g["orchestration"][req] = {"file": rel, "processor_beans": beans}
            g["gateway_apis"][req] = {"path": f"/api/v1/{req}", "processor_beans": beans}

    for jf in (repo / "src/main/java").rglob("*Processor.java"):
        text = jf.read_text(encoding="utf-8", errors="ignore")
        pkg_m = re.search(r"package\s+([\w.]+)", text)
        pkg = pkg_m.group(1) if pkg_m else ""
        cls_m = re.search(r"class\s+(\w+)", text)
        if not cls_m:
            continue
        cls = cls_m.group(1)
        bean = cls[0].lower() + cls[1:]
        extends = (
            "AbstractCreditCardManager"
            if "AbstractCreditCardManager" in text
            else ("AbstractProcessor" if "AbstractProcessor" in text else "")
        )
        g["processors"][bean] = {
            "class": f"{pkg}.{cls}",
            "file": str(jf.relative_to(repo)).replace("\\", "/"),
            "extends": extends,
        }

    cat = api_catalog_dir() / "apis"
    if cat.exists():
        for yf in cat.glob("*.yaml"):
            data = load(yf)
            api_id = data.get("api_id", yf.stem)
            g["gateway_apis"].setdefault(api_id, {}).update(
                {"catalog": str(yf.relative_to(repo)).replace("\\", "/"), "bank_calls": data.get("bank_calls") or []}
            )

    reg = stub_registry_dir() / "bank-operations"
    if reg.exists():
        for op_dir in reg.iterdir():
            if op_dir.is_dir():
                g["bank_operation_stubs"][op_dir.name] = [f.stem for f in op_dir.glob("*.yaml")]

    # Feature tags are defined per ticket (impacted.feature) and assertion-catalog/*.yaml
    return g


def sync() -> Path:
    dump(platform_path(), scan())
    return platform_path()


if __name__ == "__main__":
    p = sync()
    print(p)
