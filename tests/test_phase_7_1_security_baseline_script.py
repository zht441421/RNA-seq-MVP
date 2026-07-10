import subprocess
import sys
from pathlib import Path


HELPER_PATH = Path("scripts/print_phase_7_1_security_baseline.py")
SUCCESS_MESSAGE = "Phase 7.1 API security baseline verified"
UNSAFE_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "file://",
    "password=",
    "token=",
    "secret=",
    "traceback",
)


def _run_helper() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HELPER_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_phase_7_1_helper_exists_and_passes() -> None:
    assert HELPER_PATH.is_file()
    result = _run_helper()
    assert result.returncode == 0
    assert SUCCESS_MESSAGE in result.stdout


def test_phase_7_1_helper_output_is_public_safe() -> None:
    result = _run_helper()
    assert result.returncode == 0
    output = f"{result.stdout}\n{result.stderr}".lower()
    for unsafe_fragment in UNSAFE_FRAGMENTS:
        assert unsafe_fragment not in output


def test_phase_7_1_helper_is_offline_and_does_not_start_a_server() -> None:
    source = HELPER_PATH.read_text(encoding="utf-8").lower()
    for disallowed_import_or_call in (
        "import socket",
        "import subprocess",
        "import urllib",
        "import requests",
        "uvicorn",
        "http://",
        "https://",
    ):
        assert disallowed_import_or_call not in source
