from pathlib import Path

import pytest

from scripts import run_phase_4_4_demo


EXPECTED_ARTIFACTS = (
    "run_manifest.json",
    "execution_summary.json",
    "qc_summary.json",
    "normalized_counts_cpm.csv",
    "differential_expression_results.csv",
    "report.md",
)
FORBIDDEN_GENERATED_FRAGMENTS = (
    "pvalue",
    "padj",
    "qvalue",
    "significant",
)
ALLOWED_METHOD_METADATA_FRAGMENTS = (
    "pvalue_available",
    "adjusted_pvalue_available",
)
FORBIDDEN_PUBLIC_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "traceback",
    "token",
    "password",
    "secret",
)


def test_phase_4_4_demo_script_runs_and_generates_expected_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script_path = Path("scripts/run_phase_4_4_demo.py")
    output_root = tmp_path / "outputs"
    monkeypatch.delenv("BIOINFO_INPUT_ROOT", raising=False)
    monkeypatch.delenv("BIOINFO_OUTPUT_ROOT", raising=False)

    assert script_path.is_file()

    exit_code = run_phase_4_4_demo.main(output_root=output_root)

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert "Phase 4.4 demo validation passed" in stdout
    assert "output_dir: tasks/task_0001" in stdout

    artifact_dir = output_root / "tasks" / "task_0001"
    assert artifact_dir.is_dir()
    for artifact_name in EXPECTED_ARTIFACTS:
        artifact_path = artifact_dir / artifact_name
        assert artifact_path.is_file()

    report = (artifact_dir / "report.md").read_text(encoding="utf-8")
    assert "No DESeq2, edgeR, or limma was run." in report
    assert "No formal statistical test" in report
    assert "No p-values or adjusted p-values" in report

    for artifact_name in EXPECTED_ARTIFACTS:
        text = (artifact_dir / artifact_name).read_text(encoding="utf-8").lower()
        for allowed_fragment in ALLOWED_METHOD_METADATA_FRAGMENTS:
            text = text.replace(allowed_fragment, "")
        for forbidden_fragment in FORBIDDEN_GENERATED_FRAGMENTS:
            assert forbidden_fragment not in text

    lowered_stdout = stdout.lower()
    for forbidden_fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        assert forbidden_fragment not in lowered_stdout
