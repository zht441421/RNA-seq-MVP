from __future__ import annotations

import argparse
import json
import os
import re
import shutil
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


DEMO_METADATA_FILE = "deseq2_minimal/metadata.csv"
DEMO_COUNT_MATRIX_FILE = "deseq2_minimal/counts.csv"
EXPECTED_ARTIFACTS = [
    "deseq2_results.csv",
    "deseq2_summary.json",
    "deseq2_run_manifest.json",
    "deseq2_interpretation_summary.json",
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
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"\b[A-Za-z]:[\\/][^\s\"'<>|]+")
_POSIX_ABSOLUTE_PATH_RE = re.compile(r"(?:(?:/home|/mnt)/[^\s\"'<>|]+)")
_FORBIDDEN_WORD_RE = re.compile(r"\b(traceback|token|password|secret)\b", re.IGNORECASE)


class DemoSkipped(Exception):
    def __init__(self, preflight: dict) -> None:
        self.preflight = preflight
        super().__init__("DESeq2 preflight is not ready.")


def run_phase_4_9_demo(
    require_deseq2: bool = False,
    *,
    input_root: Path | None = None,
    output_root: Path | None = None,
) -> int:
    try:
        summary = _run_validation(input_root=input_root, output_root=output_root)
    except DemoSkipped as exc:
        print("Phase 4.9 DESeq2 demo skipped: preflight is not ready")
        print("DESeq2 is unavailable in this environment; no DESeq2 outputs were created.")
        _print_preflight_checks(exc.preflight)
        if require_deseq2:
            print("require_deseq2: true")
            return 2
        return 0
    except Exception as exc:
        print("Phase 4.9 DESeq2 demo validation failed")
        print(f"error: {_sanitize_public_text(exc)}")
        return 1

    print("Phase 4.9 DESeq2 demo validation passed")
    print(f"task_id: {summary['task_id']}")
    print(f"output_dir: {summary['output_dir']}")
    print("artifacts:")
    for artifact_name in summary["artifacts"]:
        print(f"- {artifact_name}")
    print("checks:")
    print("- DESeq2 preflight was ready")
    print("- formal_de_real DESeq2 run completed")
    print("- expected DESeq2 artifacts exist")
    print("- artifacts endpoint listed the expected files")
    print("- report includes interpretation boundaries")
    print("- package installation was not attempted")
    return 0


def main(
    argv: list[str] | None = None,
    *,
    input_root: Path | None = None,
    output_root: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Run the Phase 4.9 synthetic DESeq2 demo validation.",
    )
    parser.add_argument(
        "--require-deseq2",
        action="store_true",
        help="Return a non-zero code when DESeq2 preflight is not ready.",
    )
    args = parser.parse_args(argv)
    return run_phase_4_9_demo(
        require_deseq2=args.require_deseq2,
        input_root=input_root,
        output_root=output_root,
    )


def _run_validation(
    *,
    input_root: Path | None,
    output_root: Path | None,
) -> dict[str, object]:
    input_root = _resolve_root(
        input_root,
        env_name="BIOINFO_INPUT_ROOT",
        default=PROJECT_ROOT / "data" / "demo",
    )
    output_root = _resolve_root(
        output_root,
        env_name="BIOINFO_OUTPUT_ROOT",
        default=PROJECT_ROOT / "data" / "outputs" / "phase_4_9_deseq2_demo",
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

        preflight_response = client.get("/task/formal-de/preflight")
        _require_response(preflight_response, 200, "DESeq2 preflight")
        preflight_body = preflight_response.json()
        _verify_no_forbidden_public_fragments(preflight_body)
        if not preflight_body.get("ready"):
            raise DemoSkipped(preflight_body)

        plan_response = client.post("/task/plan", json=_plan_payload(task_id))
        _require_response(plan_response, 200, "analysis planning")

        qc_response = client.post("/task/qc", json=_qc_payload(task_id))
        _require_response(qc_response, 200, "QC planning")

        artifact_dir = output_root / "tasks" / task_id
        _remove_existing_task_output_dir(artifact_dir, output_root)

        run_response = client.post("/task/run", json=_run_payload(task_id))
        _require_response(run_response, 200, "DESeq2 run")
        run_body = run_response.json()
        _require(
            run_body["status"] == "deseq2_analysis_completed",
            "DESeq2 run did not complete",
        )

        _require(artifact_dir.is_dir(), "task output directory was not created")
        for artifact_name in EXPECTED_ARTIFACTS:
            _require(
                (artifact_dir / artifact_name).is_file(),
                f"missing artifact: {artifact_name}",
            )

        manifest = _read_json(artifact_dir / "deseq2_run_manifest.json")
        _require(
            manifest.get("package_installation_attempted") is False,
            "manifest did not record package installation boundary",
        )

        summary = _read_json(artifact_dir / "deseq2_summary.json")
        _require(
            summary.get("analysis_method") == "deseq2",
            "summary did not record DESeq2 analysis method",
        )
        _require(
            summary.get("statistical_test_performed") is True,
            "summary did not record formal statistical testing",
        )

        _verify_report(artifact_dir / "report.md")

        artifacts_response = client.get(f"/task/{task_id}/artifacts")
        _require_response(artifacts_response, 200, "artifact listing")
        artifacts_body = artifacts_response.json()
        artifact_names = [artifact["name"] for artifact in artifacts_body["artifacts"]]
        _require(
            set(artifact_names) == set(EXPECTED_ARTIFACTS)
            and len(artifact_names) == len(EXPECTED_ARTIFACTS),
            "artifact listing did not match expected DESeq2 files",
        )

        for body in (
            create_response.json(),
            preflight_body,
            plan_response.json(),
            qc_response.json(),
            run_body,
            artifacts_body,
        ):
            _verify_no_forbidden_public_fragments(body)

    return {
        "status": "success",
        "task_id": task_id,
        "output_dir": f"tasks/{task_id}",
        "artifacts": list(EXPECTED_ARTIFACTS),
        "artifact_count": len(EXPECTED_ARTIFACTS),
    }


def _plan_payload(task_id: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "project_name": "phase_4_9_deseq2_demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "group_column": "condition",
        "contrast": "treated_vs_control",
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
        "execution_mode": "formal_de_real",
        "analysis_method": "deseq2",
        "formal_de_method": "deseq2",
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


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_report(path: Path) -> None:
    text = path.read_text(encoding="utf-8").lower()
    for phrase in (
        "deseq2",
        "statistical significance is not the same as biological significance",
        "no go/kegg/gsea",
    ):
        _require(phrase in text, f"report missing boundary: {phrase}")


def _verify_no_forbidden_public_fragments(body: object) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    for fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        _require(fragment not in text, f"public response exposed forbidden text: {fragment}")


def _print_preflight_checks(preflight: dict) -> None:
    checks = preflight.get("checks", {}) if isinstance(preflight, dict) else {}
    print("checks:")
    print(f"- R: {_availability_label(checks.get('r_available'))}")
    print(f"- Rscript: {_availability_label(checks.get('rscript_available'))}")
    print(f"- BiocManager: {_availability_label(checks.get('biocmanager_available'))}")
    print(f"- DESeq2: {_availability_label(checks.get('deseq2_available'))}")


def _availability_label(value: object) -> str:
    return "available" if bool(value) else "unavailable"


def _sanitize_public_text(value: object) -> str:
    text = str(value or "")
    text = _WINDOWS_ABSOLUTE_PATH_RE.sub("[redacted-path]", text)
    text = _POSIX_ABSOLUTE_PATH_RE.sub("[redacted-path]", text)
    return _FORBIDDEN_WORD_RE.sub("redacted", text)


if __name__ == "__main__":
    raise SystemExit(main())
