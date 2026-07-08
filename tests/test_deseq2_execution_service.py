import json
from pathlib import Path

import pytest

from backend.app.services import deseq2_execution
from backend.app.services.deseq2_execution import (
    DESEQ2_PREFLIGHT_NOT_READY,
    Deseq2ExecutionError,
    execute_task_deseq2,
)
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


def _assert_no_forbidden_public_fragments(body: object) -> None:
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
                "GeneA,100,120,250,260",
                "GeneB,20,22,10,12",
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


def _not_ready_preflight() -> dict:
    return {
        "ready": False,
        "r_available": False,
        "rscript_available": False,
        "biocmanager_available": False,
        "deseq2_available": False,
        "warnings": [],
        "limitations": [
            "DESeq2 execution is not available until R, Rscript, BiocManager, and DESeq2 are installed."
        ],
    }


def _write_mock_results(output_path: str) -> None:
    Path(output_path).write_text(
        "\n".join(
            [
                "gene_id,baseMean,log2FoldChange,lfcSE,stat,pvalue,padj",
                "GeneA,182.5,1.1,0.2,5.5,0.001,0.002",
                "GeneB,16.0,-0.9,0.3,-3.0,0.02,0.04",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_deseq2_requested_but_preflight_not_ready_returns_safe_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "outputs"
    metadata_file, count_matrix_file = _write_inputs(input_root)
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str(input_root))
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    monkeypatch.setattr(
        deseq2_execution.formal_de_preflight,
        "run_deseq2_preflight",
        _not_ready_preflight,
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(
        deseq2_execution,
        "run_command_safely",
        lambda args, timeout_seconds=120: calls.append(args) or CommandResult(args=args, returncode=0),
    )

    with pytest.raises(Deseq2ExecutionError) as exc_info:
        execute_task_deseq2(
            task_id="task_0001",
            metadata_file=metadata_file,
            count_matrix_file=count_matrix_file,
        )

    detail = exc_info.value.to_detail()
    assert exc_info.value.status_code == 501
    assert detail["error_code"] == DESEQ2_PREFLIGHT_NOT_READY
    assert (
        detail["message"]
        == "DESeq2 execution is not available because the preflight check is not ready."
    )
    assert calls == []
    assert not (output_root / "tasks" / "task_0001" / "deseq2_results.csv").exists()
    _assert_no_forbidden_public_fragments(detail)


def test_run_command_safely_uses_list_args_and_shell_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return Completed()

    monkeypatch.setattr(deseq2_execution.formal_de_preflight.subprocess, "run", fake_run)

    result = deseq2_execution.run_command_safely(
        ["Rscript", "--vanilla", "run_deseq2.R"],
        timeout_seconds=15,
    )

    assert result.returncode == 0
    assert calls[0]["args"] == ["Rscript", "--vanilla", "run_deseq2.R"]
    assert isinstance(calls[0]["args"], list)
    assert calls[0]["kwargs"]["shell"] is False
    assert calls[0]["kwargs"]["timeout"] == 15


def test_successful_mocked_deseq2_execution_writes_outputs_and_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "outputs"
    metadata_file, count_matrix_file = _write_inputs(input_root)
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str(input_root))
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    monkeypatch.setattr(
        deseq2_execution.formal_de_preflight,
        "run_deseq2_preflight",
        _ready_preflight,
    )

    def fake_run(args: list[str], timeout_seconds: int = 120) -> CommandResult:
        _write_mock_results(args[-1])
        return CommandResult(args=args, returncode=0)

    monkeypatch.setattr(deseq2_execution, "run_command_safely", fake_run)

    result = execute_task_deseq2(
        task_id="task_0002",
        metadata_file=metadata_file,
        count_matrix_file=count_matrix_file,
        project_name="demo_bulk_rnaseq",
        omics_type="bulk_rnaseq",
    )

    output_dir = output_root / "tasks" / "task_0002"
    assert result.status == "deseq2_analysis_completed"
    assert (output_dir / "deseq2_results.csv").is_file()
    assert (output_dir / "deseq2_interpretation_summary.json").is_file()
    assert (output_dir / "deseq2_summary.json").is_file()
    assert (output_dir / "deseq2_run_manifest.json").is_file()
    assert (output_dir / "report.md").is_file()

    summary = json.loads((output_dir / "deseq2_summary.json").read_text(encoding="utf-8"))
    assert summary["analysis_method"] == "deseq2"
    assert summary["formal_de_method"] == "deseq2"
    assert summary["formal_de_ready"] is True
    assert summary["statistical_test_performed"] is True
    assert summary["pvalue_available"] is True
    assert summary["adjusted_pvalue_available"] is True
    assert summary["external_tools_called"] is True
    assert summary["interpretation_summary_file"] == "deseq2_interpretation_summary.json"
    assert summary["default_padj_threshold"] == 0.05
    assert summary["default_abs_log2fc_threshold"] == 1.0
    assert summary["genes_passing_default_reporting_filter"] == 1
    assert summary["top_genes_available"] is True
    assert (
        summary["interpretation_boundary"]
        == "Statistical significance does not automatically imply biological significance."
    )

    interpretation = json.loads(
        (output_dir / "deseq2_interpretation_summary.json").read_text(encoding="utf-8")
    )
    assert interpretation["threshold_summary"][
        "genes_passing_default_reporting_filter"
    ] == 1
    assert interpretation["summary"]["padj_threshold"] == 0.05

    manifest = json.loads(
        (output_dir / "deseq2_run_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["command_invoked_safely"] is True
    assert manifest["shell_used"] is False
    assert manifest["package_installation_attempted"] is False
    assert manifest["output_files"] == [
        "tasks/task_0002/deseq2_results.csv",
        "tasks/task_0002/deseq2_interpretation_summary.json",
        "tasks/task_0002/deseq2_summary.json",
        "tasks/task_0002/deseq2_run_manifest.json",
        "tasks/task_0002/report.md",
    ]
    _assert_no_forbidden_public_fragments(interpretation)
    _assert_no_forbidden_public_fragments(summary)
    _assert_no_forbidden_public_fragments(manifest)


def test_failed_rscript_error_is_sanitized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "outputs"
    metadata_file, count_matrix_file = _write_inputs(input_root)
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str(input_root))
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    monkeypatch.setattr(
        deseq2_execution.formal_de_preflight,
        "run_deseq2_preflight",
        _ready_preflight,
    )
    monkeypatch.setattr(
        deseq2_execution,
        "run_command_safely",
        lambda args, timeout_seconds=120: CommandResult(
            args=args,
            returncode=1,
            stderr=r"D:\private\token.txt /home/user/password traceback secret",
        ),
    )

    with pytest.raises(Deseq2ExecutionError) as exc_info:
        execute_task_deseq2(
            task_id="task_0003",
            metadata_file=metadata_file,
            count_matrix_file=count_matrix_file,
        )

    detail = exc_info.value.to_detail()
    assert detail["error_code"] == "DESEQ2_EXECUTION_FAILED"
    _assert_no_forbidden_public_fragments(detail)
