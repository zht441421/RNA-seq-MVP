from __future__ import annotations

import csv
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
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
    "traceback",
    "token",
    "password",
    "secret",
)
FORBIDDEN_RESULT_FIELDS = ("pvalue", "padj", "qvalue", "significant")


def run_demo(
    *,
    input_root: Path | None = None,
    output_root: Path | None = None,
) -> dict[str, object]:
    input_root = _resolve_root(
        input_root,
        env_name="BIOINFO_INPUT_ROOT",
        default=PROJECT_ROOT / "data" / "demo",
    )
    output_root = _resolve_root(
        output_root,
        env_name="BIOINFO_OUTPUT_ROOT",
        default=PROJECT_ROOT / "data" / "outputs" / "phase_4_4_demo",
    )

    with _temporary_environment(
        {
            "BIOINFO_INPUT_ROOT": str(input_root),
            "BIOINFO_OUTPUT_ROOT": str(output_root),
        }
    ):
        reset_registry()
        client = TestClient(app)
        create_response = client.post("/task/create", json={})
        _require_response(create_response, 200, "task creation")
        task_id = create_response.json()["task_id"]

        plan_response = client.post("/task/plan", json=_plan_payload(task_id))
        _require_response(plan_response, 200, "analysis planning")

        qc_response = client.post("/task/qc", json=_qc_payload(task_id))
        _require_response(qc_response, 200, "QC planning")

        run_response = client.post("/task/run", json=_run_payload(task_id))
        _require_response(run_response, 200, "minimal RNA-seq run")
        run_body = run_response.json()
        _require(
            run_body["status"] == "minimal_analysis_completed",
            "minimal run did not complete",
        )

        artifact_dir = output_root / "tasks" / task_id
        _require(artifact_dir.is_dir(), "task output directory was not created")
        for artifact_name in EXPECTED_ARTIFACTS:
            _require(
                (artifact_dir / artifact_name).is_file(),
                f"missing artifact: {artifact_name}",
            )

        execution_summary = _read_json(artifact_dir / "execution_summary.json")
        _require(
            execution_summary.get("real_execution_performed") is True,
            "execution summary did not record real execution",
        )
        _require(
            execution_summary.get("external_tools_called") is False,
            "execution summary recorded external tool usage",
        )
        _require(
            execution_summary.get("statistical_test_performed") is False,
            "execution summary recorded a statistical test",
        )

        _verify_result_csv(artifact_dir / "differential_expression_results.csv")
        _verify_report(artifact_dir / "report.md")

        artifacts_response = client.get(f"/task/{task_id}/artifacts")
        _require_response(artifacts_response, 200, "artifact listing")
        artifacts_body = artifacts_response.json()
        _require(
            [artifact["name"] for artifact in artifacts_body["artifacts"]]
            == EXPECTED_ARTIFACTS,
            "artifact listing did not match expected files",
        )

        audit_response = client.get(f"/task/{task_id}/audit")
        _require_response(audit_response, 200, "audit listing")
        audit_body = audit_response.json()
        _require(
            any(
                event["event_type"] == "minimal_rnaseq_executed"
                for event in audit_body["events"]
            ),
            "audit did not record minimal RNA-seq execution",
        )

        public_bodies = [
            create_response.json(),
            plan_response.json(),
            qc_response.json(),
            run_body,
            artifacts_body,
            audit_body,
        ]
        for body in public_bodies:
            _verify_no_forbidden_public_fragments(body)

    return {
        "status": "success",
        "task_id": task_id,
        "output_dir": f"tasks/{task_id}",
        "artifacts": list(EXPECTED_ARTIFACTS),
        "artifact_count": len(EXPECTED_ARTIFACTS),
        "audit_events": [
            event["event_type"]
            for event in audit_body["events"]
        ],
    }


def main(
    *,
    input_root: Path | None = None,
    output_root: Path | None = None,
) -> int:
    try:
        summary = run_demo(input_root=input_root, output_root=output_root)
    except Exception as exc:
        print("Phase 4.4 demo validation failed")
        print(f"error: {exc}")
        return 1

    print("Phase 4.4 demo validation passed")
    print(f"task_id: {summary['task_id']}")
    print(f"output_dir: {summary['output_dir']}")
    print("artifacts:")
    for artifact_name in summary["artifacts"]:
        print(f"- {artifact_name}")
    print("checks:")
    print("- minimal run completed")
    print("- expected artifacts exist")
    print("- no external tools were called")
    print("- no formal statistical test was performed")
    print("- public API responses use safe relative paths")
    return 0


def _plan_payload(task_id: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "project_name": "phase_4_4_demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }


def _qc_payload(task_id: str) -> dict[str, object]:
    return {
        **_plan_payload(task_id),
        "metadata_file": DEMO_METADATA_FILE,
        "count_matrix_file": DEMO_COUNT_MATRIX_FILE,
        "sample_id_column": "sample_id",
    }


def _run_payload(task_id: str) -> dict[str, object]:
    return {
        **_plan_payload(task_id),
        "metadata_file": DEMO_METADATA_FILE,
        "count_matrix_file": DEMO_COUNT_MATRIX_FILE,
        "execution_mode": "minimal_real",
    }


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


def _require_response(response: object, expected_status: int, action: str) -> None:
    status_code = getattr(response, "status_code", None)
    _require(
        status_code == expected_status,
        f"{action} returned HTTP {status_code}; expected {expected_status}",
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_result_csv(path: Path) -> None:
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = [fieldname.lower() for fieldname in reader.fieldnames or []]
        rows = list(reader)

    for forbidden_field in FORBIDDEN_RESULT_FIELDS:
        _require(
            forbidden_field not in fieldnames,
            f"unexpected result field: {forbidden_field}",
        )

    text = path.read_text(encoding="utf-8").lower()
    for forbidden_field in FORBIDDEN_RESULT_FIELDS:
        _require(
            forbidden_field not in text,
            f"unexpected result text: {forbidden_field}",
        )
    _require(bool(rows), "result CSV did not contain ranked rows")


def _verify_report(path: Path) -> None:
    text = path.read_text(encoding="utf-8").lower()
    for phrase in (
        "no deseq2, edger, or limma was run",
        "no formal statistical test",
        "no p-values or adjusted p-values",
    ):
        _require(phrase in text, f"report missing boundary: {phrase}")


def _verify_no_forbidden_public_fragments(body: object) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    for fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        _require(fragment not in text, f"public response exposed forbidden text: {fragment}")


if __name__ == "__main__":
    raise SystemExit(main())
