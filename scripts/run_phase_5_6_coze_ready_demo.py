from __future__ import annotations

import csv
import json
import os
import re
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402
from backend.app.services.task_registry import reset_registry  # noqa: E402


DEMO_METADATA_FILE = "rnaseq_minimal/metadata.csv"
DEMO_COUNT_MATRIX_FILE = "rnaseq_minimal/counts.csv"
EXPECTED_ARTIFACTS = [
    "run_manifest.json",
    "execution_summary.json",
    "qc_summary.json",
    "normalized_counts_cpm.csv",
    "differential_expression_results.csv",
    "report.md",
]
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
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"\b[A-Za-z]:[\\/][^\s\"'<>|]+")
_POSIX_ABSOLUTE_PATH_RE = re.compile(r"(?:(?:/home|/mnt)/[^\s\"'<>|]+)")
_FORBIDDEN_WORD_RE = re.compile(r"\b(traceback|token|password|secret)\b", re.IGNORECASE)


def run_demo(
    *,
    input_root: Path | None = None,
    output_root: Path | None = None,
    task_store_path: Path | None = None,
) -> dict[str, object]:
    input_root = _resolve_root(
        input_root,
        env_name="BIOINFO_INPUT_ROOT",
        default=PROJECT_ROOT / "data" / "demo",
    )
    output_root = _resolve_root(
        output_root,
        env_name="BIOINFO_OUTPUT_ROOT",
        default=PROJECT_ROOT / "data" / "outputs" / "phase_5_6_coze_ready_demo",
    )
    task_store_path = _resolve_root(
        task_store_path,
        env_name="BIOINFO_TASK_STORE_PATH",
        default=PROJECT_ROOT / "data" / "state" / "phase_5_6_demo_tasks.sqlite3",
    )

    _require_demo_data(input_root)
    contrast = _infer_demo_contrast(input_root / DEMO_METADATA_FILE)

    with _temporary_environment(
        {
            "BIOINFO_INPUT_ROOT": str(input_root),
            "BIOINFO_OUTPUT_ROOT": str(output_root),
            "BIOINFO_TASK_STORE_PATH": str(task_store_path),
        }
    ):
        reset_registry()
        client = TestClient(app)

        create_response = client.post("/task/create", json={})
        _require_response(create_response, 200, "task creation")
        task_id = create_response.json()["task_id"]

        artifact_dir = output_root / "tasks" / task_id
        _remove_existing_task_output_dir(artifact_dir, output_root)

        metadata_register_response = client.post(
            f"/task/{task_id}/inputs/register",
            json={
                "input_role": "metadata",
                "source_relative_path": DEMO_METADATA_FILE,
            },
        )
        _require_response(metadata_register_response, 200, "metadata input registration")

        count_register_response = client.post(
            f"/task/{task_id}/inputs/register",
            json={
                "input_role": "count_matrix",
                "source_relative_path": DEMO_COUNT_MATRIX_FILE,
            },
        )
        _require_response(count_register_response, 200, "count matrix input registration")

        plan_response = client.post("/task/plan", json=_plan_payload(task_id, contrast))
        _require_response(plan_response, 200, "analysis planning")

        qc_response = client.post("/task/qc", json=_qc_payload(task_id, contrast))
        _require_response(qc_response, 200, "QC planning")

        run_response = client.post("/task/run", json=_run_payload(task_id, contrast))
        _require_response(run_response, 200, "minimal RNA-seq run")
        run_body = run_response.json()
        _require(
            run_body.get("status") == "minimal_analysis_completed",
            "minimal run did not complete",
        )

        status_response = client.get(f"/task/{task_id}/status")
        _require_response(status_response, 200, "task status fetch")
        status_body = status_response.json()
        _require(
            status_body.get("status") == "run_placeholder_ready",
            "task status did not record run completion",
        )

        artifacts_response = client.get(f"/task/{task_id}/artifacts")
        _require_response(artifacts_response, 200, "artifact listing")
        artifacts_body = artifacts_response.json()
        artifact_names = [artifact["name"] for artifact in artifacts_body["artifacts"]]
        _require(
            artifact_names == EXPECTED_ARTIFACTS,
            "artifact listing did not match expected minimal workflow files",
        )

        report_download = client.get(f"/task/{task_id}/artifacts/report.md/download")
        _require_response(report_download, 200, "report download")
        report_text = report_download.text
        _verify_report_download(report_text, contrast)

        csv_download = client.get(
            f"/task/{task_id}/artifacts/differential_expression_results.csv/download"
        )
        _require_response(csv_download, 200, "CSV artifact download")
        _verify_csv_download(csv_download.text, contrast)

        coze_response = client.get(f"/task/{task_id}/coze-summary")
        _require_response(coze_response, 200, "Coze summary")
        coze_summary = coze_response.json()
        _verify_coze_summary(coze_summary, task_id, contrast)

        for body in (
            create_response.json(),
            metadata_register_response.json(),
            count_register_response.json(),
            plan_response.json(),
            qc_response.json(),
            run_body,
            status_body,
            artifacts_body,
            coze_summary,
        ):
            _verify_no_forbidden_public_fragments(body)

        for downloaded_text in (report_text, csv_download.text):
            _verify_no_forbidden_public_fragments(downloaded_text)

    return {
        "status": "success",
        "task_id": task_id,
        "output_dir": f"tasks/{task_id}",
        "state_store": "data/state/phase_5_6_demo_tasks.sqlite3",
        "registered_inputs": [DEMO_METADATA_FILE, DEMO_COUNT_MATRIX_FILE],
        "artifacts": list(EXPECTED_ARTIFACTS),
        "downloaded_artifacts": [
            "report.md",
            "differential_expression_results.csv",
        ],
        "contrast": contrast,
        "coze_safe_to_present": bool(coze_summary.get("safe_to_present")),
    }


def main(
    *,
    input_root: Path | None = None,
    output_root: Path | None = None,
    task_store_path: Path | None = None,
) -> int:
    try:
        summary = run_demo(
            input_root=input_root,
            output_root=output_root,
            task_store_path=task_store_path,
        )
    except Exception as exc:
        print("Phase 5.6 Coze-ready demo validation failed")
        print(f"error: {_sanitize_public_text(exc)}")
        return 1

    print("Phase 5.6 Coze-ready demo validation passed")
    print(f"task_id: {summary['task_id']}")
    print(f"output_dir: {summary['output_dir']}")
    print("checks:")
    print("- task created")
    print("- inputs registered")
    print("- run completed")
    print("- artifacts verified")
    print("- downloads verified")
    print("- coze summary verified")
    print(f"- contrast direction: {summary['contrast']['direction']}")
    print("- public responses are safe for Coze/front-end presentation")
    return 0


def _plan_payload(task_id: str, contrast: dict[str, str]) -> dict[str, object]:
    return {
        "task_id": task_id,
        "project_name": "phase_5_6_coze_ready_demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "group_column": "condition",
        "contrast": contrast["direction"],
    }


def _qc_payload(task_id: str, contrast: dict[str, str]) -> dict[str, object]:
    return {
        **_plan_payload(task_id, contrast),
        "metadata_file": DEMO_METADATA_FILE,
        "count_matrix_file": DEMO_COUNT_MATRIX_FILE,
        "sample_id_column": "sample_id",
    }


def _run_payload(task_id: str, contrast: dict[str, str]) -> dict[str, object]:
    return {
        **_plan_payload(task_id, contrast),
        "execution_mode": "minimal_real",
        "analysis_method": "minimal_cpm_log2fc",
        "contrast_column": "condition",
        "contrast_numerator": contrast["numerator"],
        "contrast_denominator": contrast["denominator"],
    }


def _require_demo_data(input_root: Path) -> None:
    missing = [
        relative_path
        for relative_path in (DEMO_METADATA_FILE, DEMO_COUNT_MATRIX_FILE)
        if not (input_root / relative_path).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            "required demo data is missing: " + ", ".join(missing)
        )


def _infer_demo_contrast(metadata_path: Path) -> dict[str, str]:
    conditions: list[str] = []
    with metadata_path.open("r", encoding="utf-8", newline="") as metadata_file:
        reader = csv.DictReader(metadata_file)
        for row in reader:
            condition = str(row.get("condition") or "").strip()
            if condition and condition not in conditions:
                conditions.append(condition)
    _require(len(conditions) == 2, "demo metadata must contain exactly two conditions")
    denominator, numerator = conditions[0], conditions[1]
    return {
        "column": "condition",
        "numerator": numerator,
        "denominator": denominator,
        "direction": f"{_direction_token(numerator)}_vs_{_direction_token(denominator)}",
        "positive": f"Higher in {numerator} relative to {denominator}",
        "negative": f"Lower in {numerator} relative to {denominator}",
    }


def _verify_report_download(report_text: str, contrast: dict[str, str]) -> None:
    lowered = report_text.lower()
    for phrase in (
        "minimal bulk rna-seq mvp report",
        "contrast direction",
        contrast["direction"].lower(),
        contrast["positive"].lower(),
        "no formal statistical test",
    ):
        _require(phrase in lowered, f"report download missing expected text: {phrase}")


def _verify_csv_download(csv_text: str, contrast: dict[str, str]) -> None:
    reader = csv.DictReader(csv_text.splitlines())
    rows = list(reader)
    _require(bool(rows), "downloaded differential expression CSV had no rows")
    _require(
        "contrast_direction" in (reader.fieldnames or []),
        "downloaded differential expression CSV did not include contrast direction",
    )
    _require(
        any(row.get("contrast_direction") == contrast["direction"] for row in rows),
        "downloaded differential expression CSV did not record the explicit contrast",
    )


def _verify_coze_summary(
    summary: dict,
    task_id: str,
    contrast: dict[str, str],
) -> None:
    for field in (
        "summary_message",
        "result_files",
        "download_links",
        "contrast",
        "positive_log2fc_interpretation",
        "negative_log2fc_interpretation",
        "warnings",
        "limitations",
        "safe_to_present",
    ):
        _require(field in summary, f"Coze summary missing field: {field}")

    _require(summary.get("safe_to_present") is True, "Coze summary is not safe to present")
    _require(
        summary["contrast"]["direction"] == contrast["direction"],
        "Coze summary did not record contrast direction",
    )
    _require(
        summary["positive_log2fc_interpretation"] == contrast["positive"],
        "Coze summary did not record positive log2FC interpretation",
    )
    _require(
        summary["negative_log2fc_interpretation"] == contrast["negative"],
        "Coze summary did not record negative log2FC interpretation",
    )
    _require(
        summary.get("registered_inputs") == {
            "count_matrix": DEMO_COUNT_MATRIX_FILE,
            "metadata": DEMO_METADATA_FILE,
        },
        "Coze summary did not include registered input paths",
    )

    for artifact_name, download_url in summary["download_links"].items():
        _require(
            str(download_url).startswith(f"/task/{task_id}/artifacts/"),
            f"download link is not a relative artifact API path: {artifact_name}",
        )
        _require(
            str(download_url).endswith("/download"),
            f"download link is not a download endpoint path: {artifact_name}",
        )
        _require(
            not str(download_url).startswith(("file://", "http://", "https://")),
            f"download link is not relative: {artifact_name}",
        )


def _resolve_root(path: Path | None, *, env_name: str, default: Path) -> Path:
    if path is not None:
        return path.resolve(strict=False)
    configured = os.environ.get(env_name, "").strip()
    return Path(configured).resolve(strict=False) if configured else default.resolve(strict=False)


@contextmanager
def _temporary_environment(values: dict[str, str]) -> Iterator[None]:
    previous = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, old_value in previous.items():
            if old_value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = old_value


def _remove_existing_task_output_dir(artifact_dir: Path, output_root: Path) -> None:
    resolved_root = output_root.resolve(strict=False)
    resolved_dir = artifact_dir.resolve(strict=False)
    _require(
        _is_relative_to(resolved_dir, resolved_root),
        "task output directory escaped the configured output root",
    )
    if resolved_dir.exists():
        shutil.rmtree(resolved_dir)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _require_response(response: object, expected_status: int, action: str) -> None:
    status_code = getattr(response, "status_code", None)
    _require(
        status_code == expected_status,
        f"{action} returned HTTP {status_code}; expected {expected_status}",
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _verify_no_forbidden_public_fragments(value: object) -> None:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    lowered = text.lower()
    for fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        _require(fragment not in lowered, f"public output exposed forbidden text: {fragment}")


def _direction_token(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "unknown"


def _sanitize_public_text(value: object) -> str:
    text = str(value or "")
    text = _WINDOWS_ABSOLUTE_PATH_RE.sub("[redacted-path]", text)
    text = _POSIX_ABSOLUTE_PATH_RE.sub("[redacted-path]", text)
    text = text.replace("file://", "[redacted-uri]")
    return _FORBIDDEN_WORD_RE.sub("redacted", text)


if __name__ == "__main__":
    raise SystemExit(main())
