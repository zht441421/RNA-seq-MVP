import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase_7_4_baseline_script() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/print_phase_7_4_rate_limiting_baseline.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Phase 7.4 rate limiting baseline verified" in result.stdout
