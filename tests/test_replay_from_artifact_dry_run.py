import subprocess
import sys
from pathlib import Path

from tests.evidence_helpers import run_api_project


def test_replay_from_artifact_dry_run_does_not_execute_docker() -> None:
    result = run_api_project(run_mode="mock")
    artifact_root: Path = result["artifact_root"]

    completed = subprocess.run(
        [sys.executable, "scripts/replay_from_artifact.py", str(artifact_root)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "Dry run only" in completed.stdout
    assert "Docker command:" in completed.stdout
    assert not list(artifact_root.parent.glob(f"{artifact_root.name}_replay_*"))
