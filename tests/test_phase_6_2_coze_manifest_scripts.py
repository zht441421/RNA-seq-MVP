import json
import subprocess
import sys
from pathlib import Path


VALIDATE_SCRIPT = Path("scripts/validate_phase_6_2_coze_manifest.py")
OPENAPI_SUBSET_SCRIPT = Path("scripts/export_phase_6_2_coze_openapi_subset.py")
OPENAPI_SUBSET_PATH = Path("docs/examples/coze_manifest/openapi_coze_subset.json")
RECOMMENDED_ENDPOINTS = (
    ("GET", "/health"),
    ("POST", "/task/create"),
    ("POST", "/task/{task_id}/inputs/register"),
    ("POST", "/task/run"),
    ("GET", "/task/{task_id}/status"),
    ("GET", "/task/{task_id}/coze-summary"),
    ("GET", "/task/{task_id}/artifacts"),
    ("GET", "/task/{task_id}/artifacts/{artifact_name}/download"),
    ("GET", "/task/formal-de/preflight"),
)
FORBIDDEN_FRAGMENTS = (
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


def test_phase_6_2_validate_script_exits_zero() -> None:
    assert VALIDATE_SCRIPT.is_file()
    result = subprocess.run(
        [sys.executable, str(VALIDATE_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Phase 6.2 Coze manifest materials verified" in result.stdout


def test_phase_6_2_openapi_subset_script_exports_safe_subset() -> None:
    assert OPENAPI_SUBSET_SCRIPT.is_file()
    result = subprocess.run(
        [sys.executable, str(OPENAPI_SUBSET_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert OPENAPI_SUBSET_PATH.is_file()
    payload = json.loads(OPENAPI_SUBSET_PATH.read_text(encoding="utf-8"))
    paths = payload["paths"]

    for method, path in RECOMMENDED_ENDPOINTS:
        assert path in paths
        assert method.lower() in paths[path]

    text = json.dumps(payload, sort_keys=True).lower()
    for forbidden_fragment in FORBIDDEN_FRAGMENTS:
        assert forbidden_fragment not in text
