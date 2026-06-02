"""Start/stop WireMock without bash (Windows-safe)."""
from __future__ import annotations

import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from bob_home import tdd_root


def _jar_path() -> Path:
    return Path(os.environ.get("WIREMOCK_JAR", tdd_root() / "lib" / "wiremock-standalone-3.13.2.jar"))


def stop_wiremock(root: Path) -> None:
    """Stop WireMock for this runtime root so log/mappings can be replaced (Windows)."""
    root = Path(root)
    pid_file = root / ".wiremock.pid"
    if not pid_file.is_file():
        return
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        pid_file.unlink(missing_ok=True)
        return
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid), "/T"],
            capture_output=True,
            creationflags=flags,
        )
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        time.sleep(0.3)
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    pid_file.unlink(missing_ok=True)
    time.sleep(0.5)


def _download_jar(jar: Path) -> None:
    jar.parent.mkdir(parents=True, exist_ok=True)
    url = (
        "https://repo1.maven.org/maven2/org/wiremock/wiremock-standalone/"
        "3.13.2/wiremock-standalone-3.13.2.jar"
    )
    urllib.request.urlretrieve(url, jar)


def _shutdown_wiremock_port(port: int) -> None:
    """Stop whatever WireMock (or stale process) is listening on port."""
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/__admin/shutdown",
            data=b"",
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
        time.sleep(1)
    except (urllib.error.URLError, OSError, TimeoutError):
        pass


def start_wiremock(root: Path, port: int, *, reload: bool = False) -> tuple[bool, str]:
    """Start WireMock on port. Use reload=True after scenario stub dirs change."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "mappings").mkdir(parents=True, exist_ok=True)
    (root / "__files").mkdir(parents=True, exist_ok=True)

    stop_wiremock(root)
    if reload:
        _shutdown_wiremock_port(port)
    elif not (root / ".wiremock.pid").is_file():
        # Stale listener on port without our pid — avoid serving old mappings.
        _shutdown_wiremock_port(port)

    admin = f"http://127.0.0.1:{port}/__admin/mappings"
    if reload:
        _shutdown_wiremock_port(port)

    jar = _jar_path()
    if not jar.is_file():
        try:
            _download_jar(jar)
        except Exception as e:
            return False, f"WireMock jar missing and download failed: {e}"

    pid_file = root / ".wiremock.pid"
    log_file = root / "wiremock.log"
    cmd = [
        "java",
        "-jar",
        str(jar),
        "--port",
        str(port),
        "--root-dir",
        str(root),
    ]
    with log_file.open("a", encoding="utf-8") as logfh:
        proc = subprocess.Popen(
            cmd,
            stdout=logfh,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
    pid_file.write_text(str(proc.pid), encoding="utf-8")

    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(admin, timeout=2) as resp:
                if 200 <= resp.status < 300:
                    return True, f"WireMock OK http://127.0.0.1:{port} pid={proc.pid}"
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(0.5)
        if proc.poll() is not None:
            tail = log_file.read_text(encoding="utf-8", errors="replace")[-1500:]
            return False, f"WireMock exited {proc.returncode}: {tail}"

    return False, f"WireMock start timeout port {port} — see {log_file}"
