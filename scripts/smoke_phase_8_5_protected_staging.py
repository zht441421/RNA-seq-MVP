from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    Request,
    build_opener,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "https://127.0.0.1:8443"
DEFAULT_HTTP_URL = "http://127.0.0.1:8080"
DEFAULT_SECRET_FILE = ROOT / ".staging-secrets/api_key.txt"
DEFAULT_STATE_FILE = ROOT / ".staging-runtime/phase-8-5-smoke-state.json"
METADATA_FILE = "rnaseq_minimal/metadata.csv"
COUNT_MATRIX_FILE = "rnaseq_minimal/counts.csv"
FORBIDDEN_RESPONSE_PATTERNS = (
    re.compile(r"[A-Za-z]:[\\/]"),
    re.compile(r"file://", re.IGNORECASE),
    re.compile(r"/(?:home|mnt|users|private|tmp|var|root|workspace)/", re.IGNORECASE),
    re.compile(r"traceback", re.IGNORECASE),
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class SmokeFailure(RuntimeError):
    pass


class LocalStagingClient:
    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" or parsed.hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise SmokeFailure("Smoke test is restricted to a local HTTPS staging URL")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        self.opener = build_opener(HTTPSHandler(context=context), NoRedirect())

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict | None = None,
        expected: set[int] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        data = None
        headers = {"Accept": "application/json, text/plain, text/csv, text/markdown"}
        if self.api_key is not None:
            headers["X-Bioinfo-API-Key"] = self.api_key
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            self.base_url + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=15) as response:
                status = response.getcode()
                response_headers = {key.lower(): value for key, value in response.headers.items()}
                body = response.read()
        except HTTPError as exc:
            status = exc.code
            response_headers = {key.lower(): value for key, value in exc.headers.items()}
            body = exc.read()
        except (URLError, TimeoutError, OSError):
            raise SmokeFailure("Local staging service could not be reached") from None
        _assert_safe_response(body, self.api_key)
        expected_statuses = expected or {200}
        if status not in expected_statuses:
            raise SmokeFailure(f"Unexpected HTTP status for {method} {path}: {status}")
        if "x-request-id" not in response_headers:
            raise SmokeFailure(f"Request ID missing for {method} {path}")
        return status, response_headers, body

    def json(
        self,
        method: str,
        path: str,
        *,
        payload: dict | None = None,
        expected: set[int] | None = None,
    ) -> dict:
        _, _, body = self.request(method, path, payload=payload, expected=expected)
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise SmokeFailure(f"Invalid JSON response for {method} {path}") from None
        if not isinstance(value, dict):
            raise SmokeFailure(f"Non-object JSON response for {method} {path}")
        return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify local protected Phase 8.5 staging.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--http-url", default=DEFAULT_HTTP_URL)
    parser.add_argument("--secret-file", type=Path, default=DEFAULT_SECRET_FILE)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    args = parser.parse_args()
    try:
        result = run_smoke(
            base_url=args.base_url,
            http_url=args.http_url,
            secret_file=args.secret_file,
            state_file=args.state_file,
        )
    except SmokeFailure as exc:
        print(f"Phase 8.5 protected staging smoke test failed: {exc}")
        return 1
    print("Phase 8.5 protected staging smoke test passed")
    print(json.dumps(result, sort_keys=True))
    return 0


def run_smoke(
    *,
    base_url: str,
    http_url: str,
    secret_file: Path,
    state_file: Path,
) -> dict:
    api_key = _read_api_key(secret_file)
    valid = LocalStagingClient(base_url, api_key)
    anonymous = LocalStagingClient(base_url)
    invalid = LocalStagingClient(base_url, "invalid-local-staging-key")

    health = anonymous.json("GET", "/health")
    if health.get("status") != "ok":
        raise SmokeFailure("Health response was not ready")
    _verify_plain_http_redirect(http_url)
    anonymous.json("POST", "/task/create", payload={}, expected={401})
    invalid.json("POST", "/task/create", payload={}, expected={401})

    previous_checked = _verify_previous_state(valid, state_file)
    task_id = valid.json("POST", "/task/create", payload={})["task_id"]
    for role, path in (("metadata", METADATA_FILE), ("count_matrix", COUNT_MATRIX_FILE)):
        registered = valid.json(
            "POST",
            f"/task/{quote(task_id, safe='')}/inputs/register",
            payload={"input_role": role, "source_relative_path": path},
        )
        if registered.get("safe_relative_path") != path:
            raise SmokeFailure("Input registration did not preserve its safe reference")

    validation = valid.json(
        "POST",
        "/task/validate-inputs",
        payload={"metadata_file": METADATA_FILE, "count_matrix_file": COUNT_MATRIX_FILE},
    )
    if validation.get("valid") is not True:
        raise SmokeFailure("Reference fixture validation failed")

    plan = _plan_payload(task_id)
    valid.json("POST", "/task/plan", payload=plan)
    valid.json(
        "POST",
        "/task/qc",
        payload={
            **plan,
            "metadata_file": METADATA_FILE,
            "count_matrix_file": COUNT_MATRIX_FILE,
            "sample_id_column": "sample_id",
        },
    )
    run = valid.json(
        "POST",
        "/task/run",
        payload={
            **plan,
            "execution_mode": "minimal_real",
            "analysis_method": "minimal_cpm_log2fc",
            "metadata_file": METADATA_FILE,
            "count_matrix_file": COUNT_MATRIX_FILE,
            "contrast_column": "condition",
            "contrast_numerator": "treatment",
            "contrast_denominator": "control",
        },
    )
    if run.get("status") != "minimal_analysis_completed":
        raise SmokeFailure("Minimal staging analysis did not complete")

    status = valid.json("GET", f"/task/{quote(task_id, safe='')}/status")
    summary = valid.json("GET", f"/task/{quote(task_id, safe='')}/coze-summary")
    artifacts = valid.json("GET", f"/task/{quote(task_id, safe='')}/artifacts")
    audit = valid.json("GET", f"/task/{quote(task_id, safe='')}/audit")
    _verify_summary(summary)
    if "minimal_rnaseq_executed" not in {
        event.get("event_type") for event in audit.get("events", [])
    }:
        raise SmokeFailure("Execution audit event was not recorded")

    artifact_by_name = {
        artifact.get("name"): artifact
        for artifact in artifacts.get("artifacts", [])
        if isinstance(artifact, dict)
    }
    for artifact_name in ("report.md", "qc_summary.json"):
        if artifact_by_name.get(artifact_name, {}).get("available") is not True:
            raise SmokeFailure(f"Required artifact is unavailable: {artifact_name}")
    _, _, report = valid.request(
        "GET", f"/task/{quote(task_id, safe='')}/artifacts/report.md/download"
    )
    _, _, qc_bytes = valid.request(
        "GET", f"/task/{quote(task_id, safe='')}/artifacts/qc_summary.json/download"
    )
    if b"exploratory" not in report.lower():
        raise SmokeFailure("Downloaded report lost its exploratory boundary")
    try:
        qc_summary = json.loads(qc_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SmokeFailure("Downloaded QC summary was invalid") from None

    valid.request(
        "GET",
        f"/task/{quote(task_id, safe='')}/artifacts/%2E%2E%2Freport.md/download",
        expected={400, 404},
    )
    incomplete_task_id = valid.json("POST", "/task/create", payload={})["task_id"]
    valid.request(
        "GET",
        f"/task/{quote(incomplete_task_id, safe='')}/artifacts/report.md/download",
        expected={400, 404},
    )

    preflight = valid.json("GET", "/task/formal-de/preflight")
    deseq2_ready = preflight.get("ready") is True
    _verify_golden(
        summary=summary,
        artifacts=artifacts,
        qc_summary=qc_summary,
        terminal_status=status.get("status"),
        deseq2_ready=deseq2_ready,
    )

    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {
                "completed_task_id": task_id,
                "incomplete_task_id": incomplete_task_id,
                "artifact_name": "report.md",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "completed": True,
        "previous_persistence_checked": previous_checked,
        "task_id": task_id,
        "incomplete_task_id": incomplete_task_id,
        "golden_result": "passed",
        "deseq2_ready": deseq2_ready,
        "remote_deployment": False,
        "coze_integration": False,
    }


def _verify_previous_state(client: LocalStagingClient, state_file: Path) -> bool:
    if not state_file.is_file():
        return False
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise SmokeFailure("Previous smoke state was invalid") from None
    completed = str(state.get("completed_task_id") or "")
    incomplete = str(state.get("incomplete_task_id") or "")
    artifact = str(state.get("artifact_name") or "")
    if not completed or not incomplete or PurePosixPath(artifact).name != artifact:
        raise SmokeFailure("Previous smoke state was incomplete")
    status = client.json("GET", f"/task/{quote(completed, safe='')}/status")
    if status.get("status") != "run_placeholder_ready":
        raise SmokeFailure("Completed task metadata did not persist across restart")
    client.request(
        "GET",
        f"/task/{quote(completed, safe='')}/artifacts/{quote(artifact, safe='')}/download",
    )
    audit = client.json("GET", f"/task/{quote(completed, safe='')}/audit")
    if not audit.get("events"):
        raise SmokeFailure("Audit history did not persist across restart")
    incomplete_status = client.json("GET", f"/task/{quote(incomplete, safe='')}/status")
    if incomplete_status.get("status") != "created":
        raise SmokeFailure("Incomplete task state did not persist as created")
    return True


def _verify_summary(summary: dict) -> None:
    required = {
        "warnings",
        "limitations",
        "reliability_information",
        "interpretation_boundary",
        "artifact_references",
    }
    if not required.issubset(summary):
        raise SmokeFailure("Safe summary fields were missing")
    if summary.get("analysis_method") != "minimal_cpm_log2fc":
        raise SmokeFailure("Unexpected staging analysis method")
    if summary.get("statistical_test_performed") is not False:
        raise SmokeFailure("Minimal staging workflow claimed a statistical test")
    if summary.get("pvalue_available") is not False:
        raise SmokeFailure("Minimal staging workflow claimed p-values")
    if summary.get("adjusted_pvalue_available") is not False:
        raise SmokeFailure("Minimal staging workflow claimed adjusted p-values")
    if "exploratory" not in str(summary.get("interpretation_boundary") or "").lower():
        raise SmokeFailure("Summary lost its exploratory interpretation boundary")


def _verify_golden(
    *,
    summary: dict,
    artifacts: dict,
    qc_summary: dict,
    terminal_status: object,
    deseq2_ready: bool,
) -> None:
    sys.path.insert(0, str(ROOT))
    from backend.app.services.reference_validation import (
        compare_golden_result,
        load_json_object,
    )

    golden = load_json_object(
        ROOT
        / "docs/reference-datasets/golden-results/phase-8-4-rnaseq-minimal-synthetic-v1.json"
    )
    observed = {
        "analysis_method": summary.get("analysis_method"),
        "comparison_direction": (summary.get("contrast") or {}).get("direction"),
        "input_sample_count": qc_summary.get("sample_count"),
        "input_gene_count": qc_summary.get("gene_count"),
        "terminal_task_status": terminal_status,
        "statistical_test_performed": summary.get("statistical_test_performed"),
        "pvalue_available": summary.get("pvalue_available"),
        "adjusted_pvalue_available": summary.get("adjusted_pvalue_available"),
        "scientific_conclusion_generated": False,
        "reliability_information": summary.get("reliability_information"),
        "warnings": summary.get("warnings"),
        "limitations": summary.get("limitations"),
        "interpretation_boundary": summary.get("interpretation_boundary"),
        "summary_fields": sorted(summary),
        "artifact_categories": [
            artifact.get("artifact_type")
            for artifact in artifacts.get("artifacts", [])
            if isinstance(artifact, dict)
        ],
        "claims": [],
        "deseq2_execution_state": (
            "available_for_separate_validation" if deseq2_ready else "unavailable"
        ),
    }
    comparison = compare_golden_result(
        observed, golden, environment={"deseq2_ready": deseq2_ready}
    )
    if not comparison["passed"]:
        raise SmokeFailure("Phase 8.4 Golden Result comparison failed")


def _plan_payload(task_id: str) -> dict:
    return {
        "task_id": task_id,
        "project_name": "phase_8_5_local_staging",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }


def _read_api_key(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        raise SmokeFailure("Local staging API key file is unavailable") from None
    if not value:
        raise SmokeFailure("Local staging API key file is empty")
    return value


def _verify_plain_http_redirect(http_url: str) -> None:
    parsed = urlsplit(http_url)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise SmokeFailure("HTTP redirect check is restricted to a local URL")
    opener = build_opener(NoRedirect())
    request = Request(http_url.rstrip("/") + "/health", method="GET")
    try:
        opener.open(request, timeout=5)
    except HTTPError as exc:
        if exc.code != 308:
            raise SmokeFailure("Plain HTTP was not rejected or redirected") from None
        location = str(exc.headers.get("Location") or "")
        if not location.startswith("https://localhost:8443/"):
            raise SmokeFailure("Plain HTTP redirect target was unexpected")
        return
    except (URLError, TimeoutError, OSError):
        raise SmokeFailure("Local plain HTTP redirect endpoint was unavailable") from None
    raise SmokeFailure("Plain HTTP unexpectedly returned success")


def _assert_safe_response(body: bytes, api_key: str | None) -> None:
    text = body.decode("utf-8", errors="replace")
    if api_key and api_key in text:
        raise SmokeFailure("API key appeared in a staging response")
    for pattern in FORBIDDEN_RESPONSE_PATTERNS:
        if pattern.search(text):
            raise SmokeFailure("Unsafe internal detail appeared in a staging response")


if __name__ == "__main__":
    raise SystemExit(main())
