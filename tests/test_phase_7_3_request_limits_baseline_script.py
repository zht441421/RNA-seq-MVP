import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase_7_3_baseline_script_is_safe_and_succeeds() -> None:
    script = ROOT / "scripts" / "print_phase_7_3_request_limits_baseline.py"
    assert script.is_file()
    result = subprocess.run(
        [sys.executable, str(script)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "Phase 7.3 request limits baseline verified" in result.stdout
    rendered = (result.stdout + result.stderr).lower()
    for unsafe in ("d:\\", "c:\\", "/home/", "/mnt/", "file://", "secret="):
        assert unsafe not in rendered
