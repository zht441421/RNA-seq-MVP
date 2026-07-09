import json
from pathlib import Path

import pytest

from backend.app.services import deseq2_execution
from backend.app.services.contrast_validation import ContrastValidationError
from backend.app.services.deseq2_execution import execute_task_deseq2
from backend.app.services.formal_de_preflight import CommandResult


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


def _assert_safe(body: object) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_PUBLIC_FRAGMENTS)


def _write_inputs(input_root: Path) -> tuple[str, str]:
    demo_dir = input_root / "demo"
    demo_dir.mkdir(parents=True)
    (demo_dir / "metadata.csv").write_text(
        "\n".join(
            [
                "sample_id,condition",
                "sample_1,control",
                "sample_2,control",
                "sample_3,treatment",
                "sample_4,treatment",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (demo_dir / "counts.csv").write_text(
        "\n".join(
            [
                "gene_id,sample_1,sample_2,sample_3,sample_4",
                "GeneA,10,10,30,30",
                "GeneB,90,90,70,70",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return "demo/metadata.csv", "demo/counts.csv"


def _ready_preflight() -> dict:
    return {
        "ready": True,
        "r_available": True,
        "rscript_available": True,
        "biocmanager_available": True,
        "deseq2_available": True,
        "warnings": [],
        "limitations": [],
    }


def _write_mock_results(output_path: str) -> None:
    Path(output_path).write_text(
        "\n".join(
            [
                "gene_id,baseMean,log2FoldChange,lfcSE,stat,pvalue,padj",
                "GeneA,20,1.3,0.2,6.5,0.001,0.002",
                "GeneB,80,-0.4,0.3,-1.3,0.1,0.2",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_deseq2_receives_explicit_contrast_and_writes_contrast_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "outputs"
    metadata_file, count_matrix_file = _write_inputs(input_root)
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str(input_root))
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    calls: list[list[str]] = []

    def fake_run(args: list[str], timeout_seconds: int = 120) -> CommandResult:
        calls.append(args)
        _write_mock_results(args[-1])
        return CommandResult(args=args, returncode=0)

    monkeypatch.setattr(deseq2_execution, "run_command_safely", fake_run)

    result = execute_task_deseq2(
        task_id="task_deseq2_contrast",
        metadata_file=metadata_file,
        count_matrix_file=count_matrix_file,
        project_name="demo_bulk_rnaseq",
        omics_type="bulk_rnaseq",
        contrast_column="condition",
        contrast_numerator="treatment",
        contrast_denominator="control",
        preflight=_ready_preflight(),
    )

    assert result.status == "deseq2_analysis_completed"
    assert calls
    command = calls[0]
    assert command[-4:-1] == ["condition", "treatment", "control"]
    script_text = Path(command[2]).read_text(encoding="utf-8")
    assert (
        "results(dds, contrast = c(contrast_column, contrast_numerator, contrast_denominator))"
        in script_text
    )

    output_dir = output_root / "tasks" / "task_deseq2_contrast"
    summary = json.loads((output_dir / "deseq2_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (output_dir / "deseq2_run_manifest.json").read_text(encoding="utf-8")
    )
    interpretation = json.loads(
        (output_dir / "deseq2_interpretation_summary.json").read_text(encoding="utf-8")
    )
    report_text = (output_dir / "report.md").read_text(encoding="utf-8")

    for payload in (summary, manifest, interpretation):
        assert payload["contrast"]["direction"] == "treatment_vs_control"
        assert payload["positive_log2fc_interpretation"] == (
            "Higher in treatment relative to control"
        )
        assert payload["negative_log2fc_interpretation"] == (
            "Lower in treatment relative to control"
        )
        _assert_safe(payload)
    assert "Positive log2FoldChange: Higher in treatment relative to control" in report_text


def test_invalid_deseq2_contrast_does_not_call_rscript(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "outputs"
    metadata_file, count_matrix_file = _write_inputs(input_root)
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str(input_root))
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    calls: list[list[str]] = []
    monkeypatch.setattr(
        deseq2_execution,
        "run_command_safely",
        lambda args, timeout_seconds=120: calls.append(args) or CommandResult(
            args=args,
            returncode=0,
        ),
    )

    with pytest.raises(ContrastValidationError) as exc_info:
        execute_task_deseq2(
            task_id="task_invalid_contrast",
            metadata_file=metadata_file,
            count_matrix_file=count_matrix_file,
            contrast_column="condition",
            contrast_numerator="case",
            contrast_denominator="control",
            preflight=_ready_preflight(),
        )

    assert calls == []
    assert exc_info.value.to_detail()["error_code"] == "CONTRAST_VALIDATION_FAILED"
    assert not (output_root / "tasks" / "task_invalid_contrast").exists()
    _assert_safe(exc_info.value.to_detail())
