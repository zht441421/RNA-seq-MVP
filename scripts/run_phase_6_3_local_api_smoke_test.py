from __future__ import annotations

import csv
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_SOURCE_ROOT = PROJECT_ROOT / "data" / "demo" / "rnaseq_minimal"
DEMO_METADATA_FILE = "rnaseq_minimal/metadata.csv"
DEMO_COUNT_MATRIX_FILE = "rnaseq_minimal/counts.csv"
DEFAULT_PORT = 8765
STARTUP_TIMEOUT_SECONDS = 15.0
REQUEST_TIMEOUT_SECONDS = 10.0
CONTRAST_DIRECTION = "treatment_vs_control"
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
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
_UNC_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![\\])\\{2,}[^\\/\s\"']+[\\/][^\\/\s\"']+"
)
_POSIX_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9:])/(?!task(?:/|\b)|health\b)[A-Za-z0-9._~/-]+"
)
_OTHER_LOCAL_ROOT_RE = re.compile(
    r"/(?:private/)?(?:tmp|var/(?:tmp|folders)|users|root|workspace|opt|srv)/",
    re.IGNORECASE,
)
_HTTP = build_opener(ProxyHandler({}))


class SmokeTestFailure(RuntimeError):
    """Deterministic, public-safe failure raised by the local smoke test."""


def main() -> int:
    try:
        run_smoke_test()
    except KeyboardInterrupt:
        print("Phase 6.3 local API smoke test failed: interrupted")
        return 1
    except SmokeTestFailure as exc:
        print(f"Phase 6.3 local API smoke test failed: {exc}")
        return 1
    except Exception:
        print("Phase 6.3 local API smoke test failed: unexpected local validation failure")
        return 1

    print("Phase 6.3 local API smoke test passed")
    print("health verified")
    print("task created")
    print("inputs registered")
    print("run completed")
    print("status verified")
    print("artifacts verified")
    print("coze summary verified")
    print("downloads verified")
    return 0


def run_smoke_test() -> None:
    port = _configured_port()
    _require_port_available(port)

    with tempfile.TemporaryDirectory(prefix="bioinfo_phase_6_3_") as temp_dir:
        state_root = Path(temp_dir)
        input_root = state_root / "inputs"
        output_root = state_root / "outputs"
        task_store_path = state_root / "state" / "tasks.sqlite3"
        _copy_demo_inputs(input_root)
        output_root.mkdir(parents=True, exist_ok=True)
        task_store_path.parent.mkdir(parents=True, exist_ok=True)

        server_environment = os.environ.copy()
        for environment_name in list(server_environment):
            normalized_name = environment_name.upper()
            if normalized_name == "WEB_CONCURRENCY" or normalized_name.startswith(
                "UVICORN_"
            ):
                server_environment.pop(environment_name, None)
        server_environment.update(
            {
                "BIOINFO_INPUT_ROOT": str(input_root),
                "BIOINFO_OUTPUT_ROOT": str(output_root),
                "BIOINFO_TASK_STORE_PATH": str(task_store_path),
                "PYTHONUNBUFFERED": "1",
            }
        )

        server: subprocess.Popen[str] | None = None
        try:
            server = _start_server(port, server_environment)
            base_url = f"http://127.0.0.1:{port}"
            health = _wait_for_health(server, base_url)
            _validate_health(health)
            _exercise_task_lifecycle(base_url)
        finally:
            _stop_server(server)


def _exercise_task_lifecycle(base_url: str) -> None:
    create_body = _request_json(
        base_url,
        "POST",
        "/task/create",
        payload={},
        action="task creation",
    )
    task_id = create_body.get("task_id")
    _require(isinstance(task_id, str) and bool(task_id), "task creation response was invalid")
    _require(create_body.get("status") == "created", "task was not created")

    metadata_registration = _request_json(
        base_url,
        "POST",
        f"/task/{task_id}/inputs/register",
        payload={
            "input_role": "metadata",
            "source_relative_path": DEMO_METADATA_FILE,
        },
        action="metadata input registration",
    )
    _validate_registration(
        metadata_registration,
        task_id=task_id,
        input_role="metadata",
        relative_path=DEMO_METADATA_FILE,
        next_required_inputs=["count_matrix"],
    )

    count_registration = _request_json(
        base_url,
        "POST",
        f"/task/{task_id}/inputs/register",
        payload={
            "input_role": "count_matrix",
            "source_relative_path": DEMO_COUNT_MATRIX_FILE,
        },
        action="count matrix input registration",
    )
    _validate_registration(
        count_registration,
        task_id=task_id,
        input_role="count_matrix",
        relative_path=DEMO_COUNT_MATRIX_FILE,
        next_required_inputs=[],
    )

    # The existing lifecycle guard requires these preparation states before run.
    plan_body = _request_json(
        base_url,
        "POST",
        "/task/plan",
        payload=_plan_payload(task_id),
        action="analysis planning",
    )
    _require(plan_body.get("status") == "planned", "analysis planning did not complete")

    qc_body = _request_json(
        base_url,
        "POST",
        "/task/qc",
        payload=_qc_payload(task_id),
        action="QC planning",
    )
    _require(qc_body.get("status") == "qc_planned", "QC planning did not complete")

    run_body = _request_json(
        base_url,
        "POST",
        "/task/run",
        payload=_run_payload(task_id),
        action="minimal workflow run",
    )
    _require(
        run_body.get("status") == "minimal_analysis_completed",
        "minimal workflow did not complete",
    )
    _require(run_body.get("task_id") == task_id, "run response task did not match")

    status_body = _request_json(
        base_url,
        "GET",
        f"/task/{task_id}/status",
        action="task status",
    )
    _require(status_body.get("task_id") == task_id, "status response task did not match")
    _require(
        status_body.get("status") == "run_placeholder_ready",
        "task status did not record run completion",
    )

    artifacts_body = _request_json(
        base_url,
        "GET",
        f"/task/{task_id}/artifacts",
        action="artifact listing",
    )
    _validate_artifacts(artifacts_body, task_id)

    coze_summary = _request_json(
        base_url,
        "GET",
        f"/task/{task_id}/coze-summary",
        action="Coze summary",
    )
    _validate_coze_summary(coze_summary, task_id)

    download_links = coze_summary.get("download_links")
    _require(isinstance(download_links, dict), "summary download links were missing")
    report_path = download_links.get("report.md")
    csv_path = download_links.get("differential_expression_results.csv")
    _require(isinstance(report_path, str), "report download link was missing")
    _require(isinstance(csv_path, str), "CSV download link was missing")

    report_text = _request_text(
        base_url,
        "GET",
        report_path,
        action="report download",
    )
    _validate_report_download(report_text)

    csv_text = _request_text(
        base_url,
        "GET",
        csv_path,
        action="CSV artifact download",
    )
    _validate_csv_download(csv_text)


def _plan_payload(task_id: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "project_name": "phase_6_3_local_api_smoke_test",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "group_column": "condition",
        "contrast": CONTRAST_DIRECTION,
    }


def _qc_payload(task_id: str) -> dict[str, Any]:
    return {
        **_plan_payload(task_id),
        "metadata_file": DEMO_METADATA_FILE,
        "count_matrix_file": DEMO_COUNT_MATRIX_FILE,
        "sample_id_column": "sample_id",
    }


def _run_payload(task_id: str) -> dict[str, Any]:
    return {
        **_plan_payload(task_id),
        "execution_mode": "minimal_real",
        "analysis_method": "minimal_cpm_log2fc",
        "contrast_column": "condition",
        "contrast_numerator": "treatment",
        "contrast_denominator": "control",
    }


def _validate_health(body: dict[str, Any]) -> None:
    _require(body.get("status") == "ok", "health status was not ready")
    _require(
        body.get("service") == "bioinformatics-agent-backend",
        "health service identity did not match",
    )


def _validate_registration(
    body: dict[str, Any],
    *,
    task_id: str,
    input_role: str,
    relative_path: str,
    next_required_inputs: list[str],
) -> None:
    _require(body.get("task_id") == task_id, "input registration task did not match")
    _require(body.get("input_role") == input_role, "input registration role did not match")
    _require(
        body.get("safe_relative_path") == relative_path,
        "input registration path did not match",
    )
    _require(body.get("registered") is True, "input was not registered")
    _require(
        body.get("next_required_inputs") == next_required_inputs,
        "input registration readiness did not match",
    )


def _validate_artifacts(body: dict[str, Any], task_id: str) -> None:
    artifacts = body.get("artifacts")
    _require(isinstance(artifacts, list), "artifact listing was missing")
    names = [artifact.get("name") for artifact in artifacts if isinstance(artifact, dict)]
    _require(names == EXPECTED_ARTIFACTS, "artifact listing did not match expected files")

    for artifact in artifacts:
        _require(isinstance(artifact, dict), "artifact entry was invalid")
        artifact_name = artifact.get("name")
        _require(artifact.get("available") is True, "an expected artifact was unavailable")
        _require(
            artifact.get("path") == f"tasks/{task_id}/{artifact_name}",
            "artifact path was not a safe task-relative path",
        )


def _validate_coze_summary(body: dict[str, Any], task_id: str) -> None:
    _require(body.get("task_id") == task_id, "summary task did not match")
    _require(body.get("safe_to_present") is True, "summary was not safe to present")
    _require(
        body.get("analysis_method") == "minimal_cpm_log2fc",
        "summary analysis method did not match",
    )
    _require(
        body.get("registered_inputs")
        == {
            "count_matrix": DEMO_COUNT_MATRIX_FILE,
            "metadata": DEMO_METADATA_FILE,
        },
        "summary registered inputs did not match",
    )

    contrast = body.get("contrast")
    _require(isinstance(contrast, dict), "summary contrast was missing")
    _require(contrast.get("contrast_column") == "condition", "contrast column did not match")
    _require(contrast.get("contrast_numerator") == "treatment", "contrast numerator did not match")
    _require(contrast.get("contrast_denominator") == "control", "contrast denominator did not match")
    _require(contrast.get("direction") == CONTRAST_DIRECTION, "contrast direction did not match")
    _require(contrast.get("contrast_source") == "explicit", "contrast source was not explicit")
    _require(contrast.get("inferred") is False, "contrast was unexpectedly inferred")
    _require(
        body.get("positive_log2fc_interpretation")
        == "Higher in treatment relative to control",
        "positive direction interpretation did not match",
    )
    _require(
        body.get("negative_log2fc_interpretation")
        == "Lower in treatment relative to control",
        "negative direction interpretation did not match",
    )

    download_links = body.get("download_links")
    _require(isinstance(download_links, dict) and bool(download_links), "summary download links were missing")
    for artifact_name, download_path in download_links.items():
        _validate_relative_download_path(download_path, task_id, str(artifact_name))

    result_files = body.get("result_files")
    _require(isinstance(result_files, list) and bool(result_files), "summary result files were missing")
    for result_file in result_files:
        _require(isinstance(result_file, dict), "summary result file entry was invalid")
        artifact_name = str(result_file.get("artifact_name") or "")
        _require(bool(artifact_name), "summary result file name was missing")
        _require(result_file.get("available") is True, "summary result file was unavailable")
        _validate_relative_download_path(
            result_file.get("download_url"),
            task_id,
            artifact_name,
        )


def _validate_relative_download_path(value: object, task_id: str, artifact_name: str) -> None:
    _require(isinstance(value, str), "artifact download link was invalid")
    parsed = urlsplit(value)
    _require(not parsed.scheme and not parsed.netloc, "artifact download link was not relative")
    _require(not parsed.query and not parsed.fragment, "artifact download link was not canonical")
    _require(
        parsed.path == f"/task/{task_id}/artifacts/{artifact_name}/download",
        "artifact download link did not match its task artifact",
    )


def _validate_report_download(report_text: str) -> None:
    lowered = report_text.lower()
    for expected_text in (
        "minimal bulk rna-seq mvp report",
        "contrast direction",
        CONTRAST_DIRECTION,
        "higher in treatment relative to control",
        "no formal statistical test",
    ):
        _require(expected_text in lowered, "report download content did not match")


def _validate_csv_download(csv_text: str) -> None:
    reader = csv.DictReader(StringIO(csv_text))
    rows = list(reader)
    _require(bool(rows), "downloaded CSV contained no rows")
    _require(
        "contrast_direction" in (reader.fieldnames or []),
        "downloaded CSV contrast column was missing",
    )
    _require(
        any(row.get("contrast_direction") == CONTRAST_DIRECTION for row in rows),
        "downloaded CSV contrast direction did not match",
    )


def _request_json(
    base_url: str,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    action: str,
) -> dict[str, Any]:
    response_text = _request_text(
        base_url,
        method,
        path,
        payload=payload,
        action=action,
    )
    try:
        body = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise SmokeTestFailure(f"{action} returned invalid JSON") from exc
    _require(isinstance(body, dict), f"{action} returned an invalid response")
    return body


def _request_text(
    base_url: str,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    action: str,
) -> str:
    data = None
    headers = {"Accept": "application/json, text/plain, text/csv, text/markdown"}
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(
        f"{base_url}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with _HTTP.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            status = response.getcode()
            response_bytes = response.read()
    except HTTPError as exc:
        response_bytes = exc.read()
        if response_bytes:
            _assert_safe_public_text(_decode_response(response_bytes, action))
        raise SmokeTestFailure(f"{action} returned an unexpected HTTP status") from None
    except (URLError, TimeoutError, OSError):
        raise SmokeTestFailure(f"{action} request could not reach the local server") from None

    _require(status == 200, f"{action} returned an unexpected HTTP status")
    response_text = _decode_response(response_bytes, action)
    _assert_safe_public_text(response_text)
    return response_text


def _wait_for_health(
    server: subprocess.Popen[str],
    base_url: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise SmokeTestFailure("local server exited before health verification")

        request = Request(f"{base_url}/health", headers={"Accept": "application/json"})
        try:
            with _HTTP.open(request, timeout=0.5) as response:
                if response.getcode() != 200:
                    time.sleep(0.1)
                    continue
                response_bytes = response.read()
        except (HTTPError, URLError, TimeoutError, OSError):
            time.sleep(0.1)
            continue

        response_text = _decode_response(response_bytes, "health check")
        _assert_safe_public_text(response_text)
        try:
            body = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise SmokeTestFailure("health check returned invalid JSON") from exc
        _require(isinstance(body, dict), "health check returned an invalid response")
        if server.poll() is not None:
            raise SmokeTestFailure("local server exited during health verification")
        return body

    raise SmokeTestFailure("local server did not become healthy before the startup timeout")


def _start_server(
    port: int,
    environment: dict[str, str],
) -> subprocess.Popen[str]:
    try:
        return subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--workers",
                "1",
                "--log-level",
                "warning",
                "--no-access-log",
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError:
        raise SmokeTestFailure("local server process could not be started") from None


def _stop_server(server: subprocess.Popen[str] | None) -> None:
    if server is None:
        return

    if server.poll() is None:
        try:
            server.terminate()
            server.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            if server.poll() is None:
                try:
                    server.kill()
                    server.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    pass

    if server.poll() is None:
        raise SmokeTestFailure("local server process could not be terminated")


def _copy_demo_inputs(input_root: Path) -> None:
    source_files = [
        DEMO_SOURCE_ROOT / "metadata.csv",
        DEMO_SOURCE_ROOT / "counts.csv",
    ]
    _require(all(path.is_file() for path in source_files), "bundled demo input was missing")
    target_root = input_root / "rnaseq_minimal"
    target_root.mkdir(parents=True, exist_ok=True)
    for source_file in source_files:
        shutil.copy2(source_file, target_root / source_file.name)


def _configured_port() -> int:
    configured = os.environ.get("BIOINFO_SMOKE_TEST_PORT", str(DEFAULT_PORT)).strip()
    try:
        port = int(configured)
    except ValueError:
        raise SmokeTestFailure("configured local port was invalid") from None
    _require(1 <= port <= 65535, "configured local port was invalid")
    return port


def _require_port_available(port: int) -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))
    except OSError:
        raise SmokeTestFailure("configured local port was unavailable") from None


def _decode_response(response_bytes: bytes, action: str) -> str:
    try:
        return response_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SmokeTestFailure(f"{action} returned non-text content") from exc


def _assert_safe_public_text(value: str) -> None:
    lowered = value.lower()
    if any(fragment in lowered for fragment in FORBIDDEN_PUBLIC_FRAGMENTS):
        raise SmokeTestFailure("public response safety check failed")
    if (
        _WINDOWS_ABSOLUTE_PATH_RE.search(value)
        or _UNC_ABSOLUTE_PATH_RE.search(value)
        or _POSIX_ABSOLUTE_PATH_RE.search(value)
        or _OTHER_LOCAL_ROOT_RE.search(value)
    ):
        raise SmokeTestFailure("public response safety check failed")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeTestFailure(message)


if __name__ == "__main__":
    raise SystemExit(main())
