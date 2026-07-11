import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase_8_1_verification_script() -> None:
    result = subprocess.run([sys.executable, "scripts/print_phase_8_1_coze_contract_baseline.py"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "Phase 8.1 Coze integration contract verified" in result.stdout
