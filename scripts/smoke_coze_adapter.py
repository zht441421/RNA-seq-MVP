import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


def request(base_url: str, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {method} {path}: {body}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Coze adapter smoke test.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--run-mode", default="mock")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    project = request(
        base_url,
        "POST",
        "/coze/projects",
        {
            "project_name": "Coze adapter smoke test",
            "omics_type": "bulk_rnaseq",
            "input_level": "count_matrix",
            "organism": "simulated",
            "gene_id_type": "symbol",
            "annotation_version": "simulated",
        },
    )
    project_id = project["project_id"]

    inspect = request(
        base_url,
        "POST",
        f"/coze/projects/{project_id}/inspect",
        {
            "count_matrix_path": "examples/real_small_count_matrix.csv",
            "metadata_path": "examples/real_small_metadata.csv",
        },
    )

    prepare = request(
        base_url,
        "POST",
        f"/coze/projects/{project_id}/prepare-analysis",
        {
            "gene_id_column": "gene_id",
            "sample_id_column": "sample_id",
            "group_column": "condition",
            "reference_group": "control",
            "test_group": "treatment",
            "batch_column": None,
            "covariates": [],
            "fdr_threshold": 0.05,
            "log2fc_threshold": 1.0,
            "run_enrichment": False,
        },
    )

    run = request(
        base_url,
        "POST",
        f"/coze/projects/{project_id}/confirm-and-run",
        {"confirmed": True, "run_mode": args.run_mode, "analysis_plan_overrides": {}},
    )
    status = request(base_url, "GET", f"/coze/projects/{project_id}/status")
    report = request(base_url, "GET", f"/coze/projects/{project_id}/report")
    manifest_files_count = len((run.get("artifact_manifest") or {}).get("files", []))

    print(f"project_id: {project_id}")
    print(f"qc_status: {prepare.get('qc_status')}")
    print(f"recommended_method: {(prepare.get('recommended_plan') or {}).get('primary_method')}")
    print(f"run_status: {run.get('run_status')}")
    print(f"reliability_grade: {run.get('reliability_grade')}")
    print(f"strong_conclusion_allowed: {report.get('strong_conclusion_allowed')}")
    print(f"manifest_files_count: {manifest_files_count}")
    print(f"next_action: {status.get('next_action')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

