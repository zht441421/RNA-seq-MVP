import os
import socket
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path("scripts/run_phase_6_3_local_api_smoke_test.py")
EXPECTED_STDOUT_MARKERS = (
    "Phase 6.3 local API smoke test passed",
    "health verified",
    "task created",
    "inputs registered",
    "run completed",
    "status verified",
    "artifacts verified",
    "coze summary verified",
    "downloads verified",
)
FORBIDDEN_PUBLIC_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "file://",
    "traceback",
    "token",
    "password",
    "secret",
)


def _find_unused_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _assert_no_forbidden_text(value: str) -> None:
    lowered = value.lower()
    for forbidden_fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        assert forbidden_fragment not in lowered


def _assert_loopback_port_closed(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        assert sock.connect_ex(("127.0.0.1", port)) != 0


def test_phase_6_3_local_api_smoke_test_script_executes_successfully() -> None:
    assert SCRIPT_PATH.is_file()

    port = _find_unused_loopback_port()
    env = os.environ.copy()
    env["BIOINFO_SMOKE_TEST_PORT"] = str(port)
    env["WEB_CONCURRENCY"] = "2"
    env["UVICORN_WORKERS"] = "2"
    for env_name in (
        "BIOINFO_INPUT_ROOT",
        "BIOINFO_OUTPUT_ROOT",
        "BIOINFO_TASK_STORE_PATH",
    ):
        env.pop(env_name, None)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )

    _assert_loopback_port_closed(port)
    assert result.returncode == 0
    for expected_marker in EXPECTED_STDOUT_MARKERS:
        assert expected_marker in result.stdout

    _assert_no_forbidden_text(result.stdout)
    _assert_no_forbidden_text(result.stderr)
