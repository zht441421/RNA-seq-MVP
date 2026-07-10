import os
import subprocess
import sys
from pathlib import Path


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


def _assert_no_forbidden_text(value: str) -> None:
    lowered = value.lower()
    for forbidden_fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        assert forbidden_fragment not in lowered


def test_phase_5_6_coze_ready_demo_script_executes_successfully(
    tmp_path: Path,
) -> None:
    script_path = Path("scripts/run_phase_5_6_coze_ready_demo.py")
    assert script_path.is_file()

    env = os.environ.copy()
    env["BIOINFO_OUTPUT_ROOT"] = str(tmp_path / "outputs")
    env["BIOINFO_TASK_STORE_PATH"] = str(tmp_path / "state" / "tasks.sqlite3")
    env.pop("BIOINFO_INPUT_ROOT", None)

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0
    stdout = result.stdout
    stderr = result.stderr
    for expected_marker in (
        "Phase 5.6",
        "task created",
        "inputs registered",
        "run completed",
        "artifacts verified",
        "downloads verified",
        "coze summary verified",
    ):
        assert expected_marker in stdout

    _assert_no_forbidden_text(stdout)
    _assert_no_forbidden_text(stderr)
