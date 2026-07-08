import json
from pathlib import Path

import pytest

from backend.app.services import deseq2_execution, formal_de_preflight
from backend.app.services.formal_de_preflight import CommandResult
from scripts import run_phase_4_9_deseq2_demo


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


def _not_ready_preflight() -> dict:
    return {
        "r_available": False,
        "rscript_available": False,
        "r_version": None,
        "rscript_version": None,
        "biocmanager_available": False,
        "deseq2_available": False,
        "formal_method": "deseq2",
        "ready": False,
        "checked_at": "2026-07-09T00:00:00Z",
        "commands_checked": [],
        "warnings": [],
        "errors": [
            "R executable is not available.",
            "Rscript executable is not available.",
        ],
        "limitations": [
            "DESeq2 execution is not available until R, Rscript, BiocManager, and DESeq2 are installed."
        ],
    }


def _ready_preflight() -> dict:
    return {
        "r_available": True,
        "rscript_available": True,
        "r_version": "4.4.1",
        "rscript_version": "4.4.1",
        "biocmanager_available": True,
        "deseq2_available": True,
        "formal_method": "deseq2",
        "ready": True,
        "checked_at": "2026-07-09T00:00:00Z",
        "commands_checked": [
            "R --version",
            "Rscript --version",
            'Rscript --vanilla -e requireNamespace("BiocManager")',
            'Rscript --vanilla -e requireNamespace("DESeq2")',
        ],
        "warnings": [],
        "errors": [],
        "limitations": [
            "This preflight only checks local environment readiness for future DESeq2 execution.",
            "No DESeq2 differential expression analysis is run.",
            "No R or Bioconductor packages are installed, updated, or modified.",
        ],
    }


def _write_mock_results(output_path: str) -> None:
    Path(output_path).write_text(
        "\n".join(
            [
                "gene_id,baseMean,log2FoldChange,lfcSE,stat,pvalue,padj",
                "Gene001,195.2,1.1,0.2,5.5,0.001,0.002",
                "Gene002,146.3,0.9,0.3,3.0,0.02,0.04",
                "Gene003,232.5,-1.0,0.25,-4.0,0.005,0.01",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _assert_no_forbidden_text(value: object) -> None:
    text = str(value).lower()
    for forbidden_fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        assert forbidden_fragment not in text


def test_phase_4_9_demo_script_skips_safely_when_preflight_not_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_root = tmp_path / "outputs"
    monkeypatch.delenv("BIOINFO_INPUT_ROOT", raising=False)
    monkeypatch.delenv("BIOINFO_OUTPUT_ROOT", raising=False)
    monkeypatch.setattr(
        formal_de_preflight,
        "run_deseq2_preflight",
        _not_ready_preflight,
    )

    exit_code = run_phase_4_9_deseq2_demo.run_phase_4_9_demo(
        output_root=output_root,
    )

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert "Phase 4.9 DESeq2 demo skipped" in stdout
    assert "preflight is not ready" in stdout
    assert "unavailable" in stdout.lower()
    assert not (output_root / "tasks" / "task_0001" / "deseq2_results.csv").exists()
    _assert_no_forbidden_text(stdout)


def test_phase_4_9_demo_script_require_deseq2_fails_when_preflight_not_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("BIOINFO_INPUT_ROOT", raising=False)
    monkeypatch.delenv("BIOINFO_OUTPUT_ROOT", raising=False)
    monkeypatch.setattr(
        formal_de_preflight,
        "run_deseq2_preflight",
        _not_ready_preflight,
    )

    exit_code = run_phase_4_9_deseq2_demo.main(
        ["--require-deseq2"],
        output_root=tmp_path / "outputs",
    )

    assert exit_code == 2
    stdout = capsys.readouterr().out
    assert "Phase 4.9 DESeq2 demo skipped" in stdout
    assert "require_deseq2: true" in stdout
    _assert_no_forbidden_text(stdout)


def test_phase_4_9_demo_script_validates_mocked_deseq2_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_root = tmp_path / "outputs"
    monkeypatch.delenv("BIOINFO_INPUT_ROOT", raising=False)
    monkeypatch.delenv("BIOINFO_OUTPUT_ROOT", raising=False)
    monkeypatch.setattr(
        formal_de_preflight,
        "run_deseq2_preflight",
        _ready_preflight,
    )

    def fake_run(args: list[str], timeout_seconds: int = 120) -> CommandResult:
        _write_mock_results(args[-1])
        return CommandResult(args=args, returncode=0)

    monkeypatch.setattr(deseq2_execution, "run_command_safely", fake_run)

    exit_code = run_phase_4_9_deseq2_demo.run_phase_4_9_demo(
        output_root=output_root,
    )

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert "Phase 4.9 DESeq2 demo validation passed" in stdout
    assert "output_dir: tasks/task_0001" in stdout
    _assert_no_forbidden_text(stdout)

    artifact_dir = output_root / "tasks" / "task_0001"
    for artifact_name in run_phase_4_9_deseq2_demo.EXPECTED_ARTIFACTS:
        assert (artifact_dir / artifact_name).is_file()

    manifest = json.loads(
        (artifact_dir / "deseq2_run_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["package_installation_attempted"] is False

    report = (artifact_dir / "report.md").read_text(encoding="utf-8")
    assert "DESeq2" in report
    assert "Statistical significance is not the same as biological significance" in report
    assert "No GO/KEGG/GSEA" in report
    _assert_no_forbidden_text(report)
