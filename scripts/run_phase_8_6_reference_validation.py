from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.reference_validation import compare_golden_result, load_json_object, sha256_file
from scripts.phase_8_6_reference_common import (
    ReferenceDataError,
    prepared_dataset_root,
    public_datasets,
    select_datasets,
)


REPORT_ROOT = ROOT / ".staging-runtime/phase-8-6-validation"
DEFAULT_STAGING_URL = "https://127.0.0.1:8443"
DEFAULT_SECRET = ROOT / ".staging-secrets/api_key.txt"
FORBIDDEN_REPORT_TEXT = (
    "-----begin private key-----",
    "traceback (most recent call last)",
)
WINDOWS_ABSOLUTE_PATH = re.compile(r"(?i)(?<![a-z0-9])[a-z]:[\\\\/]")


@dataclass
class SimpleResponse:
    status_code: int
    headers: dict[str, str]
    content: bytes

    def json(self) -> Any:
        return json.loads(self.content.decode("utf-8"))


class StagingClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ReferenceDataError("Staging validation is restricted to local protected HTTPS.")
        if not api_key:
            raise ReferenceDataError("Protected staging API key is unavailable.")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        self.opener = build_opener(HTTPSHandler(context=context))
        self._wait_until_ready()

    def _wait_until_ready(self) -> None:
        consecutive = 0
        for _ in range(30):
            try:
                response = self.request("GET", "/health")
                consecutive = consecutive + 1 if response.status_code == 200 else 0
                if consecutive >= 2:
                    return
            except ReferenceDataError:
                consecutive = 0
            time.sleep(0.5)
        raise ReferenceDataError("Protected local staging did not become healthy.")

    def request(self, method: str, url: str, **kwargs: Any) -> SimpleResponse:
        headers = {"Accept": "application/json,text/csv,text/markdown", "X-Bioinfo-API-Key": self.api_key}
        body = None
        if "json" in kwargs:
            body = json.dumps(kwargs["json"], separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(self.base_url + url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=30) as response:
                return SimpleResponse(
                    response.getcode(),
                    {key.lower(): value for key, value in response.headers.items()},
                    response.read(),
                )
        except HTTPError as exc:
            return SimpleResponse(
                exc.code,
                {key.lower(): value for key, value in exc.headers.items()},
                exc.read(),
            )
        except (URLError, TimeoutError, OSError) as exc:
            raise ReferenceDataError("Protected local staging could not be reached.") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 8.6 real-public reference validation.")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dataset")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--mode", choices=("local", "staging"), default="local")
    parser.add_argument("--base-url", default=DEFAULT_STAGING_URL)
    parser.add_argument("--secret-file", type=Path, default=DEFAULT_SECRET)
    args = parser.parse_args()
    if args.list:
        for dataset in public_datasets():
            print(f"{dataset['dataset_id']}\t{dataset['contrast']['direction']}")
        return 0
    try:
        selected = select_datasets(args.dataset, all_datasets=args.all)
        client = _client_for_mode(args.mode, args.base_url, args.secret_file)
        results = [validate_dataset(dataset, client=client, mode=args.mode) for dataset in selected]
        report = _write_aggregate_report(results, args.mode)
    except ReferenceDataError as exc:
        print(json.dumps({
            "passed": False,
            "error": {
                "code": "REFERENCE_VALIDATION_FAILED",
                "message": str(exc),
            },
            "scientific_conclusion_generated": False,
        }, indent=2, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


def _client_for_mode(mode: str, base_url: str, secret_file: Path):
    if mode == "staging":
        try:
            api_key = secret_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ReferenceDataError("Protected staging secret file is unavailable.") from exc
        return StagingClient(base_url, api_key)

    prepared_root = ROOT / ".reference-data/prepared"
    os.environ["BIOINFO_INPUT_ROOT"] = str(prepared_root.resolve())
    os.environ["BIOINFO_OUTPUT_ROOT"] = str((REPORT_ROOT / "local-runtime-artifacts").resolve())
    os.environ["BIOINFO_TASK_STORE_PATH"] = str((REPORT_ROOT / "local-tasks.sqlite3").resolve())
    os.environ["BIOINFO_REQUIRE_API_KEY"] = "false"
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.services.task_registry import reset_registry

    reset_registry()
    return TestClient(app)


def validate_dataset(dataset: dict[str, Any], *, client: Any, mode: str) -> dict[str, Any]:
    from backend.app.services.local_agent_simulator import LocalAgentSimulator

    _verify_prepared_inputs(dataset)
    relative_root = dataset["dataset_id"]
    request = {
        "project_name": dataset["dataset_id"],
        "metadata_file": f"{relative_root}/metadata.csv",
        "count_matrix_file": f"{relative_root}/counts.csv",
        "sample_id_column": "sample_id",
        "group_column": dataset["contrast"]["column"],
        "contrast_numerator": dataset["contrast"]["numerator"],
        "contrast_denominator": dataset["contrast"]["denominator"],
        "execution_mode": "minimal_real",
        "analysis_method": "minimal_cpm_log2fc",
    }
    workflow = LocalAgentSimulator(client).simulate_workflow(request)
    if not workflow.get("completed"):
        steps = workflow.get("steps") if isinstance(workflow.get("steps"), list) else []
        last_error = steps[-1].get("error") if steps and isinstance(steps[-1], dict) else None
        error_code = last_error.get("code") if isinstance(last_error, dict) else "WORKFLOW_INCOMPLETE"
        raise ReferenceDataError(
            f"Reference workflow did not complete successfully ({error_code})."
        )
    task_id = workflow["task_id"]
    summary = workflow.get("summary") or {}
    artifacts = workflow.get("artifacts") or {}
    status = _json_request(client, "GET", f"/task/{task_id}/status")
    audit = _json_request(client, "GET", f"/task/{task_id}/audit")
    preflight = _json_request(client, "GET", "/task/formal-de/preflight")
    qc = _download_json(client, summary, "qc_summary.json")
    ranking = _download_ranking(client, summary)
    observation = _build_observation(summary, artifacts, status, qc, ranking, preflight)
    golden = load_json_object(ROOT / Path(dataset["golden_result"]))
    comparison = compare_golden_result(
        observation, golden, environment={"deseq2_ready": preflight.get("ready") is True}
    )
    reproducibility = _compare_previous(dataset["dataset_id"], mode, observation)
    result = {
        "report_schema_version": "1.0",
        "run_id": _run_id(dataset["dataset_id"], mode),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repository_commit": _repository_commit(),
        "application_version": "FastAPI OpenAPI contract at repository commit",
        "execution_mode": mode,
        "dataset_id": dataset["dataset_id"],
        "source_version": dataset["source_version"],
        "input_checksums": _prepared_checksums(dataset),
        "preprocessing_version": dataset["preprocessing"]["version"],
        "method": summary.get("analysis_method"),
        "contrast": summary.get("contrast"),
        "terminal_status": status.get("status"),
        "comparison": comparison,
        "warnings": summary.get("warnings", []),
        "limitations": summary.get("limitations", []),
        "reliability": summary.get("reliability_information"),
        "interpretation_boundary": summary.get("interpretation_boundary"),
        "artifact_inventory": _artifact_inventory(summary),
        "audit_event_types": [event.get("event_type") for event in audit.get("events", [])],
        "deseq2": _deseq2_policy(preflight),
        "reproducibility": reproducibility,
        "environment": {"runtime": "local_python" if mode == "local" else "protected_local_staging", "secrets_recorded": False},
        "skipped_checks": [] if preflight.get("ready") else ["DESeq2 execution validation"],
        "known_limitations": dataset["known_limitations"],
        "scientific_conclusion_generated": False,
        "pass": comparison["passed"],
    }
    _assert_safe_report(result)
    _write_dataset_result(dataset["dataset_id"], mode, result, observation, comparison)
    return result


def _verify_prepared_inputs(dataset: dict[str, Any]) -> None:
    paths = {entry["role"]: prepared_dataset_root(dataset) / ("metadata.csv" if entry["role"] == "metadata" else "counts.csv") for entry in dataset["expected_files"]}
    expected = {entry["role"]: entry["sha256"] for entry in dataset["expected_files"]}
    for role, path in paths.items():
        if not path.is_file() or sha256_file(path) != expected[role]:
            raise ReferenceDataError("Prepared reference input is missing or has changed.")


def _json_request(client: Any, method: str, path: str) -> dict[str, Any]:
    response = client.request(method, path)
    if response.status_code != 200:
        raise ReferenceDataError("Reference validation API request failed.")
    value = response.json()
    if not isinstance(value, dict):
        raise ReferenceDataError("Reference validation API returned an invalid object.")
    return value


def _download_response(client: Any, summary: dict[str, Any], name: str) -> SimpleResponse:
    url = (summary.get("download_links") or {}).get(name)
    if not isinstance(url, str) or not url.startswith("/task/"):
        raise ReferenceDataError("Required task-scoped artifact link is unavailable.")
    response = client.request("GET", url)
    if response.status_code != 200:
        raise ReferenceDataError("Required task-scoped artifact could not be downloaded.")
    return response


def _download_json(client: Any, summary: dict[str, Any], name: str) -> dict[str, Any]:
    value = _download_response(client, summary, name).json()
    if not isinstance(value, dict):
        raise ReferenceDataError("Downloaded JSON artifact is invalid.")
    return value


def _download_ranking(client: Any, summary: dict[str, Any]) -> list[dict[str, str]]:
    content = _download_response(client, summary, "differential_expression_results.csv").content
    try:
        rows = list(csv.DictReader(io.StringIO(content.decode("utf-8"))))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ReferenceDataError("Downloaded ranking artifact is invalid.") from exc
    if not rows:
        raise ReferenceDataError("Downloaded ranking artifact is empty.")
    return rows


def _build_observation(
    summary: dict[str, Any], artifacts: dict[str, Any], status: dict[str, Any],
    qc: dict[str, Any], ranking: list[dict[str, str]], preflight: dict[str, Any]
) -> dict[str, Any]:
    selected = {row["gene_id"]: float(row["log2_fold_change"]) for row in ranking[:50]}
    numeric_values = [float(row["log2_fold_change"]) for row in ranking]
    if not all(value == value and abs(value) != float("inf") for value in numeric_values):
        raise ReferenceDataError("Non-finite value appeared in the user-facing ranking.")
    return {
        "analysis_method": summary.get("analysis_method"),
        "comparison_direction": (summary.get("contrast") or {}).get("direction"),
        "input_sample_count": qc.get("sample_count"),
        "input_gene_count": qc.get("gene_count"),
        "retained_gene_count": qc.get("retained_gene_count_after_filtering"),
        "terminal_task_status": status.get("status"),
        "statistical_test_performed": summary.get("statistical_test_performed"),
        "pvalue_available": summary.get("pvalue_available"),
        "adjusted_pvalue_available": summary.get("adjusted_pvalue_available"),
        "scientific_conclusion_generated": False,
        "reliability_information": summary.get("reliability_information"),
        "warnings": summary.get("warnings", []),
        "limitations": summary.get("limitations", []),
        "interpretation_boundary": summary.get("interpretation_boundary"),
        "summary_fields": sorted(summary),
        "artifact_categories": sorted({item.get("artifact_type") for item in summary.get("artifact_references", []) if item.get("artifact_type")}),
        "claims": [],
        "deseq2_execution_state": "available_for_separate_validation" if preflight.get("ready") else "unavailable",
        "selected_gene_log2fc": selected,
        "top_ranked_gene_ids": [row["gene_id"] for row in ranking[:50]],
        "ranking_log2fc_values": numeric_values,
    }


def _artifact_inventory(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"name": item.get("artifact_name"), "category": item.get("artifact_type"), "available": item.get("available")}
        for item in summary.get("artifact_references", [])
    ]


def _deseq2_policy(preflight: dict[str, Any]) -> dict[str, Any]:
    ready = preflight.get("ready") is True
    errors = [str(value) for value in preflight.get("errors", [])]
    return {
        "policy": "environment_dependent",
        "preflight_ready": ready,
        "preflight_errors": errors,
        "validation": "available_for_separate_real_execution" if ready else "skipped",
        "confidence_effect": "Formal DESeq2 behavior is unvalidated in this run." if not ready else "Preflight readiness alone is not an execution result.",
        "future_action": "Run a separate real DESeq2 validation only in a ready environment.",
        "simulated": False,
    }


def _prepared_checksums(dataset: dict[str, Any]) -> dict[str, str]:
    return {entry["role"]: entry["sha256"] for entry in dataset["expected_files"]}


def _compare_previous(dataset_id: str, mode: str, observation: dict[str, Any]) -> dict[str, Any]:
    root = REPORT_ROOT / "datasets" / dataset_id
    previous_path = root / f"{mode}-previous-observation.json"
    previous = load_json_object(previous_path) if previous_path.is_file() else None
    checks: dict[str, bool] = {}
    if previous:
        for field in (
            "terminal_task_status", "summary_fields", "artifact_categories", "warnings",
            "limitations", "interpretation_boundary", "comparison_direction", "analysis_method",
        ):
            checks[field] = previous.get(field) == observation.get(field)
        old_top = set(previous.get("top_ranked_gene_ids", [])[:20])
        new_top = set(observation.get("top_ranked_gene_ids", [])[:20])
        checks["top20_overlap_at_least_18"] = len(old_top & new_top) >= 18
        checks["selected_sign_agreement"] = all(
            (float(value) > 0) == (float(observation.get("selected_gene_log2fc", {}).get(gene, 0)) > 0)
            for gene, value in previous.get("selected_gene_log2fc", {}).items()
            if gene in observation.get("selected_gene_log2fc", {})
        )
    root.mkdir(parents=True, exist_ok=True)
    previous_path.write_text(json.dumps(observation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"previous_run_available": previous is not None, "checks": checks, "passed": all(checks.values()) if checks else None}


def _write_dataset_result(dataset_id: str, mode: str, result: dict[str, Any], observation: dict[str, Any], comparison: dict[str, Any]) -> None:
    root = REPORT_ROOT / "datasets" / dataset_id
    root.mkdir(parents=True, exist_ok=True)
    documents = {
        f"{mode}-result.json": result,
        f"{mode}-observation.json": observation,
        f"{mode}-comparison.json": comparison,
        f"{mode}-artifact-inventory.json": {"artifacts": result["artifact_inventory"]},
    }
    for name, value in documents.items():
        (root / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_aggregate_report(results: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    report = {
        "report_schema_version": "1.0",
        "execution_mode": mode,
        "dataset_count": len(results),
        "datasets": [{"dataset_id": item["dataset_id"], "pass": item["pass"]} for item in results],
        "passed": bool(results) and all(item["pass"] for item in results),
        "scientific_boundary": "Golden Results detect regressions; passing does not prove biological truth.",
        "coze_integration": False,
        "remote_deployment": False,
    }
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    (REPORT_ROOT / "validation-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Phase 8.6 Validation Summary", "", f"- Mode: {mode}", f"- Passed: {str(report['passed']).lower()}", "", "Passing detects regressions and does not prove biological truth."]
    for item in results:
        lines.append(f"- {item['dataset_id']}: {'passed' if item['pass'] else 'failed'}")
    (REPORT_ROOT / "validation-summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def _assert_safe_report(value: dict[str, Any]) -> None:
    rendered = json.dumps(value, sort_keys=True).lower()
    for fragment in FORBIDDEN_REPORT_TEXT:
        if fragment in rendered:
            raise ReferenceDataError("Validation report contains unsafe internal material.")
    if WINDOWS_ABSOLUTE_PATH.search(rendered):
        raise ReferenceDataError("Validation report contains unsafe internal material.")
    secret = DEFAULT_SECRET.read_text(encoding="utf-8").strip() if DEFAULT_SECRET.is_file() else ""
    if secret and secret in rendered:
        raise ReferenceDataError("Validation report contains the protected staging API key.")


def _repository_commit() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def _run_id(dataset_id: str, mode: str) -> str:
    return f"phase-8-6-{mode}-{dataset_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


if __name__ == "__main__":
    raise SystemExit(main())
