import subprocess
import sys
from pathlib import Path


CHECKLIST_PATH = Path("docs/phase-6-4-operator-checklist.md")
HELPER_PATH = Path("scripts/print_phase_6_4_operator_checklist.py")
SUCCESS_MESSAGE = "Phase 6.4 operator checklist verified"
UNSAFE_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "file://",
    "token",
    "password",
    "secret",
    "traceback",
)


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def _run_helper() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HELPER_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_phase_6_4_operator_checklist_helper_exists_and_passes() -> None:
    assert HELPER_PATH.is_file()

    result = _run_helper()

    assert result.returncode == 0
    assert SUCCESS_MESSAGE in result.stdout


def test_phase_6_4_operator_checklist_mentions_required_topics() -> None:
    assert CHECKLIST_PATH.is_file()
    lowered = _normalized(CHECKLIST_PATH)

    for required_text in (
        "before launch",
        "environment variables",
        "health check",
        "smoke test",
        "coze base url",
        "artifact download",
        "coze-summary",
        "safety verification",
        "deseq2 preflight",
        "troubleshooting",
        "release tag",
    ):
        assert required_text in lowered


def test_phase_6_4_checklist_and_helper_output_are_public_safe() -> None:
    result = _run_helper()
    assert result.returncode == 0

    combined = "\n".join(
        (
            CHECKLIST_PATH.read_text(encoding="utf-8"),
            result.stdout,
            result.stderr,
        )
    ).lower()
    for unsafe_fragment in UNSAFE_FRAGMENTS:
        assert unsafe_fragment not in combined


def test_phase_6_4_helper_is_offline_and_does_not_start_a_server() -> None:
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
